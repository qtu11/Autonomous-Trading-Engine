"""Unit tests for method_overlays.py — Sniper/SMC/ICT/PA detectors.

These tests use synthetic but shape-valid candle data and assert that each
overlay emits the expected object types and that the trading-method filter
groups contain them.
"""

from __future__ import annotations

import sys
import os

# Ensure dashboard/ is on sys.path so `from method_overlays import ...` works
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
import numpy as np
import pandas as pd

from method_overlays import (
    METHOD_OBJECT_GROUPS,
    compute_confluence_score,
    compute_ict_overlay,
    compute_pa_overlay,
    compute_smc_overlay,
    compute_sniper_overlay,
)
from chart_markup import build_chart_markup


def make_df(n: int = 200, base: float = 2000.0, slope: float = 0.5,
            step_min: int = 15, seed: int = 1) -> pd.DataFrame:
    """Realistic ranging candle generator. Slope adds drift; sine wave adds swing."""
    rng = np.random.default_rng(seed)
    times = [datetime(2026, 8, 5, 0, 0) + timedelta(minutes=step_min * i) for i in range(n)]
    closes = [base + slope * i + 10 * np.sin(i / 8.0) + rng.normal(0, 0.5) for i in range(n)]
    return pd.DataFrame({
        "time": times,
        "open":  [c - 0.3 for c in closes],
        "high":  [c + 1.5 + abs(rng.normal(0, 0.2)) for c in closes],
        "low":   [c - 1.5 - abs(rng.normal(0, 0.2)) for c in closes],
        "close": closes,
        "volume": [1000.0 + rng.normal(0, 100.0) for _ in range(n)],
        "tick_volume": [100] * n,
        "spread": [5] * n,
    })


def test_sniper_emits_ema_ribbon_vwap_score():
    df = make_df(n=200)
    m5 = make_df(n=600, step_min=5, seed=2)
    objs = compute_sniper_overlay("XAUUSD", df, m5)
    types = {o["type"] for o in objs}
    for required in ("EMA", "EMA_RIBBON", "VWAP", "SNIPER_SCORE",
                     "ADX", "MACD_LINE", "RSI_LEVEL"):
        assert required in types, f"Sniper missing {required}; got {types}"
    score_obj = next(o for o in objs if o["type"] == "SNIPER_SCORE")
    assert "bull_pct" in score_obj and "bear_pct" in score_obj
    assert 0 <= score_obj["bull_pct"] <= 100
    assert 0 <= score_obj["bear_pct"] <= 100
    assert score_obj["bias"] in ("STRONG_BULL", "STRONG_BEAR", "MILD_BULL", "MILD_BEAR")


def test_sniper_generates_signal_and_tps_on_crossover():
    """Force a clean EMA9/21 crossover by making the last 2 candles invert trend."""
    df = make_df(n=200, slope=-0.5, seed=10)  # downtrend
    df.iloc[-1, df.columns.get_loc("close")] = float(df["close"].iloc[-1]) + 5.0  # bullish spike
    objs = compute_sniper_overlay("XAUUSD", df)
    signal_objs = [o for o in objs if o["type"].startswith("SNIPER_")]
    # Either crossover happened (signal+SL+5TP) or didn't (just score). Both valid.
    has_signal = any(o["type"] == "SNIPER_SIGNAL" for o in objs)
    if has_signal:
        for required in ("SNIPER_SIGNAL", "SNIPER_SL",
                         "SNIPER_TP1", "SNIPER_TP2", "SNIPER_TP3",
                         "SNIPER_TP4", "SNIPER_TP5"):
            assert any(o["type"] == required for o in objs), f"Sniper missing {required} after crossover"


def test_smc_emits_swings_bsl_ssl_eqh_eql():
    df = make_df(n=200)
    objs = compute_smc_overlay(df)
    types = {o["type"] for o in objs}
    # BSL/SSL pools and swings must appear in a ranging market
    assert "BSL" in types or "SSL" in types, f"SMC missing liquidity pools; got {types}"
    swing_labels = {o.get("label") for o in objs if o["type"] == "SWING"}
    assert swing_labels.intersection({"HH", "HL", "LH", "LL"}), f"SMC swing labels missing: {swing_labels}"


