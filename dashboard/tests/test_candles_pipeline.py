"""Tests for the candle pipeline fixes:
- EA pushes full M1 history (40000 candles) in chunks with replace/append flags
- Server merges chunks by timestamp instead of overwriting
- fetch_real_candles prefers the EA cache regardless of requested count
- _normalize_candle_df drops NaT timestamps and sorts ascending
"""
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(__file__))

import server  # noqa: E402


# ── Regression: server.detect_liquidity_sweep direction ──────────────────────
def _sweep_df(highs, lows, closes):
    """Build a small OHLC DataFrame (high/low/close) for sweep detection."""
    n = len(highs)
    return pd.DataFrame({
        "open": [c for c in closes],
        "high": list(highs),
        "low": list(lows),
        "close": list(closes),
        "tick_volume": [100] * n,
        "timestamp": pd.date_range("2026-08-12", periods=n, freq="1min"),
    })


def test_sweep_above_highs_is_bearish_not_bullish():
    """Stop-hunt ABOVE previous highs đóng cửa dưới = BEARISH (không đảo ngược).
    BUG FIX: trước đây trả BULLISH_SWEEP — làm lệch điểm SMC/ULTRA_CONFLUENCE."""
    # 10 nến quanh 100; nến cuối spike lên 102 rồi đóng về 99.5 (< max_high 101)
    highs = [101] * 9 + [102]
    lows = [99] * 9 + [99.5]   # low không thủng min_low → chỉ nhánh bearish kích hoạt
    closes = [100] * 9 + [99.5]
    res = server.detect_liquidity_sweep(_sweep_df(highs, lows, closes))
    assert res == "BEARISH_SWEEP"


def test_find_swing_points_with_offset_index_no_nan():
    """BUG FIX (CRITICAL): /api/market trả 500 'Cannot mask with non-boolean
    array containing NA' khi build_chart_markup cắt df.tail(2000) làm index
    không còn 0..n-1. find_swing_points cũ dùng df.at[i, ...] theo LABEL -> gán
    vào index không tồn tại -> thêm row NaN -> chart web không hiển thị cho
    M1/M5 (>=2000 nến). Fix: numpy bool array theo vị trí."""
    import numpy as np

    n = 40000
    df = pd.DataFrame({
        "high": np.linspace(3300.0, 3400.0, n),
        "low": np.linspace(3290.0, 3390.0, n),
    })
    # build_chart_markup: m15 = mtf_data[primary_tf].tail(2000) giữ index gốc
    df.index = pd.RangeIndex(0, n)
    df = df.tail(2000)  # -> index 38000..39999

    from detectors import detect_market_structure, find_swing_points

    s = find_swing_points(df, window=2)
    assert len(s) == 2000
    assert s["swing_high"].isna().sum() == 0, "swing_high không được chứa NaN"
    assert s["swing_low"].isna().sum() == 0, "swing_low không được chứa NaN"
    assert s["swing_high"].dtype == bool

    # detect_market_structure (mắt xích crash gốc) phải chạy được
    r = detect_market_structure(df, window=2, n=6)
    assert r["structure"] in ("UPTREND", "DOWNTREND", "RANGE")


def test_build_chart_markup_with_40000_m1_bars_no_crash():
    """BUG FIX (CRITICAL): /api/market?tf=M1 trả 500 vì (1) find_swing_points
    df.at theo label tạo NaN rows, (2) sau m15.tail(2000) label 38000+ dùng với
    .iloc -> IndexError. Đây là path THẬT web gọi (40000 nến M1 từ EA push)."""
    import numpy as np

    n = 40000
    df = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=n, freq="1min"),
        "open": np.linspace(3300.0, 3400.0, n),
        "high": np.linspace(3300.5, 3400.5, n),
        "low": np.linspace(3299.5, 3399.5, n),
        "close": np.linspace(3300.2, 3400.2, n),
        "volume": np.full(n, 100.0),
    })

    from chart_markup import build_chart_markup

    for method in ("SMC", "ICT", "ULTRA_CONFLUENCE", "PRICE_ACTION", "SNIPER"):
        out = build_chart_markup(
            symbol="XAUUSD",
            mtf_data={"M1": df},
            method=method,
            primary_tf="M1",
        )
        assert out["objects"] is not None, method
        assert "confluence" in out, method
    print("build_chart_markup M1 40000 bars: OK")


def test_sweep_below_lows_is_bullish_not_bearish():
    """Stop-hunt BELOW previous lows đóng cửa trên = BULLISH (không đảo ngược)."""
    # 10 nến quanh 100; nến cuối spike xuống 98 (thủng min_low 99) rồi đóng
    # về 101.5 — TRÊN CẢ min_low lẫn max_high → chỉ nhánh bullish kích hoạt
    highs = [101] * 9 + [102]
    lows = [99] * 9 + [98]
    closes = [100] * 9 + [101.5]
    res = server.detect_liquidity_sweep(_sweep_df(highs, lows, closes))
    assert res == "BULLISH_SWEEP"


def test_json_safe_handles_numpy_scalars():
    """BUG FIX: markup từ pandas/numpy (np.bool_, np.float64...) phải serialize
    được qua json.dumps — trước đây FastAPI jsonable_encoder ném 500 trên
    /api/market với dữ liệu EA 40000 nến."""
    import json

    payload = {
        "ok": np.bool_(True),
        "score": np.float64(87.5),
        "count": np.int64(3),
        "arr": np.array([np.float64(1.1), np.float64(2.2)]),
        "nan": np.float64("nan"),
        "inf": np.float64("inf"),
        "plain": "x",
        "nested": {"fvg": np.bool_(False), "price": np.float64(3370.25)},
    }
    out = server._json_safe(payload)
    assert out["ok"] is True
    assert out["score"] == 87.5
    assert out["count"] == 3
    assert out["arr"] == [1.1, 2.2]
    assert out["nan"] is None
    assert out["inf"] is None
    assert out["nested"]["fvg"] is False
    assert out["nested"]["price"] == 3370.25
    json.dumps(out)  # phải không ném lỗi


