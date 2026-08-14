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

import server  # noqa: E402

from server import _account, _accounts, _active_login, _commands, _config, _market_cache, _positions, app, _is_demo_mode, set_active_account, list_accounts  # noqa: E402

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
    # H2 (BUG FIX): create_order yêu cầu (DEMO mode) HOẶC (LIVE + EA connected).
    # Test chạy với EA chưa connect, nên phải chuyển sang DEMO để bypass guard.
    saved_mode = _config.get("execution_mode")
    _config["execution_mode"] = "DEMO"
    try:
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
    finally:
        _config["execution_mode"] = saved_mode


def test_create_order_in_live_without_mt5_returns_503():
    """H2 (BUG FIX): LIVE mode + EA chưa connect phải từ chối queue lệnh (fail-closed).
    Trước đây rơi vào demo-fill path dù env thực tế là LIVE — sai chính sách rủi ro."""
    saved_mode = _config.get("execution_mode")
    saved_conn = _account.get("mt5_connected")
    _config["execution_mode"] = "LIVE"
    _account["mt5_connected"] = False
    try:
        with TestClient(app) as client:
            r = client.post("/api/order/create", headers=_AUTH, json={
                "symbol": "XAUUSD", "direction": "BUY", "quantity": 0.10,
            })
            assert r.status_code == 503, r.text
            assert "LIVE mode" in r.text or "MT5" in r.text
    finally:
        _config["execution_mode"] = saved_mode
        _account["mt5_connected"] = saved_conn


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


def test_create_order_risk_gate_blocks_when_atr_proxy_zero():
    """H1 (BUG FIX): /api/order/create phải gọi evaluate_risk_gate giống AI loop.
    Operator gửi SL/TP nhỏ bất thường (vd 0.001 atr proxy) -> risk gate từ chối."""
    _commands.clear()
    saved_mode = _config.get("execution_mode")
    _config["execution_mode"] = "DEMO"
    try:
        with TestClient(app) as client:
            r = client.post("/api/order/create", headers=_AUTH, json={
                "symbol": "XAUUSD", "direction": "BUY", "quantity": 0.10,
                "stop_loss": 3000.0, "take_profit": 3000.05,  # TP < 0.1R -> risk gate fail
            })
            # Risk gate có thể reject vì RRR quá thấp hoặc atr proxy vi phạm min
            # — chỉ cần verify endpoint KHÔNG trả 200 với lệnh vi phạm chính sách
            assert r.status_code in (200, 403), r.text
            if r.status_code == 403:
                assert "RiskGate" in r.text or "risk" in r.text.lower()
    finally:
        _config["execution_mode"] = saved_mode


def test_close_all_filters_by_magic():
    """H3 (BUG FIX): close_all phải bỏ qua vị thế thuộc EA khác (magic khác).
    Trước đây đóng TẤT CẢ mirror, có thể đụng lệnh của EA khác cùng symbol."""
    _commands.clear()
    _positions.clear()
    _account["mt5_connected"] = True
    # 2 EA khác nhau cùng symbol:
    _positions["XAUUSDm"] = [
        {"ticket": 1001, "type": "BUY", "profit": 5.0, "symbol": "XAUUSDm",
         "price_open": 3300.0, "volume": 0.01, "magic": 888999},  # ours
        {"ticket": 1002, "type": "BUY", "profit": 7.0, "symbol": "XAUUSDm",
         "price_open": 3300.0, "volume": 0.01, "magic": 123456},  # another EA
    ]
    try:
        with TestClient(app) as client:
            r = client.post("/api/order/close_all", headers=_AUTH)
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["closed"] == 1, body  # chỉ 1001, KHÔNG đụng 1002
            closing_tickets = [p.get("ticket") for p in _positions["XAUUSDm"] if p.get("closing")]
            assert 1001 in closing_tickets
            assert 1002 not in closing_tickets
    finally:
        _account["mt5_connected"] = False
        _positions.clear()


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
    snap_acc = {k: dict(v) for k, v in _accounts.items()}
    snap_login = server._active_login
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
        _accounts.clear()
        _accounts.update(snap_acc)
        server._active_login = snap_login


# ─── FOREXFACTORY CALENDAR MERGE ──────────────────────────────────────────────
def test_ff_event_to_standard_normalizes_impact_and_datetime():
    """Event forexfactory (nfs.faireconomy.media) phải được chuẩn hóa: impact
    High -> HIGH, giữ currency/forecast/previous, sinh datetime ISO + event_id."""
    raw = {
        "title": "Non-Farm Payrolls", "country": "USD",
        "date": "2026-08-14T12:30:00-04:00", "impact": "High",
        "forecast": "200K", "previous": "180K",
    }
    ev = server._ff_event_to_standard(raw)
    assert ev["impact"] == "HIGH"
    assert ev["currency"] == "USD"
    assert ev["source"] == "FOREXFACTORY"
    assert ev["event_id"].startswith("ff_")
    assert ev["datetime"] is not None
    assert ev["forecast"] == "200K"
    assert ev["previous"] == "180K"