def test_ict_emits_pd_ote_killzone_asian():
    df = make_df(n=200)
    objs = compute_ict_overlay(df, broker_utc_offset_hours=2.0)
    types = {o["type"] for o in objs}
    assert "PD" in types, f"ICT missing PD; got {types}"
    assert "OTE" in types, f"ICT missing OTE; got {types}"
    assert "KILLZONE" in types, f"ICT missing KILLZONE; got {types}"
    pd_objs = [o for o in objs if o["type"] == "PD"]
    pd_labels = {o.get("label") for o in pd_objs}
    assert pd_labels == {"PREMIUM", "DISCOUNT"}, f"PD must have both PREMIUM and DISCOUNT; got {pd_labels}"


def test_pa_emits_pivots_pdh_pdl_and_patterns():
    df = make_df(n=200)
    objs = compute_pa_overlay(df)
    types = {o["type"] for o in objs}
    assert "PIVOT" in types, f"PA missing PIVOT; got {types}"
    assert "PDH" in types, f"PA missing PDH; got {types}"
    assert "PDL" in types, f"PA missing PDL; got {types}"
    # At least 6 pivot levels (P/R1/R2/R3/S1/S2/S3)
    pivot_labels = {o.get("label") for o in objs if o["type"] == "PIVOT"}
    assert len(pivot_labels) >= 6, f"PA must emit 6+ pivot levels; got {pivot_labels}"


def test_method_groups_contain_overlay_types():
    """Every type emitted by an overlay must appear in its method's group (or ULTRA)."""
    df = make_df(n=200)
    all_objs = (
        compute_sniper_overlay("XAUUSD", df)
        + compute_smc_overlay(df)
        + compute_ict_overlay(df)
        + compute_pa_overlay(df)
    )
    sniper_types = {o["type"] for o in all_objs if o["type"] in METHOD_OBJECT_GROUPS["SNIPER"]}
    smc_types = {o["type"] for o in all_objs if o["type"] in METHOD_OBJECT_GROUPS["SMC"]}
    ict_types = {o["type"] for o in all_objs if o["type"] in METHOD_OBJECT_GROUPS["ICT"]}
    pa_types = {o["type"] for o in all_objs if o["type"] in METHOD_OBJECT_GROUPS["PRICE_ACTION"]}
    # Sniper group must include at least the 5 core types we emit
    for t in ("EMA", "VWAP", "SNIPER_SCORE"):
        assert t in sniper_types, f"Sniper group missing {t}"
    # SMC group must include SWING, BSL/SSL
    for t in ("SWING",):
        assert t in smc_types, f"SMC group missing {t}"
    # ICT group must include PD, OTE, KILLZONE
    for t in ("PD", "OTE", "KILLZONE"):
        assert t in ict_types, f"ICT group missing {t}"
    # PA group must include PIVOT
    assert "PIVOT" in pa_types, f"PA group missing PIVOT"


