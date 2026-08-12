"""Unit tests for core ATE modules (strategy_core, command_store, performance).

NOTE: This file was rewritten during the BUG-FIX cleanup pass. The previous
version imported `risk_gate` and used a pre-refactor `server.py` API that no
longer exists (risk_gate.py / ws_hub.py were consolidated into server.py, and
the fail-closed risk gate is now `server.evaluate_risk_gate`, covered by
`dashboard/tests/test_risk_gate.py`). Only the tests that target modules still
in production are kept here.
"""

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "dashboard"))

from command_store import CommandStore  # noqa: E402
from performance import ClosedTrade, calculate_performance  # noqa: E402
from strategy_core import SignalAction, decide_signal  # noqa: E402


class CoreStrategyTests(unittest.TestCase):
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


class CommandStoreTests(unittest.TestCase):
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


class PerformanceTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