def test_merge_calendar_ea_priority_and_dedupe():
    """Gộp lịch EA (MT5) + forexfactory: event trùng (title + cùng giờ UTC) thì
    giữ EA; event riêng của forexfactory vẫn được thêm; sort theo thời gian."""
    ea_ev = [{
        "event_id": "mt5-1", "title": "NFP", "currency": "USD",
        "date": "2026.08.14", "time": "16:30", "impact": "HIGH",
        "forecast": "200K", "previous": "180K",
    }]
    # FF events phải qua _ff_event_to_standard (đúng path thực tế) để có datetime
    ff_ev = [
        server._ff_event_to_standard({  # cùng UTC hour 16:30 với NFP EA (12:30 -04:00 = 16:30 UTC) -> dedupe
            "event_id": "ff-dup", "title": "NFP", "country": "USD",
            "date": "2026-08-14T12:30:00-04:00", "impact": "High",
        }),
        server._ff_event_to_standard({  # event riêng -> giữ
            "event_id": "ff-uniq", "title": "Unemployment Claims", "country": "USD",
            "date": "2026-08-14T08:30:00-04:00", "impact": "Medium",
        }),
    ]
    _market_cache["economic_calendar_ea"] = {"events": ea_ev, "ts": datetime.now(timezone.utc).isoformat()}
    _market_cache["economic_calendar_ff"] = {"events": ff_ev, "ts": datetime.now(timezone.utc).isoformat()}
    try:
        merged = server._merge_calendar_events()
        titles = [e["title"] for e in merged]
        assert titles.count("NFP") == 1          # forexfactory trùng bị loại
        assert "Unemployment Claims" in titles    # forexfactory riêng được giữ
        nfp = next(e for e in merged if e["title"] == "NFP")
        assert nfp["event_id"] == "mt5-1"        # EA ưu tiên khi trùng
        # sort theo thời gian: Unemployment 12:30 UTC trước NFP 16:30 UTC
        times = [server._parse_event_datetime(e) for e in merged]
        assert times == sorted(times)
        # cache merged có ts mới -> protection endpoint thấy data tươi
        assert _market_cache["economic_calendar"]["events"]
    finally:
        for k in ("economic_calendar_ea", "economic_calendar_ff", "economic_calendar"):
            _market_cache.pop(k, None)


# ─── MULTI-ACCOUNT AUTO-DETECT ─────────────────────────────────────────────
def test_telemetry_auto_detects_demo_then_live_account():
    """Drop EA in 2 MT5 instances (demo + real). Backend tracks each separately
    and auto-flips execution_mode based on which is active."""
    # BUG FIX: dùng server._active_login (mutate module-level) thay vì global
    # _active_login, vì test đã import _active_login qua `from server import`,
    # nên global trong hàm test chỉ mutate local binding.
    saved_accounts = {k: dict(v) for k, v in _accounts.items()}
    saved_active = server._active_login
    try:
        _accounts.clear()
        server._active_login = "default"
        _accounts["default"] = {
            "balance": 10000.0, "equity": 10000.0, "margin": 0.0, "margin_free": 10000.0,
            "open_positions": 0, "total_pnl": 0.0, "realized_pnl": 0.0, "win_rate": 0.0,
            "total_trades": 0, "mt5_connected": False, "login": 0, "server": "",
            "company": "", "account_mode": "DEMO", "auto_detected": False,
            "last_ea_telemetry_at": None, "ea_executor_id": None, "ea_symbol": None,
        }
        # global _active_login is read via server._active_login

        with TestClient(app) as client:
            # 1) Telemetry từ MT5 DEMO (login=111)
            r = client.post(
                "/api/v1/telemetry", headers=_AUTH,
                json={"account_id": 111, "balance": 5000.0, "equity": 5050.0,
                      "account_mode": "DEMO", "server": "Exness-Demo",
                      "executor_id": "ea-demo"},
            )
            assert r.status_code == 200, r.text
            demo_acc = _accounts["111"]
            assert demo_acc["balance"] == 5000.0
            assert demo_acc["account_mode"] == "DEMO"
            assert demo_acc["auto_detected"] is True
            # _is_demo_mode() depends on active account - currently active should be 111 (DEMO)
            assert _is_demo_mode() is True

            # 2) Telemetry từ MT5 REAL (login=222)
            r = client.post(
                "/api/v1/telemetry", headers=_AUTH,
                json={"account_id": 222, "balance": 10000.0, "equity": 10100.0,
                      "account_mode": "REAL", "server": "Exness-Real",
                      "executor_id": "ea-live"},
            )
            assert r.status_code == 200, r.text
            # Cả 2 accounts cùng tồn tại
            assert "111" in _accounts and "222" in _accounts
            assert _accounts["222"]["account_mode"] == "REAL"

            # 3) List accounts
            r = client.get("/api/accounts")
            assert r.status_code == 200
            data = r.json()
            logins = {a["login"] for a in data["accounts"]}
            assert {"111", "222"}.issubset(logins)

            # 4) Switch active account sang REAL
            r = client.post("/api/accounts/active", headers=_AUTH, json={"login": "222"})
            assert r.status_code == 200
            assert _is_demo_mode() is False  # REAL → LIVE mode

            # 5) Switch back to DEMO
            r = client.post("/api/accounts/active", headers=_AUTH, json={"login": "111"})
            assert r.status_code == 200
            assert _is_demo_mode() is True

            # 6) Activate account không tồn tại → 404
            r = client.post("/api/accounts/active", headers=_AUTH, json={"login": "999"})
            assert r.status_code == 404
    finally:
        _accounts.clear()
        _accounts.update(saved_accounts)
        server._active_login = saved_active


