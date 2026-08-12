"""Unit tests for MT5 auto-deploy pure helpers and the AI provider error
classifier.

NOTE: This file was rewritten during the BUG-FIX cleanup pass. The previous
version imported `risk_profiles` (module deleted — risk profiles were merged
into server.py) and tested `server._encode_secret`/`save_control_config`
(pre-refactor API that no longer exists). Only the tests that target modules
still in production are kept here. These run offline (no network, no UI
automation).
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "dashboard"))

import mt5_auto  # noqa: E402
from ai_provider_test import classify_http_error  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
