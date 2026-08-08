"""Unit tests for detectors.py module."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / "dashboard"))

from detectors import (
    Candle,
    PDArray,
    PDArrayDirection,
    PDArrayType,
    calculate_ote_zone,
    classify_pd_array_zone,
    classify_trend_structure,
    detect_fvg,
    detect_order_blocks,
    detect_rejection_blocks,
    df_to_candles,
    find_swing_points,
    get_asian_range,
    get_killzone_status,
    get_last_swing_points,
    get_premium_discount_zone,
    is_price_in_ote,
)


class TestDetectors(unittest.TestCase):

    def setUp(self):
        # Create synthetic DataFrame with known swing high and low
        times = pd.date_range("2026-08-07 00:00", periods=20, freq="15min")
        highs = [10.0, 10.5, 12.0, 10.2, 9.8, 9.5, 8.0, 9.2, 9.6, 11.0, 11.5, 10.8, 10.2, 10.0, 10.5, 11.2, 11.8, 11.0, 10.5, 10.0]
        lows = [9.0, 9.2, 10.0, 9.0, 8.5, 8.0, 7.0, 8.0, 8.5, 9.5, 10.0, 9.2, 9.0, 8.8, 9.2, 10.0, 10.5, 9.8, 9.2, 8.8]
        opens = [9.2, 9.5, 10.2, 10.0, 9.0, 8.5, 7.5, 8.2, 9.0, 10.0, 10.5, 10.2, 9.5, 9.0, 9.5, 10.2, 10.8, 10.5, 9.8, 9.2]
        closes = [9.5, 10.2, 10.1, 9.2, 8.6, 8.1, 8.0, 9.0, 9.5, 10.5, 10.2, 9.5, 9.1, 9.4, 10.1, 10.8, 10.6, 9.9, 9.3, 8.9]

        self.df = pd.DataFrame({
            "time": times,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "tick_volume": [100] * 20,
        })
        self.candles = df_to_candles(self.df)

    def test_candle_properties(self):
        c = Candle(index=0, time=pd.Timestamp.now(), open=100.0, high=105.0, low=95.0, close=102.0)
        self.assertTrue(c.is_bullish)
        self.assertFalse(c.is_bearish)
        self.assertEqual(c.body_size, 2.0)
        self.assertEqual(c.range_size, 10.0)
        self.assertEqual(c.body_ratio, 0.2)

    def test_find_swing_points(self):
        swings_df = find_swing_points(self.df, window=2)
        self.assertIn("swing_high", swings_df.columns)
        self.assertIn("swing_low", swings_df.columns)
        swings = get_last_swing_points(swings_df, n=3)
        self.assertTrue(len(swings["swing_highs"]) > 0)
        self.assertTrue(len(swings["swing_lows"]) > 0)

    def test_detect_fvg(self):
        fvgs = detect_fvg(self.candles)
        self.assertIsInstance(fvgs, list)
        for f in fvgs:
            self.assertIn(f.direction, (PDArrayDirection.BULLISH, PDArrayDirection.BEARISH))
            self.assertIsNotNone(f.ce)

    def test_ote_zone_calculation(self):
        ote = calculate_ote_zone(swing_low=100.0, swing_high=200.0, direction="BUY")
        self.assertAlmostEqual(ote["zone_top"], 138.2)
        self.assertAlmostEqual(ote["zone_bottom"], 121.0)
        self.assertTrue(is_price_in_ote(130.0, ote))
        self.assertFalse(is_price_in_ote(150.0, ote))

    def test_premium_discount_classification(self):
        pd_zone = get_premium_discount_zone(swing_low=100.0, swing_high=200.0)
        self.assertEqual(pd_zone["fib_50"], 150.0)

        ob_discount = PDArray(
            type=PDArrayType.ORDER_BLOCK,
            direction=PDArrayDirection.BULLISH,
            top=140.0,
            bottom=130.0,
            formed_at_index=1,
            formed_at_time=pd.Timestamp.now(),
        )
        self.assertEqual(classify_pd_array_zone(ob_discount, pd_zone), "DISCOUNT")

        ob_premium = PDArray(
            type=PDArrayType.ORDER_BLOCK,
            direction=PDArrayDirection.BEARISH,
            top=180.0,
            bottom=160.0,
            formed_at_index=2,
            formed_at_time=pd.Timestamp.now(),
        )
        self.assertEqual(classify_pd_array_zone(ob_premium, pd_zone), "PREMIUM")

    def test_killzone_status(self):
        t = pd.Timestamp("2026-08-07 14:30:00")
        kz = get_killzone_status(t, broker_utc_offset_hours=2.0)
        self.assertIn("is_any_killzone", kz)
        self.assertIn("vn_time", kz)


if __name__ == "__main__":
    unittest.main()
