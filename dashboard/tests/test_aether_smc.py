import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timezone

from aether_smc import (
    detect_pivots,
    detect_smc_structure,
    detect_luxalgo_order_blocks,
    detect_luxalgo_fvg,
    detect_ict_killzones,
    calculate_ict_ote,
    detect_ict_turtle_soup,
    calculate_sniper_flow,
    detect_price_action_patterns,
    compute_ultra_confluence_matrix,
    build_aether_flow_payload,
)


def _generate_synthetic_candles(n: int = 100, trend: str = "UP") -> pd.DataFrame:
    times = pd.date_range("2026-08-14 00:00", periods=n, freq="15min")
    base = 2400.0
    opens, highs, lows, closes, vols = [], [], [], [], []

    for i in range(n):
        step = 0.5 if trend == "UP" else -0.5
        o = base + i * step + np.sin(i / 3.0) * 2.0
        h = o + 2.0 + np.random.uniform(0.1, 0.5)
        l = o - 2.0 - np.random.uniform(0.1, 0.5)
        c = o + step + np.random.uniform(-0.5, 0.5)
        opens.append(o)
        highs.append(h)
        lows.append(l)
        closes.append(c)
        vols.append(100.0 + i * 2.0)

    return pd.DataFrame({
        "time": times.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": vols,
    })


class TestAetherEngine:
    def test_pivots_detection_with_recent_swings(self):
        df = _generate_synthetic_candles(60, "UP")
        highs = df["high"].values
        lows = df["low"].values
        sh, sl = detect_pivots(highs, lows, length=5)
        assert len(sh) > 0
        assert len(sl) > 0
        # Đảm bảo index sắp xếp theo thứ tự tăng dần
        assert all(sh[i][0] < sh[i + 1][0] for i in range(len(sh) - 1))

    def test_ote_downtrend_calculation(self):
        df = _generate_synthetic_candles(60, "DOWN")
        # Downtrend: swing_high = 2450, swing_low = 2400
        ote_bear = calculate_ict_ote(df, 2450.0, 2400.0, trend=-1)
        assert ote_bear["direction"] == "BEARISH"
        # OTE Sell zone phải nằm phía trên 50% equilibrium (từ 2430 trở lên)
        assert ote_bear["ote_sweet_spot"] > ote_bear["equilibrium_50"]
        assert ote_bear["ote_sweet_spot"] == pytest.approx(2400.0 + 50.0 * 0.705, 0.1)

    def test_order_blocks_and_breakers(self):
        df = _generate_synthetic_candles(80, "UP")
        obs, breakers = detect_luxalgo_order_blocks(df, pivot_len=5)
        assert isinstance(obs, list)
        assert isinstance(breakers, list)
        for ob in obs:
            assert "top" in ob and "bottom" in ob
            assert ob["top"] >= ob["bottom"]

    def test_killzones_window(self):
        # 14:00 UTC = 840 min -> London & NY AM overlap / Silver Bullet
        dt = datetime(2026, 8, 14, 14, 15, tzinfo=timezone.utc)
        kz = detect_ict_killzones(dt)
        assert kz["is_ny_am"] is True
        assert kz["is_silver_bullet"] is True

    def test_master_aether_flow_payload(self):
        df = _generate_synthetic_candles(100, "UP")
        payload = build_aether_flow_payload("XAUUSD", df)
        assert payload["symbol"] == "XAUUSD"
        assert "swings" in payload
        assert "order_blocks" in payload
        assert "fvgs" in payload
        assert "confluence" in payload
        assert 0 <= payload["confluence"]["score"] <= 100
