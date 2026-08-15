"""Unit tests for DCA (Dollar Cost Averaging) logic.

Covers:
- _dca_evaluate: điều kiện thuần (lỗ >= N x ATR, mức tối đa, giãn cách, volume
  multiplier, giới hạn rủi ro theo balance, bắt buộc SL).
- _dca_check: queue lệnh DCA + demo fill khi EA chưa kết nối; tôn trọng
  kill switch / ai_auto_loop / news protection (fail-closed).
"""

import asyncio
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from server import (
    _account, _commands, _config, _dca_state, _market_cache, _positions,
    _dca_evaluate, _dca_check,
)


def _pos(**kw):
    p = {
        "ticket": 111, "symbol": "XAUUSDm", "type": "BUY", "volume": 0.01,
        "price_open": 3350.0, "sl": 3300.0, "orig_sl": 3300.0, "tp": 3450.0,
        "be_applied": False, "profit": 0.0, "current_price": 3350.0,
    }
    p.update(kw)
    return p


@pytest.fixture(autouse=True)
def _clean_state():
    _dca_state.clear()
    _commands.clear()
    _positions.clear()
    _market_cache.pop("economic_calendar", None)
    # BUG FIX (test isolation): snapshot account trước khi test mutate — các test
    # dưới set _account["balance"]=0.0/100.0 mà không restore → test_risk_gate chạy
    # sau đó fail vì risk_pct (balance=0). Giờ restore đầy đủ sau mỗi test.
    saved_account = {
        "balance": _account.get("balance"),
        "equity": _account.get("equity"),
        "mt5_connected": _account.get("mt5_connected"),
        "total_pnl": _account.get("total_pnl"),
    }
    _account["balance"] = 10000.0
    _account["equity"] = 10000.0
    _account["mt5_connected"] = False
    saved = {
        "execution_mode": _config.get("execution_mode"),
        "kill_switch": _config.get("kill_switch"),
        "dca_enabled": _config.get("dca_enabled"),
        "ai_auto_loop": _config.get("ai_auto_loop"),
    }
    yield
    for k, v in saved.items():
        _config[k] = v
    for k, v in saved_account.items():
        _account[k] = v
    _dca_state.clear()
    _commands.clear()


def _cfg(**kw):
    c = {
        "dca_enabled": True, "dca_max_levels": 2, "dca_distance_atr": 1.5,
        "dca_interval_sec": 300, "dca_volume_multiplier": 1.0,
        "dca_max_risk_balance_pct": 0.01,
    }
    c.update(kw)
    return c


def test_dca_evaluate_disabled_returns_none():
    assert _dca_evaluate(_pos(), 3300.0, 10.0, _cfg(dca_enabled=False)) is None


def test_dca_evaluate_no_loss_returns_none():
    # đang lời (current > entry) -> không nhồi
    assert _dca_evaluate(_pos(), 3370.0, 10.0, _cfg()) is None


def test_dca_evaluate_small_loss_returns_none():
    # lỗ 10 = 1.0 ATR < 1.5 ATR -> chưa đủ điều kiện
    assert _dca_evaluate(_pos(), 3340.0, 10.0, _cfg()) is None


def test_dca_evaluate_qualified_returns_level1():
    # lỗ 20 = 2.0 ATR >= 1.5 ATR -> level 1, volume cơ bản
    d = _dca_evaluate(_pos(), 3330.0, 10.0, _cfg())
    assert d is not None
    assert d["level"] == 1
    assert d["volume"] == 0.01
    assert d["adverse_atr"] == 2.0


def test_dca_evaluate_volume_multiplier():
    # multiplier áp dụng từ level 2 trở đi (level 1 luôn = volume cơ bản)
    _dca_state["XAUUSDm:111"] = {"level": 1, "last_add": ""}
    d = _dca_evaluate(_pos(), 3330.0, 10.0, _cfg(dca_volume_multiplier=2.0))
    assert d is not None
    assert d["level"] == 2
    assert d["volume"] == 0.02


def test_dca_evaluate_level_cap():
    _dca_state["XAUUSDm:111"] = {"level": 2, "last_add": ""}
    assert _dca_evaluate(_pos(), 3330.0, 10.0, _cfg(dca_max_levels=2)) is None
    _dca_state["XAUUSDm:111"] = {"level": 2, "last_add": ""}
    d = _dca_evaluate(_pos(), 3330.0, 10.0, _cfg(dca_max_levels=3))
    assert d is not None and d["level"] == 3


