"""Unit tests for the EA <-> FastAPI bridge protocol fixes.

Covers the bugs fixed in this pass:
- BUG: claim response must be COMPACT JSON (separators=(',', ':')) so the MQL5
  EA's exact StringFind matches ("status":"CLAIMED") — otherwise claimed commands
  are never executed.
- BUG: create_order must return command_id + MANUAL_ORDER log (dead code was
  trapped inside news_analyze).
- BUG: economic-calendar/protection must compute a real lockdown/approaching
  level from EA-pushed events and expose BOTH key naming conventions.
- BUG: EXECUTED receipt from EA must create the mirrored position.
- Telemetry must update the account snapshot (balance/equity/login).
"""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

from server import _account, _commands, _config, _market_cache, _positions, app  # noqa: E402

_AUTH = {"Authorization": "Bearer test-token"}


def _queue_buy_cmd(cmd_id: str = "test-cmd-1") -> None:
    _commands.append({
        "command_id": cmd_id,
        "ts": datetime.now(timezone.utc).isoformat(),
        "action": "BUY",
        "symbol": "XAUUSDm",
        "magic": 888999,
        "volume": 0.01,
        "stop_loss": 3300.0,
        "take_profit": 3400.0,
        "entry": 3350.0,
        "reason": "unit test",
        "status": "QUEUED",
    })


def _post_events(events):
    with TestClient(app) as client:
        return client.post(
            "/api/v1/bridge/calendar",
            json={"executor_id": "ea-test", "events": events},
            headers=_AUTH,
        )


