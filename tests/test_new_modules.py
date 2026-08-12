"""Unit tests for the production-hardening modules.

NOTE: This file was rewritten during the BUG-FIX cleanup pass. The previous
version imported `ws_hub.ConnectionManager` (module deleted — the WebSocket
logic was consolidated into server.py) and exercised a pre-refactor server API
(`server._CALENDAR_CACHE`, `server.execution_readiness`, `server.LIVE_ARMED`,
...) that no longer exists. Only the tests that target modules still in
production are kept here. These run offline (no MT5, no network).
"""

from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "dashboard"))

from logging_config import LogEvent, log_event, read_recent_logs, timed  # noqa: E402


class LoggingTests(unittest.TestCase):
    def test_log_event_writes_json_line(self) -> None:
        marker = f"selftest-{datetime.now(timezone.utc).timestamp()}"
        log_event(LogEvent.ORDER_SENT, component="selftest", marker=marker, volume=0.1)
        logs = read_recent_logs(limit=50)
        self.assertTrue(any(entry.get("marker") == marker for entry in logs))

    def test_timed_context_records_latency(self) -> None:
        with timed(LogEvent.TRADE_LATENCY, component="selftest"):
            sum(range(1000))
        logs = read_recent_logs(limit=10)
        latency_entries = [e for e in logs if e.get("event") == LogEvent.TRADE_LATENCY]
        self.assertTrue(latency_entries)
        self.assertIn("latency_ms", latency_entries[-1])

    def test_read_recent_logs_level_filter(self) -> None:
        log_event(LogEvent.WARNING, component="selftest", level=30)  # WARNING
        warning_only = read_recent_logs(limit=20, level="WARNING")
        self.assertTrue(all(e.get("level") == "WARNING" for e in warning_only))


if __name__ == "__main__":
    unittest.main()