def test_dca_evaluate_interval_guard():
    _dca_state["XAUUSDm:111"] = {"level": 1, "last_add": datetime.now(timezone.utc).isoformat()}
    assert _dca_evaluate(_pos(), 3330.0, 10.0, _cfg()) is None


def test_dca_evaluate_risk_cap():
    # risk = (3350-3300)*0.01*100 = 50 = 0.5% balance -> OK
    assert _dca_evaluate(_pos(), 3330.0, 10.0, _cfg()) is not None
    # balance quá nhỏ -> vượt cap rủi ro
    _account["balance"] = 100.0
    assert _dca_evaluate(_pos(), 3330.0, 10.0, _cfg()) is None


def test_dca_evaluate_fail_closed_when_balance_zero():
    # FAIL-CLOSED: balance <= 0 (vd EA cũ gửi balance=0) -> không nhồi, kể cả
    # khi lỗ đã vượt ngưỡng — tránh bỏ qua cap rủi ro.
    _account["balance"] = 0.0
    assert _dca_evaluate(_pos(), 3330.0, 10.0, _cfg()) is None


def test_dca_evaluate_requires_sl():
    assert _dca_evaluate(_pos(sl=0), 3330.0, 10.0, _cfg()) is None


def test_dca_check_queues_command_and_demo_fill(monkeypatch):
    # Môi trường host đang LIVE — ép DEMO để test nhánh giả lập fill mirror
    _config["execution_mode"] = "DEMO"
    _config["dca_enabled"] = True
    _config["ai_auto_loop"] = True
    _positions["XAUUSDm"].append(_pos())

    async def fake_bid_ask(symbol):
        return (3300.0, 3300.5)

    def fake_risk_gate(**kw):
        return {"approved": True, "reason": "", "checks": {}}

    monkeypatch.setattr("server.fetch_real_bid_ask", fake_bid_ask)
    monkeypatch.setattr("server.evaluate_risk_gate", fake_risk_gate)

    asyncio.run(_dca_check("XAUUSD", "SMC", 10.0))

    dca_cmds = [c for c in _commands if str(c.get("reason", "")).startswith("DCA parent_ticket=111")]
    assert len(dca_cmds) == 1
    cmd = dca_cmds[0]
    assert cmd["action"] == "BUY"
    assert cmd["volume"] == 0.01
    assert cmd["entry"] == 3300.0
    assert cmd["stop_loss"] == 3300.0
    assert cmd["status"] == "FILLED"  # demo mirror fill vì EA chưa kết nối
    assert _dca_state.get("XAUUSDm:111", {}).get("level") == 1


def test_dca_check_skips_pending_duplicate(monkeypatch):
    """Đã có lệnh DCA QUEUED cho ticket -> không queue lệnh thứ 2."""
    _config["dca_enabled"] = True
    _config["ai_auto_loop"] = True
    _positions["XAUUSDm"].append(_pos())
    _commands.append({
        "command_id": "dca-pending", "ts": datetime.now(timezone.utc).isoformat(),
        "action": "BUY", "symbol": "XAUUSDm", "volume": 0.01,
        "reason": "DCA parent_ticket=111 level=1", "status": "QUEUED",
    })

    async def fake_bid_ask(symbol):
        return (3300.0, 3300.5)

    def fake_risk_gate(**kw):
        return {"approved": True, "reason": "", "checks": {}}

    monkeypatch.setattr("server.fetch_real_bid_ask", fake_bid_ask)
    monkeypatch.setattr("server.evaluate_risk_gate", fake_risk_gate)

    asyncio.run(_dca_check("XAUUSD", "SMC", 10.0))
    dca_cmds = [c for c in _commands if str(c.get("reason", "")).startswith("DCA parent_ticket=111")]
    assert len(dca_cmds) == 1  # chỉ lệnh ban đầu


def test_dca_check_respects_kill_switch():
    _config["dca_enabled"] = True
    _config["ai_auto_loop"] = True
    _config["kill_switch"] = True
    _positions["XAUUSDm"].append(_pos())
    asyncio.run(_dca_check("XAUUSD", "SMC", 10.0))
    assert not any(str(c.get("reason", "")).startswith("DCA") for c in _commands)