def test_claim_response_is_compact_json_with_singular_command_key():
    """EA parse response bằng StringFind khớp chính xác \"status\":\"CLAIMED\"
    (không khoảng trắng) và \"command\": (số ít). Phản hồi phải đúng dạng đó."""
    _commands.clear()
    _queue_buy_cmd()
    with TestClient(app) as client:
        r = client.post(
            "/api/v1/bridge/commands/claim",
            json={"executor_id": "ea-test", "symbol": "XAUUSD", "magic": 888999},
            headers=_AUTH,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "OK"
        assert body["count"] == 1
        assert "command" in body, "EA cần key 'command' (số ít) để thực thi"
        assert _commands[0]["status"] == "CLAIMED"

        raw = r.content.decode("utf-8")
        assert '"status":"CLAIMED"' in raw, f"compact JSON bắt buộc, got: {raw}"
        assert '"command":' in raw


def test_claim_requires_bearer_token():
    _commands.clear()
    _queue_buy_cmd()
    with TestClient(app) as client:
        r = client.post(
            "/api/v1/bridge/commands/claim",
            json={"executor_id": "ea-test", "symbol": "XAUUSD"},
        )
        assert r.status_code == 401


def test_create_order_returns_command_id_and_logs():
    """Dead code MANUAL_ORDER bị kẹt trong news_analyze -> lệnh tay không log."""
    _commands.clear()
    with TestClient(app) as client:
        r = client.post("/api/order/create", headers=_AUTH, json={
            "symbol": "XAUUSD", "direction": "BUY", "quantity": 0.10,
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "SUCCESS"
        assert body["command_id"]
        assert body["direction"] == "BUY"
        assert body["entry"] > 0
        assert any(c["command_id"] == body["command_id"] for c in _commands)

        logs = client.get("/api/logs").json()
        assert any(l.get("event") == "MANUAL_ORDER" for l in logs), (
            "create_order phải log MANUAL_ORDER")


def test_order_endpoints_require_bearer_token():
    """BUG FIX (SECURITY): /api/order/create, /api/order/close, /api/order/close_all
    trước đây KHÔNG check Bearer — ai cũng mở/đóng lệnh REAL qua backend public.
    Giờ phải 401 khi thiếu token (giống mọi endpoint khác)."""
    with TestClient(app) as client:
        r = client.post("/api/order/create", json={
            "symbol": "XAUUSD", "direction": "BUY", "quantity": 0.10,
        })
        assert r.status_code == 401, r.text
        r = client.post("/api/order/close", json={"ticket": 123456})
        assert r.status_code == 401, r.text
        r = client.post("/api/order/close_all")
        assert r.status_code == 401, r.text


def test_close_profitable_queues_ticket_filtered_close_in_live():
    """BUG FIX (HIGH): close-profitable khi EA connected trước đây gửi CLOSE_ALL
    -> đóng TẤT CẢ lệnh kể cả đang LỖ. Giờ chỉ queue CLOSE_POSITION cho từng
    ticket đang lời (mirror P&L cập nhật từ bid/ask thật)."""
    _commands.clear()
    _account["mt5_connected"] = True
    _positions["XAUUSDm"] = [
        {"ticket": 1001, "type": "BUY", "profit": 25.0, "symbol": "XAUUSDm",
         "price_open": 3300.0, "volume": 0.01},
        {"ticket": 1002, "type": "SELL", "profit": -12.0, "symbol": "XAUUSDm",
         "price_open": 3300.0, "volume": 0.01},
        # BUG FIX: mirror DEMO ảo (ticket rác) phải bị bỏ qua khi EA connected
        {"ticket": 1003, "type": "BUY", "profit": 40.0, "symbol": "XAUUSDm",
         "price_open": 3300.0, "volume": 0.01, "source": "DEMO"},
    ]
    try:
        with TestClient(app) as client:
            r = client.post("/api/orders/close-profitable", headers=_AUTH)
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["queued_for_ea"] is True
            assert body["closed"] == 1, body  # chỉ lệnh thật 1001, bỏ qua 1002 (lỗ) + 1003 (DEMO)
            actions = [(c.get("action"), c.get("ticket")) for c in _commands]
            assert ("CLOSE_POSITION", 1001) in actions, actions
            assert ("CLOSE_POSITION", 1002) not in actions, actions
            assert ("CLOSE_POSITION", 1003) not in actions, actions
            assert not any(c.get("action") == "CLOSE_ALL" for c in _commands), actions
    finally:
        _account["mt5_connected"] = False
        _positions.pop("XAUUSDm", None)


def test_executed_receipt_adds_position_mirror():
    _commands.clear()
    _positions.clear()
    _queue_buy_cmd("test-cmd-receipt")
    with TestClient(app) as client:
        client.post(
            "/api/v1/bridge/commands/claim",
            json={"executor_id": "ea-test", "symbol": "XAUUSD", "magic": 888999},
            headers=_AUTH,
        )
        r = client.post(
            "/api/v1/bridge/commands/test-cmd-receipt/receipt",
            json={
                "executor_id": "ea-test",
                "status": "EXECUTED",
                "order_ticket": 555001,
                "fill_price": 3350.0,
                "fill_volume": 0.01,
                "sl": 3300.0,
                "tp": 3400.0,
                "result_message": "done",
            },
            headers=_AUTH,
        )
        assert r.status_code == 200, r.text
        assert r.json()["new_status"] == "EXECUTED"
        pos = _positions.get("XAUUSDm", [])
        assert len(pos) == 1, "receipt EXECUTED phải tạo mirror position"
        assert pos[0]["ticket"] == 555001
        assert pos[0]["type"] == "BUY"


def test_economic_calendar_protection_computes_lockdown():
    """Endpoint protection phải tính lockdown từ event HIGH đang diễn ra và trả
    cả 2 bộ key (level / protection_level, live_seconds / live_remaining_seconds)."""
    now = datetime.now(timezone.utc)
    ev = {
        "event_id": "1",
        "date": now.strftime("%Y.%m.%d"),
        "time": now.strftime("%H:%M"),
        "title": "FOMC Statement",
        "impact": "HIGH",
    }
    _post_events([ev])
    with TestClient(app) as client:
        r = client.get("/api/economic-calendar/protection", headers=_AUTH)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["protection_level"] == "lockdown", body
        assert body["level"] == "lockdown"  # legacy key EA parse
        assert body["live_seconds"] == body["live_remaining_seconds"]
        assert body["next_event"] is not None
        assert body["next_event"]["title"] == "FOMC Statement"


def test_protection_lockdown_overrides_watch_regardless_of_order():
    """BUG FIX: nếu event watch (xa hơn) được xử lý TRƯỚC event lockdown (đang
    diễn ra), lockdown vẫn phải thắng — mức nghiêm nhất không phụ thuộc thứ tự."""
    now = datetime.now(timezone.utc)
    watch_ev = {
        "event_id": "w",
        "date": (now + timedelta(hours=3)).strftime("%Y.%m.%d"),
        "time": (now + timedelta(hours=3)).strftime("%H:%M"),
        "title": "Watch Event",
        "impact": "HIGH",
    }
    lockdown_ev = {
        "event_id": "l",
        "date": now.strftime("%Y.%m.%d"),
        "time": now.strftime("%H:%M"),
        "title": "NFP Release",
        "impact": "MED",
    }
    _post_events([watch_ev, lockdown_ev])
    with TestClient(app) as client:
        body = client.get("/api/economic-calendar/protection", headers=_AUTH).json()
        assert body["protection_level"] == "lockdown", body
        assert body["next_event"]["title"] == "NFP Release"


def test_economic_calendar_protection_unknown_without_data():
    """FAIL-CLOSED: không có dữ liệu lịch kinh tế (cache trống) -> "unknown" chứ
    KHÔNG phải "none" — EA phải CHẶN entry khi không có thông tin tin tức nào
    (trước đây trả "none" -> EA trade mù là FAIL-OPEN)."""
    _market_cache.pop("economic_calendar", None)
    with TestClient(app) as client:
        r = client.get("/api/v1/economic-calendar/protection", headers=_AUTH)
        assert r.status_code == 200
        body = r.json()
        assert body["protection_level"] == "unknown"
        assert body["level"] == "unknown"
        assert body["next_event"] is None
        assert body["data_available"] is False


def test_economic_calendar_protection_none_with_fresh_empty_calendar():
    """Calendar TƯƠI (EA vừa đẩy) nhưng không có event HIGH/MED -> "none"."""
    now = datetime.now(timezone.utc)
    _post_events([{
        "event_id": "low",
        "date": now.strftime("%Y.%m.%d"),
        "time": now.strftime("%H:%M"),
        "title": "Low Impact",
        "impact": "LOW",
    }])
    with TestClient(app) as client:
        body = client.get("/api/v1/economic-calendar/protection", headers=_AUTH).json()
        assert body["protection_level"] == "none"
        assert body["level"] == "none"
        assert body["data_available"] is True


def test_telemetry_updates_account_and_tick():
    snap = {
        "mt5_connected": _account.get("mt5_connected"),
        "login": _account.get("login"),
        "balance": _account.get("balance"),
        "equity": _account.get("equity"),
    }
    try:
        with TestClient(app) as client:
            r = client.post(
                "/api/v1/telemetry",
                json={
                    "symbol": "XAUUSDm",
                    "account_id": 999001,
                    "server": "ICMarkets-Demo",
                    "balance": 12345.6,
                    "equity": 12500.0,
                    "margin": 100.0,
                    "margin_free": 12245.6,
                    "bid": 3350.0,
                    "ask": 3350.5,
                    "positions": 2,
                    "executor_id": "ea-test",
                },
                headers=_AUTH,
            )
            assert r.status_code == 200, r.text
            assert r.json()["status"] == "OK"
            assert _account["balance"] == 12345.6
            assert _account["equity"] == 12500.0
            assert _account["login"] == 999001
            assert _account["server"] == "ICMarkets-Demo"
            tick = _market_cache.get("XAUUSDm_tick")
            assert tick is not None and tick["bid"] == 3350.0
    finally:
        for k, v in snap.items():
            _account[k] = v
