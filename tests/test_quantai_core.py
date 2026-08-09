import asyncio
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "dashboard"))
sys.path.insert(0, str(PROJECT_ROOT))

from command_store import CommandStore
from performance import ClosedTrade, calculate_performance
from risk_gate import AccountSnapshot, RiskPolicy, SymbolSpec, evaluate_risk
from strategy_core import SignalAction, decide_signal
import server


class ATECoreTests(unittest.TestCase):
    def test_strategy_abstains_without_required_features(self):
        proposal = decide_signal(
            symbol="EURUSD",
            timeframe="M15",
            indicators={},
            bid=1.1000,
            ask=1.1001,
        )
        self.assertEqual(proposal.action, SignalAction.NO_TRADE)
        self.assertIn("INSUFFICIENT_INDICATORS", proposal.reason_codes)

    def test_risk_gate_rejects_when_execution_is_disabled(self):
        proposal = decide_signal(
            symbol="EURUSD",
            timeframe="M15",
            indicators={"ema20": 1.2, "ema50": 1.1, "ema200": 1.0, "rsi": 60, "atr": 0.002},
            bid=1.2000,
            ask=1.2001,
        )
        result = evaluate_risk(
            proposal=proposal,
            account=AccountSnapshot(equity=10_000, margin_free=9_000, daily_realized_pnl=0),
            spec=SymbolSpec("EURUSD", 0.01, 2.0, 0.01, 0.00001, 1.0, 0.0003),
            bid=1.2000,
            ask=1.2001,
            open_position_count=0,
            policy=RiskPolicy(execution_enabled=False),
        )
        self.assertFalse(result.approved)
        self.assertIn("REJECT_EXECUTION_DISABLED", result.reason_codes)

    def test_risk_gate_rejects_non_finite_or_subminimum_volume(self):
        proposal = decide_signal(
            symbol="EURUSD",
            timeframe="M15",
            indicators={"ema20": 1.2, "ema50": 1.1, "ema200": 1.0, "rsi": 60, "atr": 0.002},
            bid=1.2000,
            ask=1.2001,
        )
        spec = SymbolSpec("EURUSD", 0.10, 2.0, 0.01, 0.00001, 1.0, 0.0003)
        policy = RiskPolicy(execution_enabled=True, risk_per_trade_fraction=0.000001)
        subminimum = evaluate_risk(
            proposal=proposal,
            account=AccountSnapshot(equity=10_000, margin_free=9_000, daily_realized_pnl=0),
            spec=spec,
            bid=1.2,
            ask=1.2001,
            open_position_count=0,
            policy=policy,
        )
        self.assertFalse(subminimum.approved)
        self.assertIn("REJECT_VOLUME_LIMIT", subminimum.reason_codes)
        non_finite = evaluate_risk(
            proposal=proposal,
            account=AccountSnapshot(equity=math.nan, margin_free=9_000, daily_realized_pnl=0),
            spec=spec,
            bid=1.2,
            ask=1.2001,
            open_position_count=0,
            policy=RiskPolicy(execution_enabled=True),
        )
        self.assertFalse(non_finite.approved)
        self.assertIn("REJECT_NON_FINITE_INPUT", non_finite.reason_codes)

    def test_command_store_is_idempotent_and_receipt_safe(self):
        with tempfile.TemporaryDirectory() as directory:
            store = CommandStore(str(Path(directory) / "commands.sqlite3"))
            first = store.create_command(
                idempotency_key="intent-1",
                action="BUY",
                symbol="EURUSD",
                magic=888999,
                volume=0.01,
                stop_loss=1.1,
                take_profit=1.2,
                reason="test",
            )
            repeated = store.create_command(
                idempotency_key="intent-1",
                action="BUY",
                symbol="EURUSD",
                magic=888999,
                volume=0.01,
                stop_loss=1.1,
                take_profit=1.2,
                reason="test",
            )
            self.assertEqual(first["command_id"], repeated["command_id"])
            claimed = store.claim_next(executor_id="ea-1", symbol="EURUSD", magic=888999)
            self.assertEqual(claimed["command_id"], first["command_id"])
            receipt = store.record_receipt(
                command_id=claimed["command_id"],
                executor_id="ea-1",
                receipt_id="receipt-1",
                status="REJECTED",
                retcode=10016,
                result_message="invalid stops",
            )
            replay = store.record_receipt(
                command_id=claimed["command_id"],
                executor_id="ea-1",
                receipt_id="receipt-1",
                status="REJECTED",
                retcode=10016,
                result_message="invalid stops",
            )
            self.assertEqual(receipt["state"], "REJECTED")
            self.assertEqual(receipt["command_id"], replay["command_id"])

    def test_unavailable_telemetry_never_fabricates_trade_data(self):
        original_has_mt5 = server.HAS_MT5
        try:
            server.HAS_MT5 = False
            telemetry = server.get_mt5_telemetry()
        finally:
            server.HAS_MT5 = original_has_mt5

        self.assertFalse(telemetry["mt5_connected"])
        self.assertEqual(telemetry["data_status"], "UNAVAILABLE")
        self.assertEqual(telemetry["current_ask"], 0.0)
        self.assertEqual(telemetry["ai_signal"]["primary_signal"], "NO_TRADE")
        self.assertEqual(telemetry["ai_signal"]["data_status"], "UNAVAILABLE")

    def test_demo_execution_fails_closed_when_mode_is_not_demo(self):
        original_mode = server.EXECUTION_MODE
        try:
            for invalid_mode in ("DISABLED", "INVALID_MODE", "OFF", ""):
                server.EXECUTION_MODE = invalid_mode
                ready, reason = server.demo_execution_status()
                self.assertFalse(ready)
                self.assertEqual(reason, "REJECT_EXECUTION_MODE")
        finally:
            server.EXECUTION_MODE = original_mode

    def test_control_center_status_is_sanitized_and_read_only(self):
        response = asyncio.run(server.get_control_center_status())
        serialized = json.dumps(response)
        self.assertIn("execution_locked", response["execution"])
        self.assertIn("browser_execution_enabled", response["execution"])
        for sensitive_key in ("bridge_token", "operator_token", "password", "idempotency_key", "receipt_id", "order_ticket"):
            self.assertNotIn(sensitive_key, serialized.lower())

    def test_bridge_token_requirement_fails_closed_when_unconfigured(self):
        original_token = server.BRIDGE_TOKEN
        try:
            server.BRIDGE_TOKEN = ""
            with self.assertRaises(Exception) as context:
                server.require_bridge_token(None)
        finally:
            server.BRIDGE_TOKEN = original_token

        self.assertEqual(context.exception.status_code, 503)

    def test_performance_calculates_peak_to_trough_drawdown(self):
        metrics = calculate_performance(
            [
                ClosedTrade(position_id=1, closed_at=1, net_profit=20),
                ClosedTrade(position_id=2, closed_at=2, net_profit=-5),
                ClosedTrade(position_id=3, closed_at=3, net_profit=-20),
            ]
        )
        self.assertEqual(metrics["sample_size"], 3)
        self.assertEqual(metrics["max_drawdown"], 25.0)
        self.assertEqual(metrics["win_rate"], 33.33)

    def test_execution_readiness_bypasses_mt5_when_force_unlocked(self):
        original_force_unlock = server.FORCE_UNLOCK
        original_mode = server.EXECUTION_MODE
        original_kill_switch = server.KILL_SWITCH
        original_enable_trading = server.ENABLE_TRADING
        try:
            server.FORCE_UNLOCK = True
            server.EXECUTION_MODE = "DEMO"
            server.KILL_SWITCH = False
            server.ENABLE_TRADING = True
            
            ready, reason = server.execution_readiness()
            self.assertTrue(ready)
            self.assertEqual(reason, "READY")
        finally:
            server.FORCE_UNLOCK = original_force_unlock
            server.EXECUTION_MODE = original_mode
            server.KILL_SWITCH = original_kill_switch
            server.ENABLE_TRADING = original_enable_trading


if __name__ == "__main__":
    unittest.main()