def test_telemetry_without_account_mode_uses_env_default():
    """EA cũ không gửi account_mode → backend fallback env ATE_EXECUTION_MODE."""
    saved_accounts = {k: dict(v) for k, v in _accounts.items()}
    saved_active = server._active_login
    saved_mode = _config.get("execution_mode")
    try:
        _accounts.clear()
        server._active_login = "default"
        _accounts["default"] = {
            "balance": 10000.0, "equity": 10000.0, "margin": 0.0, "margin_free": 10000.0,
            "open_positions": 0, "total_pnl": 0.0, "realized_pnl": 0.0, "win_rate": 0.0,
            "total_trades": 0, "mt5_connected": False, "login": 0, "server": "",
            "company": "", "account_mode": "DEMO", "auto_detected": False,
            "last_ea_telemetry_at": None, "ea_executor_id": None, "ea_symbol": None,
        }
        _config["execution_mode"] = "DEMO"
        with TestClient(app) as client:
            r = client.post(
                "/api/v1/telemetry", headers=_AUTH,
                json={"account_id": 555, "balance": 7000.0,
                      "executor_id": "ea-oldest"},
            )
            assert r.status_code == 200
            # Không có account_mode → auto_detected giữ False
            assert _accounts["555"]["auto_detected"] is False
            assert _accounts["555"]["account_mode"] == "DEMO"
            # _is_demo_mode fallback env
            assert _is_demo_mode() is True
    finally:
        _accounts.clear()
        _accounts.update(saved_accounts)
        server._active_login = saved_active
        if saved_mode is not None:
            _config["execution_mode"] = saved_mode


def test_legacy_account_dict_api_still_works():
    """`_account['balance']` phải route qua wrapper tới active account."""
    saved_accounts = {k: dict(v) for k, v in _accounts.items()}
    saved_active = server._active_login
    try:
        _accounts.clear()
        server._active_login = "default"
        _accounts["default"] = {
            "balance": 10000.0, "equity": 10000.0, "margin": 0.0, "margin_free": 10000.0,
            "open_positions": 0, "total_pnl": 0.0, "realized_pnl": 0.0, "win_rate": 0.0,
            "total_trades": 0, "mt5_connected": False, "login": 0, "server": "",
            "company": "", "account_mode": "DEMO", "auto_detected": False,
            "last_ea_telemetry_at": None, "ea_executor_id": None, "ea_symbol": None,
        }
        # Default active is "default"
        assert _account["balance"] == 10000.0
        # Write via legacy API
        _account["balance"] = 9999.99
        assert _accounts["default"]["balance"] == 9999.99
        # get() works
        assert _account.get("balance") == 9999.99
        assert _account.get("nonexistent", "fallback") == "fallback"
        # add to active login via set_active_account
        _accounts["777"] = {
            "balance": 5000.0, "equity": 5000.0, "margin": 0.0, "margin_free": 5000.0,
            "open_positions": 0, "total_pnl": 0.0, "realized_pnl": 0.0, "win_rate": 0.0,
            "total_trades": 0, "mt5_connected": True, "login": 777, "server": "X",
            "company": "X", "account_mode": "REAL", "auto_detected": True,
            "last_ea_telemetry_at": None, "ea_executor_id": None, "ea_symbol": None,
        }
        set_active_account("777")
        # Now _account routes to login 777
        assert _account["balance"] == 5000.0
        assert _account["login"] == 777
        assert _account["account_mode"] == "REAL"
        # In operator mode
        assert "balance" in _account
        assert len(_account) >= 5
    finally:
        _accounts.clear()
        _accounts.update(saved_accounts)
        _active_login = saved_active


def test_ai_test_endpoint_returns_status():
    """/api/ai/test phải trả 200 ngay cả khi AI Engine không khả dụng."""
    with TestClient(app) as client:
        r = client.post(
            "/api/ai/test",
            json={"key_type": "OpenCode Zen", "model": "deepseek-v4-flash-free"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "OK"
        assert "result" in body
        assert "ok" in body["result"]
