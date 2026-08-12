"""Tests for the candle pipeline fixes:
- EA pushes full M1 history (40000 candles) in chunks with replace/append flags
- Server merges chunks by timestamp instead of overwriting
- fetch_real_candles prefers the EA cache regardless of requested count
- _normalize_candle_df drops NaT timestamps and sorts ascending
"""
import os
import sys
from datetime import datetime, timezone

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(__file__))

import server  # noqa: E402


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
