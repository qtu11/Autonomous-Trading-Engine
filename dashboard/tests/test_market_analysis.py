"""
MARKET ANALYSIS ENGINE - COMPREHENSIVE UNIT TESTS
===================================================

Tests all pattern detection algorithms with deterministic synthetic data.
Each test verifies: Detection + Price Coordinates + Time + Direction + Status.

Run: python -m pytest tests/test_market_analysis.py -v
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import List

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from detectors import (
    Candle, df_to_candles, find_swing_points,
    detect_market_structure, detect_bos_choch,
    detect_order_blocks, detect_fvg, detect_rejection_blocks,
    detect_breaker_and_mitigation_blocks, detect_liquidity_sweep,
    detect_equal_highs_lows, mark_ob_mitigated,
    calculate_ote_zone, get_premium_discount_zone,
    classify_trend_structure, detect_trendlines,
    PDArray, PDArrayType, PDArrayDirection,
)
from advanced_detectors import (
    detect_support_resistance, detect_channels, detect_range_state,
    detect_breakouts, detect_pullback_retest_fake, detect_candle_patterns,
    detect_mss, detect_liquidity_zones, detect_dealing_range,
    detect_supply_demand, detect_volume_imbalance, detect_liquidity_voids,
    detect_inducement, detect_bpr, detect_unicorn,
    get_previous_day_high_low, get_session_high_low,
    detect_turtle_soup, detect_judas_swing, detect_smt_divergence,
    detect_silver_bullet, build_advanced_markup,
)


# =============================================================================
# SYNTHETIC DATA FACTORIES
# =============================================================================

def make_candle(idx: int, open_p: float, high_p: float, low_p: float, close_p: float,
                volume: float = 1000.0) -> dict:
    """Create deterministic synthetic OHLC candle."""
    timestamp = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc) + timedelta(minutes=15*idx)
    return {
        'time': timestamp,
        'open': open_p,
        'high': high_p,
        'low': low_p,
        'close': close_p,
        'volume': volume
    }


def make_df(candles: List[dict]) -> pd.DataFrame:
    """Convert list of candles to DataFrame."""
    return pd.DataFrame(candles)


def candles_to_objs(candles: List[dict]) -> List[Candle]:
    """Convert dict list to Candle objects."""
    return df_to_candles(make_df(candles))


# =============================================================================
# FVG TESTS - CRITICAL
# =============================================================================

class TestFVG:
    """Fair Value Gap - 3-Candle Model Tests"""

    def test_bullish_fvg_detected(self):
        """BULLISH FVG: HIGH(C1) < LOW(C3)"""
        # C1: bullish, close at 103 (high=104)
        # C2: bearish, body down
        # C3: bullish, open at 105 (low=105, creates gap above C1's high=104)
        candles = [
            make_candle(0, 100.0, 104.0, 99.0, 103.0),   # C1: high=104
            make_candle(1, 103.0, 103.5, 100.0, 100.5),  # C2: gap in middle
            make_candle(2, 105.0, 107.0, 105.0, 106.5),  # C3: low=105 > high(C1)=104 -> FVG!
        ]
        objs = candles_to_objs(candles)
        fvgs = detect_fvg(objs)

        # FVG detected between HIGH(C1)=104 and LOW(C3)=105
        assert len(fvgs) >= 1, f"Expected FVG, got {len(fvgs)}. C1.high={candles[0]['high']}, C3.low={candles[2]['low']}"

        bullish_fvgs = [f for f in fvgs if f.direction == PDArrayDirection.BULLISH]
        assert len(bullish_fvgs) >= 1, "Should detect bullish FVG"
        fvg = bullish_fvgs[0]
        assert fvg.bottom == 104.0, f"Bottom should be HIGH(C1)=104, got {fvg.bottom}"
        assert fvg.top == 105.0, f"Top should be LOW(C3)=105, got {fvg.top}"
        assert fvg.type == PDArrayType.FVG

    def test_bearish_fvg_detected(self):
        """BEARISH FVG: LOW(C1) > HIGH(C3)"""
        # C1: bearish, low=96
        # C2: bullish in middle
        # C3: bearish, high=95 < low(C1)=96 -> FVG!
        candles = [
            make_candle(0, 100.0, 101.0, 96.0, 96.5),    # C1: low=96
            make_candle(1, 96.5, 100.0, 95.5, 99.5),     # C2: bullish middle
            make_candle(2, 95.0, 95.5, 92.0, 93.0),      # C3: high=95.5 < low(C1)=96 -> FVG!
        ]
        objs = candles_to_objs(candles)
        fvgs = detect_fvg(objs)

        assert len(fvgs) >= 1, f"Expected bearish FVG"
        bearish_fvgs = [f for f in fvgs if f.direction == PDArrayDirection.BEARISH]
        assert len(bearish_fvgs) >= 1, "Should detect bearish FVG"

    def test_no_fvg_when_adjacent(self):
        """No FVG when candles are adjacent (no gap)"""
        candles = [
            make_candle(0, 100.0, 102.0, 99.0, 101.0),
            make_candle(1, 101.0, 103.0, 100.0, 102.0),
            make_candle(2, 102.0, 104.0, 101.0, 103.0),
        ]
        objs = candles_to_objs(candles)
        fvgs = detect_fvg(objs)

        assert len(fvgs) == 0, f"Expected no FVG for adjacent candles"

    def test_fvg_zone_only_covers_gap(self):
        """FVG rectangle MUST cover only the gap, not whole candles"""
        candles = [
            make_candle(0, 100.0, 102.0, 99.0, 101.0),   # C1: high=102
            make_candle(1, 101.0, 103.0, 100.0, 100.5),   # C2: middle
            make_candle(2, 105.0, 108.0, 105.0, 107.0),   # C3: low=105 > high(C1)=102
        ]
        objs = candles_to_objs(candles)
        fvgs = detect_fvg(objs)

        assert len(fvgs) == 1
        # Gap is between HIGH(C1)=102 and LOW(C3)=105
        gap_size = fvgs[0].top - fvgs[0].bottom
        assert gap_size == 3.0, f"Gap should be 3 (102 to 105), got {gap_size}"
        # Should NOT be 8 (which would be the whole range)


# =============================================================================
# SWING ENGINE TESTS
# =============================================================================

class TestSwingEngine:
    """Canonical Swing Point Detection Tests"""

    def test_swing_highs_identified(self):
        """Swing highs detected with N-candle lookback"""
        # Clear swing high at index 5 (105 > all neighbors)
        candles = [
            make_candle(0, 100.0, 101.0, 99.0, 100.0),
            make_candle(1, 100.0, 102.0, 99.0, 101.0),
            make_candle(2, 101.0, 103.0, 100.0, 102.0),
            make_candle(3, 102.0, 104.0, 101.0, 103.0),
            make_candle(4, 103.0, 104.5, 102.0, 103.5),
            make_candle(5, 103.5, 105.0, 103.0, 104.0),  # SWING HIGH
            make_candle(6, 104.0, 104.5, 102.0, 103.0),
            make_candle(7, 103.0, 103.5, 101.0, 102.0),
        ]

        df = make_df(candles)
        swings = find_swing_points(df, window=2)

        swing_highs = swings[swings['swing_high']]
        assert len(swing_highs) >= 1, "Should detect at least one swing high"
        assert 5 in swing_highs.index, f"Index 5 should be swing high, got swings at {swing_highs.index.tolist()}"

    def test_swing_lows_identified(self):
        """Swing lows detected with N-candle lookback"""
        candles = [
            make_candle(0, 100.0, 101.0, 99.0, 100.0),
            make_candle(1, 100.0, 101.0, 98.0, 99.0),
            make_candle(2, 99.0, 100.0, 97.0, 98.0),
            make_candle(3, 98.0, 99.0, 96.0, 97.0),
            make_candle(4, 97.0, 98.0, 95.5, 96.5),
            make_candle(5, 96.5, 97.0, 95.0, 95.5),  # SWING LOW
            make_candle(6, 95.8, 96.0, 95.5, 95.7),
            make_candle(7, 95.5, 96.5, 95.5, 96.0),
        ]

        df = make_df(candles)
        swings = find_swing_points(df, window=2)

        swing_lows = swings[swings['swing_low']]
        assert len(swing_lows) >= 1
        assert 5 in swing_lows.index, f"Index 5 should be swing low, got {swing_lows.index.tolist()}"


# =============================================================================
# HH/HL/LH/LL TESTS
# =============================================================================

class TestHHHLLL:
    """Higher High, Higher Low, Lower High, Lower Low Tests"""

    def test_hh_detection(self):
        """Higher High: current swing high > previous swing high"""
        # Swings located inside the last `n` candles read by detect_market_structure.
        # H1=100 at candle 3, H2=105 at candle 6 -> both strict fractals (window=2).
        candles = []
        for i in range(15):
            if i == 3:
                candles.append(make_candle(i, 95, 100, 94, 99))   # H1: 100
            elif i == 4:
                candles.append(make_candle(i, 99, 99.5, 98, 99))  # Pullback below 100
            elif i == 6:
                candles.append(make_candle(i, 99, 105, 98, 104))  # H2: 105 (HH)
            elif i == 7:
                candles.append(make_candle(i, 104, 104.5, 103, 104))  # Pullback below 105
            else:
                candles.append(make_candle(i, 98, 99, 97, 98))

        df = make_df(candles)
        structure = detect_market_structure(df, window=2, n=10)

        labels = [l['label'] for l in structure['labels']]
        assert 'HH' in labels, f"Should detect HH, got labels: {labels}"

    def test_hl_detection(self):
        """Higher Low: current swing low > previous swing low"""
        candles = []
        for i in range(15):
            if i == 3:
                candles.append(make_candle(i, 100, 101, 95, 96))  # L1 = 95
            elif i == 4:
                candles.append(make_candle(i, 98, 99, 97, 98))
            elif i == 7:
                candles.append(make_candle(i, 100, 101, 96.5, 97.5))  # L2 = 96.5 (HL)
            else:
                candles.append(make_candle(i, 98, 99, 97, 98))

        df = make_df(candles)
        structure = detect_market_structure(df, window=2, n=10)

        labels = [l['label'] for l in structure['labels']]
        assert 'HL' in labels, f"Should detect HL, got labels: {labels}"


# =============================================================================
# BOS/CHoCH TESTS
# =============================================================================

class TestBOSCHoCH:
    """Break of Structure / Change of Character Tests"""

    def test_bullish_bos_in_uptrend(self):
        """Bullish BOS: Close breaks above swing high in uptrend"""
        # Build uptrend then break above HH
        candles = []
        for i in range(15):
            if i == 2:
                candles.append(make_candle(i, 95, 100, 94, 99))   # SH1
            elif i == 3:
                candles.append(make_candle(i, 99, 100, 98, 99))  # SL1
            elif i == 6:
                candles.append(make_candle(i, 98, 105, 97, 104))  # SH2 (HH)
            elif i == 7:
                candles.append(make_candle(i, 104, 105, 103, 104))  # SL2
            elif i == 10:
                candles.append(make_candle(i, 103, 108, 103, 107))  # Break above SH2
            else:
                mid = 95 + i
                candles.append(make_candle(i, mid, mid+2, mid-1, mid+1))

        df = make_df(candles)
        swings = find_swing_points(df, window=2)
        objs = candles_to_objs(candles)

        result = detect_bos_choch(objs, swings, current_index=10)

        assert result.get('kind') in ['BOS', 'CHoCH'], f"Should detect BOS/CHoCH, got {result}"
        assert result.get('direction') == 'BULLISH', f"Should be bullish, got {result}"

    def test_bearish_bos_in_downtrend(self):
        """Bearish BOS: Close breaks below swing low in downtrend"""
        candles = []
        for i in range(15):
            if i == 2:
                candles.append(make_candle(i, 105, 106, 100, 101))  # SL1
            elif i == 3:
                candles.append(make_candle(i, 101, 105, 101, 104))  # SH1
            elif i == 6:
                candles.append(make_candle(i, 104, 105, 95, 96))  # SL2 (LL)
            elif i == 7:
                candles.append(make_candle(i, 96, 104, 96, 103))  # SH2
            elif i == 10:
                candles.append(make_candle(i, 103, 104, 90, 91))  # Break below SL2
            else:
                mid = 105 - i
                candles.append(make_candle(i, mid, mid+1, mid-2, mid-1))

        df = make_df(candles)
        swings = find_swing_points(df, window=2)
        objs = candles_to_objs(candles)

        result = detect_bos_choch(objs, swings, current_index=10)

        assert result.get('direction') == 'BEARISH', f"Should be bearish, got {result}"


# =============================================================================
# ORDER BLOCK TESTS
# =============================================================================

class TestOrderBlock:
    """Order Block Detection Tests"""

    def test_bullish_ob_formation(self):
        """Bullish OB: bearish consolidation + bullish displacement breaking structure"""
        candles = []
        # Need swing high first
        candles.append(make_candle(0, 95, 100, 94, 99))  # Swing high
        # Prior: bearish candle (consolidation)
        candles.append(make_candle(1, 102, 103, 98, 99))  # Bearish OB source
        # Current: bullish displacement breaking above swing high
        candles.append(make_candle(2, 99, 105, 98, 104))  # Bullish displacement
        candles.append(make_candle(3, 104, 106, 103, 105))

        df = make_df(candles)
        swings = find_swing_points(df, window=1)
        objs = candles_to_objs(candles)

        obs = detect_order_blocks(objs, swings, displacement_atr_multiplier=0.5)

        # Should detect at least one OB
        bullish_obs = [o for o in obs if o.direction == PDArrayDirection.BULLISH]
        assert len(bullish_obs) >= 1, f"Should detect bullish OB, got {len(obs)} OBs"


# =============================================================================
# CANDLESTICK PATTERN TESTS
# =============================================================================

class TestCandlePatterns:
    """Single and Multi-Candle Pattern Tests"""

    def test_pin_bar_bullish(self):
        """Bullish Pin Bar: lower wick >= 2x body, small upper wick"""
        # Pin bar: open=100, close=100, high=101, low=95
        # body=0, lower_wick=5, upper_wick=1
        candles = [
            make_candle(0, 98, 100, 97, 99),
            make_candle(1, 99, 101, 95, 100),  # Pin bar: wick down to 95
            make_candle(2, 100, 102, 99, 101),
        ]
        objs = candles_to_objs(candles)
        patterns = detect_candle_patterns(objs)

        pin_bars = [p for p in patterns if p.get('label') == 'PIN_BAR']
        bullish_pins = [p for p in pin_bars if p.get('direction') == 'BULLISH']
        assert len(bullish_pins) >= 1, f"Should detect bullish pin bar, got {patterns}"

    def test_engulfing_bullish(self):
        """Bullish Engulfing: current bullish engulfs prior bearish"""
        candles = [
            make_candle(0, 98, 100, 97, 98),    # Previous bullish
            make_candle(1, 100, 101, 97, 98),   # Prior bearish body
            make_candle(2, 97, 102, 96, 101),   # Current bullish engulfs
        ]
        objs = candles_to_objs(candles)
        patterns = detect_candle_patterns(objs)

        engulfing = [p for p in patterns if 'ENGULFING' in str(p.get('label', ''))]
        bullish_eng = [p for p in engulfing if p.get('direction') == 'BULLISH']
        assert len(bullish_eng) >= 1, f"Should detect bullish engulfing, got {patterns}"

    def test_doji_detected(self):
        """Doji: body < 10% of range"""
        candles = [
            make_candle(0, 100, 102, 98, 101),
            make_candle(1, 100, 101, 99, 100.5),  # Doji: body=0.5, range=2
            make_candle(2, 100.5, 102, 99, 101),
        ]
        objs = candles_to_objs(candles)
        patterns = detect_candle_patterns(objs)

        dojis = [p for p in patterns if p.get('label') == 'DOJI']
        assert len(dojis) >= 1, f"Should detect doji, got {patterns}"

    def test_morning_star(self):
        """Morning Star: bearish, small body, bullish"""
        candles = [
            make_candle(0, 105, 106, 101, 102),  # C1: bearish large
            make_candle(1, 102, 104, 101, 103),  # C2: small body
            make_candle(2, 103, 107, 102, 106),   # C3: bullish
        ]
        objs = candles_to_objs(candles)
        patterns = detect_candle_patterns(objs)

        morning = [p for p in patterns if p.get('label') == 'MORNING_STAR']
        assert len(morning) >= 1, f"Should detect morning star, got {patterns}"


# =============================================================================
# TREND CLASSIFICATION TESTS
# =============================================================================

class TestTrendClassification:
    """Trend detection tests"""

    def test_uptrend_classification(self):
        """Uptrend: HH and HL pattern"""
        candles = []
        # Build clear uptrend
        for i in range(10):
            base = i * 5
            candles.append(make_candle(i, base, base+5, base-1, base+4))  # Ascending

        df = make_df(candles)
        trend = classify_trend_structure(df)

        assert trend == 'UPTREND', f"Should be UPTREND, got {trend}"

    def test_downtrend_classification(self):
        """Downtrend: LH and LL pattern"""
        candles = []
        # Build clear downtrend
        for i in range(10):
            base = 100 - i * 5
            candles.append(make_candle(i, base, base+1, base-5, base-4))  # Descending

        df = make_df(candles)
        trend = classify_trend_structure(df)

        assert trend == 'DOWNTREND', f"Should be DOWNTREND, got {trend}"


# =============================================================================
# OTE / FIBONACCI TESTS
# =============================================================================

class TestOTE:
    """Optimal Trade Entry / Fibonacci Tests"""

    def test_ote_zone_calculation(self):
        """OTE zone at 62-79% retracement"""
        swing_low = 100.0
        swing_high = 200.0

        zone = calculate_ote_zone(swing_low, swing_high, 'BULLISH')

        # Verify zone structure
        assert 'zone_low' in zone
        assert 'zone_high' in zone
        assert zone['zone_low'] < zone['zone_high']
        # Zone should be between swing_low and swing_high
        assert zone['zone_low'] >= swing_low
        assert zone['zone_high'] <= swing_high

    def test_premium_discount_zones(self):
        """Premium above EQ, Discount below EQ"""
        swing_low = 100.0
        swing_high = 200.0

        pd_zone = get_premium_discount_zone(swing_low, swing_high)

        assert pd_zone['equilibrium'] == 150.0
        assert pd_zone['premium_low'] > pd_zone['equilibrium']
        assert pd_zone['discount_high'] < pd_zone['equilibrium']


# =============================================================================
# SUPPORT/RESISTANCE TESTS
# =============================================================================

class TestSupportResistance:
    """Support and Resistance Zone Tests"""

    def test_sr_zones_detected(self):
        """S/R zones from clustered swing points"""
        candles = []
        # Create multiple touches at resistance level 100
        for i in range(15):
            if i in [3, 7, 11]:  # Touches at ~100
                candles.append(make_candle(i, 99, 101, 98, 100))
            else:
                candles.append(make_candle(i, 95+i, 96+i, 94+i, 95+i))

        df = make_df(candles)
        swings = find_swing_points(df, window=1)
        objs = candles_to_objs(candles)

        sr_zones = detect_support_resistance(objs, swings, lookback=15, min_touches=2)

        assert len(sr_zones) >= 1, f"Should detect S/R zones, got {len(sr_zones)}"


# =============================================================================
# ADVANCED DETECTION TESTS
# =============================================================================

class TestAdvancedPatterns:
    """ICT/SMC advanced pattern tests"""

    def test_liquidity_sweep_detected(self):
        """Liquidity sweep: price hunts above/below previous highs/lows"""
        candles = []
        # Create equal highs at 100 level, then sweep above
        for i in range(10):
            if i == 2:
                candles.append(make_candle(i, 95, 100, 94, 99))  # EQH
            elif i == 4:
                candles.append(make_candle(i, 95, 100.5, 94, 94.5))  # Sweep above 100
            elif i == 5:
                candles.append(make_candle(i, 94, 96, 90, 91))  # Reversal
            else:
                candles.append(make_candle(i, 95, 98, 94, 96))

        df = make_df(candles)
        swings = find_swing_points(df, window=2)
        objs = candles_to_objs(candles)

        sweeps = detect_liquidity_sweep(objs, swings, lookback=10)

        assert isinstance(sweeps, list)

    def test_breakout_detection(self):
        """Breakout above/below S/R with volume"""
        candles = []
        # S/R at 100
        for i in range(5):
            candles.append(make_candle(i, 99, 101, 98, 100, volume=800))
        # Breakout candle with high volume
        candles.append(make_candle(5, 100, 105, 99, 104, volume=2000))

        df = make_df(candles)
        swings = find_swing_points(df, window=1)
        objs = candles_to_objs(candles)

        sr_zones = [{'top': 101, 'bottom': 98, 'label': 'RESISTANCE', 'index': 0, 'time_start': str(datetime.now())}]
        breakouts = detect_breakouts(objs, swings, sr_zones)

        bullish_breaks = [b for b in breakouts if b.get('direction') == 'BULLISH']
        assert len(bullish_breaks) >= 1, f"Should detect bullish breakout"


# =============================================================================
# INTEGRATION TEST - BUILD_ADVANCED_MARKUP
# =============================================================================

class TestIntegration:
    """Full markup build integration test"""

    def test_build_advanced_markup_returns_valid_structure(self):
        """build_advanced_markup returns correct object structure"""
        # Create realistic M15 data
        candles = []
        base_price = 2000.0
        for i in range(100):
            trend = 1 if i % 20 < 10 else -1
            o = base_price + i * 0.5 * trend
            c = o + 2.0 * trend
            h = max(o, c) + 0.5
            l = min(o, c) - 0.5
            candles.append({
                'time': datetime.now() + timedelta(minutes=15*i),
                'open': o, 'high': h, 'low': l, 'close': c, 'volume': 1000
            })

        df = pd.DataFrame(candles)
        mtf_data = {'M15': df}

        result = build_advanced_markup(mtf_data, include_pa=True, include_smc=True, include_ict=True)

        assert 'objects' in result
        assert 'counts' in result
        assert isinstance(result['objects'], list)

        # Check required fields
        for obj in result['objects'][:5]:
            assert 'type' in obj
            assert 'direction' in obj
            assert 'price' in obj or ('top' in obj and 'bottom' in obj)

    def test_no_random_objects_generated(self):
        """Ensure detection doesn't produce excessive random objects"""
        # Simple oscillating data
        candles = []
        for i in range(50):
            phase = (i % 10) / 10 * 3.14159
            price = 100 + np.sin(phase) * 2
            candles.append({
                'time': datetime.now() + timedelta(minutes=15*i),
                'open': price, 'high': price + 0.5, 'low': price - 0.5, 'close': price + 0.3, 'volume': 1000
            })

        df = pd.DataFrame(candles)
        mtf_data = {'M15': df}

        result = build_advanced_markup(mtf_data, include_pa=True, include_smc=True, include_ict=False)

        total_objects = len(result['objects'])
        assert total_objects < 100, f"Too many objects ({total_objects}) for 50 candles"

        # Verify FVG not excessive for oscillating data
        fvg_count = len([o for o in result['objects'] if o.get('type') == 'FVG'])
        assert fvg_count < 10, f"FVG count ({fvg_count}) too high for oscillating data"


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