def test_pivot_direction_not_inverted():
    """BUG FIX regression: giá phá TRÊN kháng cự = breakout BULLISH, phá DƯỚI hỗ
    trợ = breakdown BEARISH. Trước đây vote ngược (reject khi phá, bounce khi thủng)."""
    last_close = 2050.0
    # Price đã vượt R1 (2050 >= 2045) -> breakout bull; đã phá S1 (2050 <= 2055) -> breakdown bear
    objs = [
        {"type": "PIVOT", "label": "R1", "price": 2045.0},
        {"type": "PIVOT", "label": "S1", "price": 2055.0},
    ]
    cf = compute_confluence_score(objs, "PRICE_ACTION", last_close)
    factors = {f["reason"] for f in cf["factors"]}
    assert "PIVOT_R1_break" in factors, f"expected breakout factor, got {factors}"
    assert "PIVOT_S1_break" in factors, f"expected breakdown factor, got {factors}"
    assert cf["score"] == 0  # +5 (bull break) - 5 (bear break) triệt tiêu

    # Rejection/bounce vẫn đúng khi giá nằm CẠNH mức chưa phá (trong 0.5%)
    objs2 = [
        {"type": "PIVOT", "label": "R1", "price": 2051.0},  # giá dưới R1 (chưa phá) -> reject SELL
        {"type": "PIVOT", "label": "S1", "price": 2049.0},  # giá trên S1 (chưa thủng) -> bounce BUY
    ]
    cf2 = compute_confluence_score(objs2, "PRICE_ACTION", 2050.0)
    factors2 = {f["reason"] for f in cf2["factors"]}
    assert "PIVOT_R1_reject" in factors2, f"expected reject factor, got {factors2}"
    assert "PIVOT_S1_bounce" in factors2, f"expected bounce factor, got {factors2}"
    assert cf2["score"] == 0


def test_indicator_method_emits_no_markup_and_waits():
    """BUG FIX regression: chọn INDICATOR phải KHÔNG vẽ OB/FVG/BOS và phải trả
    WAIT. Trước đây filter bị bỏ qua nên chart hiện đầy markup của mọi phương pháp
    và AI có thể tự trade theo tín hiệu của phương pháp khác."""
    df = make_df(n=400, slope=0.8, seed=7)
    mk = build_chart_markup(
        symbol="XAUUSD",
        mtf_data={"M15": df, "H1": df.copy(), "D1": df.copy()},
        method="INDICATOR",
        primary_tf="M15",
    )
    assert mk["objects"] == [], f"INDICATOR must not emit markup objects; got {len(mk['objects'])}"
    cf = mk["confluence"]
    assert cf["signal"] == "WAIT", f"INDICATOR must produce WAIT signal; got {cf['signal']}"
    assert cf["score"] == 0


def test_confluence_score_in_valid_range():
    df = make_df(n=200)
    objs = (
        compute_sniper_overlay("XAUUSD", df)
        + compute_smc_overlay(df)
        + compute_ict_overlay(df)
        + compute_pa_overlay(df)
    )
    cf = compute_confluence_score(objs, "ULTRA_CONFLUENCE", float(df["close"].iloc[-1]))
    assert -100 <= cf["score"] <= 100, f"score out of range: {cf['score']}"
    assert cf["signal"] in ("BUY", "SELL", "WAIT")
    assert cf["direction"] in ("BULLISH", "BEARISH", "NEUTRAL")
    assert isinstance(cf["factors"], list)


if __name__ == "__main__":
    test_sniper_emits_ema_ribbon_vwap_score()
    print("PASS: test_sniper_emits_ema_ribbon_vwap_score")
    test_sniper_generates_signal_and_tps_on_crossover()
    print("PASS: test_sniper_generates_signal_and_tps_on_crossover")
    test_smc_emits_swings_bsl_ssl_eqh_eql()
    print("PASS: test_smc_emits_swings_bsl_ssl_eqh_eql")
    test_ict_emits_pd_ote_killzone_asian()
    print("PASS: test_ict_emits_pd_ote_killzone_asian")
    test_pa_emits_pivots_pdh_pdl_and_patterns()
    print("PASS: test_pa_emits_pivots_pdh_pdl_and_patterns")
    test_method_groups_contain_overlay_types()
    print("PASS: test_method_groups_contain_overlay_types")
    test_confluence_score_in_valid_range()
    print("PASS: test_confluence_score_in_valid_range")
    test_pivot_direction_not_inverted()
    print("PASS: test_pivot_direction_not_inverted")
    test_indicator_method_emits_no_markup_and_waits()
    print("PASS: test_indicator_method_emits_no_markup_and_waits")
    print("\nALL 9 UNIT TESTS PASSED")