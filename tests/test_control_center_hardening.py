"""Unit tests for Control Center hardening: secret codec, config persistence,
risk-profile defaults, MT5 auto-deploy pure helpers, and the AI provider
error classifier. These run offline (no network, no UI automation).
"""

from __future__ import annotations

import base64
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "dashboard"))

from risk_profiles import FOREX_RISK_PROFILES  # noqa: E402

# server.py re-applies persisted Control Center overrides (e.g. previous
# max_spread=1.0) onto FOREX_RISK_PROFILES at import time; capture the raw
# defaults BEFORE importing server so the default assertions stay truthful.
_GOLD_RAW_DEFAULTS = {
    sym: {
        "max_spread": FOREX_RISK_PROFILES[sym]["max_spread"],
        "version": FOREX_RISK_PROFILES[sym]["policy"].version,
        "risk_frac": FOREX_RISK_PROFILES[sym]["policy"].risk_per_trade_fraction,
        "enabled": FOREX_RISK_PROFILES[sym]["policy"].execution_enabled,
    }
    for sym in ("XAUUSD", "XAUUSDM")
}

import server  # noqa: E402
import mt5_auto  # noqa: E402
from ai_provider_test import classify_http_error  # noqa: E402


class SecretsCodecTests(unittest.TestCase):
    def test_encode_round_trip(self) -> None:
        secret = "sk-top-secret-value-123"
        stored = server._encode_secret(secret)
        self.assertTrue(stored.startswith("enc:v1:"))
        self.assertNotIn(secret, stored)
        self.assertEqual(server._decode_secret(stored), secret)

    def test_encode_is_idempotent(self) -> None:
        stored = server._encode_secret("abc")
        self.assertEqual(server._encode_secret(stored), stored)

    def test_empty_values_pass_through(self) -> None:
        self.assertEqual(server._encode_secret(""), "")
        self.assertEqual(server._decode_secret(""), "")

    def test_plaintext_decode_passthrough(self) -> None:
        self.assertEqual(server._decode_secret("plain-value"), "plain-value")

    def test_malformed_store_decodes_to_itself(self) -> None:
        self.assertEqual(server._decode_secret("enc:v1:!!!not-base64!!!"), "enc:v1:!!!not-base64!!!")

    def test_mask_field(self) -> None:
        self.assertEqual(server._mask_field("abc"), "*****")
        self.assertEqual(server._mask_field(""), "")


class ControlConfigPersistTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._orig_path = server.CONTROL_CONFIG_FILE
        self._orig_sync = server._firebase_sync_enabled
        server.CONTROL_CONFIG_FILE = os.path.join(self._tmp.name, "user_control_config.json")
        server._firebase_sync_enabled = False

    def tearDown(self) -> None:
        server.CONTROL_CONFIG_FILE = self._orig_path
        server._firebase_sync_enabled = self._orig_sync
        self._tmp.cleanup()

    def test_secret_fields_persisted_encoded(self) -> None:
        server.save_control_config({
            "gemini_api_key": "AIza-secret",
            "mt5_password": "p@ss",
            "execution_mode": "DEMO",
        })
        with open(server.CONTROL_CONFIG_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        self.assertIn("enc:v1:", raw["gemini_api_key"])
        self.assertIn("enc:v1:", raw["mt5_password"])
        self.assertEqual(raw["execution_mode"], "DEMO")

    def test_plaintext_secret_never_on_disk(self) -> None:
        server.save_control_config({"openai_api_key": "sk-proj-raw"})
        disk = open(server.CONTROL_CONFIG_FILE, encoding="utf-8").read()
        self.assertNotIn("sk-proj-raw", disk)

    def test_round_trip_via_load(self) -> None:
        server.save_control_config({
            "grok_api_key": "xai-secret",
            "gateway_key": "sk-or-secret",
            "clone_qtus_mode": "hybrid",
        })
        loaded = server.load_control_config()
        self.assertEqual(loaded["grok_api_key"], "xai-secret")
        self.assertEqual(loaded["gateway_key"], "sk-or-secret")
        self.assertEqual(loaded["clone_qtus_mode"], "hybrid")

    def test_config_updated_at_is_stamped(self) -> None:
        server.save_control_config({"execution_mode": "LIVE"})
        loaded = server.load_control_config()
        self.assertTrue(loaded.get("config_updated_at"))

    def test_secret_fields_tupled(self) -> None:
        for field in ("mt5_password", "telegram_bot_token", "gemini_api_key",
                      "claude_api_key", "deepseek_api_key", "openai_api_key",
                      "zplay_api_key", "grok_api_key", "qwen_api_key", "gateway_key"):
            self.assertIn(field, server.CONFIG_SECRET_FIELDS)


class RiskDefaultsTests(unittest.TestCase):
    def test_xauusd_conservative_defaults(self) -> None:
        prof = _GOLD_RAW_DEFAULTS["XAUUSD"]
        self.assertEqual(prof["max_spread"], 0.50)
        self.assertEqual(prof["risk_frac"], 0.01)
        self.assertEqual(prof["version"], "xauusd-v3")
        self.assertTrue(prof["enabled"])

    def test_xauusdm_shared_defaults(self) -> None:
        prof = _GOLD_RAW_DEFAULTS["XAUUSDM"]
        self.assertEqual(prof["max_spread"], 0.50)
        self.assertEqual(prof["risk_frac"], 0.01)

    def test_all_gold_profiles_allow_execution(self) -> None:
        for sym in ("XAUUSD", "XAUUSDM"):
            self.assertTrue(_GOLD_RAW_DEFAULTS[sym]["enabled"])


class Mt5AutoPureTests(unittest.TestCase):
    def test_timeframe_keys_complete(self) -> None:
        for tf in ("M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1"):
            self.assertIn(tf, mt5_auto.TIMEFRAME_KEYS)

    def test_find_terminal64_rejects_junk_path(self) -> None:
        ok, path, msg = mt5_auto.find_terminal64(r"Z:\no\such\dir\terminal64.exe")
        self.assertFalse(ok)
        self.assertIsNone(path)
        self.assertIn("Đường dẫn không hợp lệ", msg)

    def test_find_terminal64_rejects_dir_without_exe(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            ok, path, msg = mt5_auto.find_terminal64(d)
        self.assertFalse(ok)
        self.assertIsNone(path)
        self.assertIn("Không tìm thấy terminal64.exe", msg)

    def test_copy_expert_rejects_missing_data_path(self) -> None:
        ok, msg, dst = mt5_auto.copy_expert_to_data(r"Z:\no\such\data\path")
        self.assertFalse(ok)
        self.assertIsNone(dst)
        self.assertTrue(msg)

    def test_manual_checklist_is_non_empty(self) -> None:
        report = {
            "steps": [
                {"name": "locate_terminal64", "ok": True, "message": "ok"},
                {"name": "open_chart", "ok": False, "message": "Chưa cài pywinauto"},
            ],
        }
        checklist = mt5_auto.manual_checklist(report)
        self.assertIn("[OK]", checklist)
        self.assertIn("[!!]", checklist)
        self.assertIn("open_chart", checklist)


class AiErrorClassifierTests(unittest.TestCase):
    @staticmethod
    def _http_error(code: int) -> urllib.error.HTTPError:
        return urllib.error.HTTPError(
            url="https://api.example.com/v1/chat/completions",
            code=code,
            msg="error",
            hdrs={"Content-Type": "application/json"},
            fp=io.BytesIO(json.dumps({"error": {"message": "quota exceeded"}}).encode("utf-8")),
        )

    def test_rate_limited_mapped(self) -> None:
        code, msg = classify_http_error(self._http_error(429))
        self.assertEqual(code, "RATE_LIMITED")
        self.assertIn("rate/quota", msg)

    def test_invalid_key_mapped(self) -> None:
        code, _ = classify_http_error(self._http_error(401))
        self.assertEqual(code, "INVALID_KEY")

    def test_unknown_status_falls_back(self) -> None:
        code, msg = classify_http_error(self._http_error(599))
        self.assertEqual(code, "HTTP_599")
        self.assertIn("599", msg)


class SymbolResolveShapeTests(unittest.TestCase):
    def test_resolve_returns_pair(self) -> None:
        resolved, reason = server.resolve_symbol_info("XAUUSDm")
        self.assertIsInstance(resolved, str)
        self.assertIsInstance(reason, str)


class ProtectedRouteTests(unittest.TestCase):
    """Every mutation route that touches execution state, positions, ledger
    commands, brain adjustments, or telegram/test triggers MUST require the
    operator token. These routes were previously reachable without auth.
    """

    PROTECTED = [
        ("POST", "/api/control-center/mode"),
        ("POST", "/api/orders/close-profitable"),
        ("POST", "/api/orders/close-losing"),
        ("PATCH", "/api/brain/adjustments/{adjustment_id}"),
        ("POST", "/api/telegram/test_morning_news"),
        ("POST", "/api/telegram/test_evening_pnl"),
    ]

    def _route_has_operator_auth(self, method: str, path: str) -> bool:
        app_path = path.split("?")[0]
        for route in server.app.routes:
            if getattr(route, "path", None) != app_path:
                continue
            if method not in getattr(route, "methods", set()):
                continue
            deps = getattr(route, "dependencies", None) or []
            if any(getattr(d, "dependency", None) is server.require_operator_token for d in deps):
                return True
        return False

    def test_mutation_routes_require_operator_token(self) -> None:
        for method, path in self.PROTECTED:
            self.assertTrue(
                self._route_has_operator_auth(method, path),
                f"{method} {path} must require operator token",
            )


if __name__ == "__main__":
    unittest.main()