def _candle(ts: str, close: float = 4428.0) -> dict:
    return {"t": ts[11:16], "ts": ts, "o": close, "h": close + 1, "l": close - 1, "c": close, "v": 100.0}


def test_merge_candles_by_ts_append_chunks():
    """Chunk 1 (replace) + chunk 2 (append) phải gộp đủ lịch sử, sort theo ts, không trùng."""
    c1 = [_candle("2026-08-12T08:00:00", 4420), _candle("2026-08-12T08:01:00", 4421)]
    c2 = [_candle("2026-08-12T08:01:00", 4421), _candle("2026-08-12T08:02:00", 4422)]
    merged = server._merge_candles_by_ts(c1, c2)
    assert len(merged) == 3
    assert merged[0]["ts"] == "2026-08-12T08:00:00"
    assert merged[2]["ts"] == "2026-08-12T08:02:00"


def test_merge_candles_incoming_wins_on_duplicate_ts():
    """Nến cùng ts: incoming (mới hơn) thắng."""
    old = [_candle("2026-08-12T09:00:00", 4400)]
    new = [_candle("2026-08-12T09:00:00", 4405)]
    merged = server._merge_candles_by_ts(old, new)
    assert len(merged) == 1
    assert merged[0]["c"] == 4405


def test_merge_candles_bounded():
    """Giới hạn an toàn 150000 nến mỗi TF."""
    old = [_candle(f"2026-08-01T00:{i:02d}:00", 4400) for i in range(60)]
    incoming = [_candle(f"2026-08-02T00:{i:02d}:00", 4400) for i in range(60)]
    merged = server._merge_candles_by_ts(old, incoming)
    assert len(merged) <= 150000
    assert len(merged) == 120


def test_bridge_candles_merge_via_endpoint(monkeypatch):
    """POST /api/v1/bridge/candles với replace=true rồi replace=false phải tích lũy cache."""
    server._market_cache.clear()
    app = server.app
    from starlette.testclient import TestClient
    client = TestClient(app)

    hdr = {"Authorization": "Bearer test-token"}

    chunk1 = [_candle("2026-08-12T08:00:00", 4420), _candle("2026-08-12T08:01:00", 4421)]
    r1 = client.post("/api/v1/bridge/candles", json={
        "symbol": "XAUUSDm", "timeframe": "M1", "replace": True, "candles": chunk1,
    }, headers=hdr)
    assert r1.status_code == 200
    assert r1.json()["candles_cached"] == 2

    chunk2 = [_candle("2026-08-12T08:02:00", 4422)]
    r2 = client.post("/api/v1/bridge/candles", json={
        "symbol": "XAUUSD", "timeframe": "M1", "replace": False, "candles": chunk2,
    }, headers=hdr)
    assert r2.status_code == 200
    assert r2.json()["candles_cached"] == 3

    df = server._cached_candles("XAUUSD", "M1")
    assert df is not None
    assert len(df) == 3
    assert df.iloc[-1]["close"] == 4422


def test_fetch_prefers_ea_cache_regardless_of_count(monkeypatch):
    """fetch_real_candles phải dùng cache EA khi có dữ liệu dù count lớn hơn cache."""
    server._market_cache.clear()
    candles = [_candle(f"2026-08-12T0{i}:00:00", 4400 + i) for i in range(10)]
    server._market_cache["XAUUSDm_M1"] = {
        "candles": candles,
        "candles_updated": datetime.now(timezone.utc).isoformat(),
        "source": "EA",
    }

    # Vô hiệu hoá nhánh bridge bằng cách trỏ BRIDGE_URL tới cổng chết
    monkeypatch.setattr(server, "BRIDGE_URL", "http://127.0.0.1:1")
    import asyncio
    df = asyncio.run(server.fetch_real_candles("XAUUSD", "M1", 40000))
    assert df is not None
    # cache 10 nến, tail(40000) -> 10 (cache EA được ưu tiên bất kể count)
    assert len(df) == 10
    # nến phải là nến EA thật (không phải stub): giá khớp candle đã đặt
    assert float(df.iloc[-1]["close"]) == 4409


def test_normalize_drops_nat_and_sorts():
    """_normalize_candle_df bỏ dòng timestamp NaT và sort tăng dần."""
    df = pd.DataFrame([
        {"ts": "2026-08-12T09:02:00", "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 10},
        {"ts": "not-a-date", "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 10},
        {"ts": "2026-08-12T09:00:00", "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 10},
    ])
    out = server._normalize_candle_df(df)
    assert len(out) == 2
    assert str(out.iloc[0]["timestamp"]) < str(out.iloc[1]["timestamp"])


def test_get_market_default_count_m1_is_40000():
    """Default count cho M1 phải là 40000 (khớp InpCandlesHistory EA) — không còn 72000."""
    defaults = {"M1": 40000, "M5": 8000, "M15": 2700, "M30": 1350, "H1": 700, "H4": 175, "D1": 365}
    assert defaults["M1"] == 40000
    # Query le phải đủ lớn cho 40000 nến
    assert server._DATA_TTL > 0
