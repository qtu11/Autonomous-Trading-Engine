"""Unit tests for the refactored modular detectors (structure, price_action, smc, ict)."""
from __future__ import annotations
import sys
import os
import unittest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "dashboard"))

from detectors import Candle, df_to_candles
import structure as S
import price_action as PA
import ict
import smc


class TestRefactoredDetectors(unittest.TestCase):

    def setUp(self):
        # Create synthetic DataFrame with known swing high and low
        times = pd.date_range("2026-08-07 00:00", periods=30, freq="15min")
        highs = [10.0, 10.5, 12.0, 10.2, 9.8, 9.5, 8.0, 9.2, 9.6, 11.0, 11.5, 10.8, 10.2, 10.0, 10.5, 11.2, 11.8, 11.0, 10.5, 10.0,
                 10.2, 10.8, 12.5, 11.0, 10.5, 10.0, 9.8, 9.2, 9.5, 10.0]
        lows = [9.0, 9.2, 10.0, 9.0, 8.5, 8.0, 7.0, 8.0, 8.5, 9.5, 10.0, 9.2, 9.0, 8.8, 9.2, 10.0, 10.5, 9.8, 9.2, 8.8,
                9.0, 9.5, 11.0, 10.2, 9.8, 9.0, 8.5, 8.0, 8.5, 9.0]
        opens = [9.2, 9.5, 10.2, 10.0, 9.0, 8.5, 7.5, 8.2, 9.0, 10.0, 10.5, 10.2, 9.5, 9.0, 9.5, 10.2, 10.8, 10.5, 9.8, 9.2,
                 9.5, 10.0, 11.5, 10.8, 10.2, 9.5, 9.0, 8.5, 9.0, 9.5]
        closes = [9.5, 10.2, 10.1, 9.2, 8.6, 8.1, 8.0, 9.0, 9.5, 10.5, 10.2, 9.5, 9.1, 9.4, 10.1, 10.8, 10.6, 9.9, 9.3, 8.9,
                  10.0, 10.5, 12.0, 10.5, 10.0, 9.2, 8.8, 8.2, 9.2, 9.8]

        self.df = pd.DataFrame({
            "time": times,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "tick_volume": [100] * 30,
        })
        self.candles = df_to_candles(self.df)

    def test_candle_properties(self):
        c = self.candles[0]
        self.assertTrue(c.is_bullish)
        self.assertFalse(c.is_bearish)
        self.assertAlmostEqual(c.body_size, 0.3)
        self.assertAlmostEqual(c.range_size, 1.0)
        self.assertAlmostEqual(c.body_ratio, 0.3)
        self.assertAlmostEqual(c.mid, 9.5)

    def test_swing_points(self):
        swings_df = S.find_swing_points(self.df, window=2)
        self.assertIn("swing_high", swings_df.columns)
        self.assertIn("swing_low", swings_df.columns)
        
        highs, lows = S.get_swing_series(swings_df)
        self.assertTrue(len(highs) > 0)
        self.assertTrue(len(lows) > 0)
        
        labels = S.label_swing_sequence(swings_df)
        self.assertTrue(len(labels) > 0)
        self.assertEqual(labels[0]["kind"], "high")

    def test_price_action_patterns(self):
        markers = PA.scan_candlestick_patterns(self.candles)
        self.assertIsInstance(markers, list)

    def test_smc_analysis(self):
        res = smc.run_smc_analysis({"M15": self.df})
        self.assertIn("objects", res)
        self.assertIn("counts", res)

    def test_ict_analysis(self):
        res = ict.run_ict_analysis({"M15": self.df, "D1": self.df})
        self.assertIn("objects", res)
        self.assertIn("counts", res)

    def test_sniper_indicators(self):
        import signal_engines as SE
        vwap = SE._calc_vwap(self.df)
        self.assertEqual(len(vwap), len(self.df))
        
        macd, macd_sig = SE._calc_macd(self.df["close"])
        self.assertEqual(len(macd), len(self.df))
        self.assertEqual(len(macd_sig), len(self.df))
        
        adx = SE._calc_adx(self.df, 14)
        self.assertEqual(len(adx), len(self.df))
        
        res = SE.run_signal_engine("XAUUSDm", {"M15": self.df, "M5": self.df}, method="SNIPER")
        self.assertIn(res.status, ("APPROVED", "NO_TRADE"))


if __name__ == "__main__":
    unittest.main()
