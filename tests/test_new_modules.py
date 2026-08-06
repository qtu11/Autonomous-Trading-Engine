"""Unit tests for the new production-hardening modules.

Covers structured logging, the WebSocket connection manager, the real-calendar
cache, and the execution-readiness mode matrix. These run offline (no MT5, no
network) except where a faked websocket is injected.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "dashboard"))

import server  # noqa: E402
from logging_config import LogEvent, log_event, read_recent_logs, timed  # noqa: E402
from ws_hub import ConnectionManager  # noqa: E402


class _FakeWebSocket:
    """Minimal stand-in for a FastAPI WebSocket."""

    def __init__(self, fail_on_send: bool = False) -> None:
        self.accepted = False
        self.sent: list[str] = []
        self._fail = fail_on_send

    async def accept(self) -> None:
        self.accepted = True

    async def send_text(self, text: str) -> None:
        if self._fail:
            raise RuntimeError("connection reset")
        self.sent.append(text)


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


class WebSocketHubTests(unittest.TestCase):
    def test_broadcast_fans_out_to_all_clients(self) -> None:
        manager = ConnectionManager()
        ws_a, ws_b = _FakeWebSocket(), _FakeWebSocket()
        asyncio.run(manager.connect(ws_a))
        asyncio.run(manager.connect(ws_b))
        delivered = asyncio.run(manager.broadcast({"type": "telemetry", "data": {"ask": 1.0}}))
        self.assertEqual(delivered, 2)
        self.assertEqual(len(ws_a.sent), 1)
        self.assertEqual(len(ws_b.sent), 1)
        payload = json.loads(ws_a.sent[0])
        self.assertEqual(payload["type"], "telemetry")

    def test_broadcast_prunes_dead_connections(self) -> None:
        manager = ConnectionManager()
        live, dead = _FakeWebSocket(), _FakeWebSocket(fail_on_send=True)
        asyncio.run(manager.connect(live))
        asyncio.run(manager.connect(dead))
        delivered = asyncio.run(manager.broadcast({"type": "log", "data": {}}))
        self.assertEqual(delivered, 1)
        self.assertEqual(manager.count, 1)

    def test_disconnect_removes_client(self) -> None:
        manager = ConnectionManager()
        ws = _FakeWebSocket()
        asyncio.run(manager.connect(ws))
        asyncio.run(manager.disconnect(ws))
        self.assertEqual(manager.count, 0)


class CalendarCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        server._CALENDAR_CACHE["events"] = []
        server._CALENDAR_CACHE["received_at"] = None
        server._FF_CALENDAR_CACHE["events"] = []
        server._FF_CALENDAR_CACHE["fetched_at"] = None
        server._FF_CALENDAR_CACHE["last_attempt"] = datetime.now(timezone.utc)

    def test_empty_cache_returns_unavailable(self) -> None:
        events = server.fetch_real_economic_calendar()
        self.assertTrue(len(events) > 0)
        self.assertEqual(server.calendar_data_status(), "AI_FALLBACK")

    def test_fresh_push_is_served(self) -> None:
        server.update_calendar_cache([{"title": "NFP", "impact": "HIGH", "time": "13:30"}])
        events = server.fetch_real_economic_calendar()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["title"], "NFP")
        self.assertEqual(server.calendar_data_status(), "MT5_BROKER_LIVE")

    def test_stale_cache_is_not_served(self) -> None:
        server._CALENDAR_CACHE["events"] = [{"title": "Old"}]
        server._CALENDAR_CACHE["received_at"] = datetime.now(timezone.utc) - timedelta(seconds=2000)
        events = server.fetch_real_economic_calendar()
        self.assertEqual(server.calendar_data_status(), "AI_FALLBACK")


class ExecutionReadinessTests(unittest.TestCase):
    """Mode matrix must fail closed regardless of arming flags."""

    def setUp(self) -> None:
        self._mode = server.EXECUTION_MODE
        self._kill = server.KILL_SWITCH
        self._trading = server.ENABLE_TRADING

    def tearDown(self) -> None:
        server.EXECUTION_MODE = self._mode
        server.KILL_SWITCH = self._kill
        server.ENABLE_TRADING = self._trading

    def test_invalid_mode_rejected(self) -> None:
        server.EXECUTION_MODE = "BOGUS"
        ready, reason = server.execution_readiness()
        self.assertFalse(ready)
        self.assertEqual(reason, "REJECT_EXECUTION_MODE")

    def test_kill_switch_blocks_everything(self) -> None:
        server.EXECUTION_MODE = "DEMO"
        server.KILL_SWITCH = True
        ready, reason = server.execution_readiness()
        self.assertFalse(ready)
        self.assertEqual(reason, "REJECT_KILL_SWITCH")

    def test_trading_disabled_blocks(self) -> None:
        server.EXECUTION_MODE = "DEMO"
        server.KILL_SWITCH = False
        server.ENABLE_TRADING = False
        ready, reason = server.execution_readiness()
        self.assertFalse(ready)
        self.assertEqual(reason, "REJECT_TRADING_DISABLED")

    def test_live_requires_explicit_arm(self) -> None:
        server.EXECUTION_MODE = "LIVE"
        server.KILL_SWITCH = False
        server.ENABLE_TRADING = True
        server.LIVE_ARMED = False
        ready, reason = server.execution_readiness()
        self.assertFalse(ready)
        self.assertEqual(reason, "REJECT_LIVE_NOT_ARMED")


if __name__ == "__main__":
    unittest.main()
