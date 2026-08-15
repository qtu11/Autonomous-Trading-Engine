"""Unit tests for auto-trade logic and method switching stability."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pandas as pd
import numpy as np
from method_overlays import compute_confluence_score
from server import evaluate_risk_gate, _config, _account


def test_confluence_sl_tp_never_none_for_buy_sell_signals():
    """Verify that BUY and SELL signals always produce valid SL, TP, and RRR >= 1.0 across all methods."""
    methods = ["SNIPER", "SMC", "ICT", "PRICE_ACTION", "ULTRA_CONFLUENCE"]
    entry_price = 2850.0

    for method in methods:
        # 1. Bullish scenario with natural structure
        bullish_objs = [
            {"type": "OB", "direction": "BULLISH", "top": 2840.0, "bottom": 2830.0, "touches": 2},
            {"type": "RESISTANCE", "price": 2880.0, "touches": 3},
            {"type": "SNIPER_SCORE", "bull_pct": 85, "bear_pct": 15},
            {"type": "ADX", "price": 32.0},  # Non-price indicator object
            {"type": "RSI_LEVEL", "top": 70.0, "bottom": 30.0},
        ]
        res_buy = compute_confluence_score(bullish_objs, method, entry_price)
        if res_buy["signal"] in ("BUY", "SELL"):
            assert res_buy["sl"] is not None, f"SL must not be None for {method} {res_buy['signal']}"
            assert res_buy["tp"] is not None, f"TP must not be None for {method} {res_buy['signal']}"
            assert res_buy["rrr"] is not None and res_buy["rrr"] >= 1.0, f"RRR must be >= 1.0 for {method}"
            if res_buy["signal"] == "BUY":
                assert res_buy["sl"] < entry_price
                assert res_buy["tp"] > entry_price

        # 2. Bearish scenario with ATH / no natural resistance above
        bearish_objs = [
            {"type": "OB", "direction": "BEARISH", "top": 2870.0, "bottom": 2860.0, "touches": 2},
            {"type": "SNIPER_SCORE", "bull_pct": 10, "bear_pct": 90},
        ]
        res_sell = compute_confluence_score(bearish_objs, method, entry_price)
        if res_sell["signal"] in ("BUY", "SELL"):
            assert res_sell["sl"] is not None, f"SL must not be None for {method} {res_sell['signal']}"
            assert res_sell["tp"] is not None, f"TP must not be None for {method} {res_sell['signal']}"
            assert res_sell["rrr"] is not None and res_sell["rrr"] >= 1.0, f"RRR must be >= 1.0 for {method}"
            if res_sell["signal"] == "SELL":
                assert res_sell["sl"] > entry_price
                assert res_sell["tp"] < entry_price


def test_confluence_wait_signal_clean_state():
    """Verify that WAIT signal returns None for sl, tp, and rrr."""
    objs = [
        {"type": "SNIPER_SCORE", "bull_pct": 50, "bear_pct": 50},
    ]
    res = compute_confluence_score(objs, "SMC", 2500.0)
    assert res["signal"] == "WAIT"
    assert res["sl"] is None
    assert res["tp"] is None
    assert res["rrr"] is None


def test_evaluate_risk_gate_all_methods_approved():
    """Verify that evaluate_risk_gate approves valid setups for all 5 trading methods."""
    for method in ["SNIPER", "SMC", "ICT", "PRICE_ACTION", "ULTRA_CONFLUENCE"]:
        res = evaluate_risk_gate(
            symbol="XAUUSD",
            signal="BUY",
            entry=2800.0,
            sl=2785.0,
            tp=2830.0,
            spread=1.5,
            atr=12.0,
            score=75,
            method=method
        )
        assert res["approved"] is True, f"Failed for {method}: {res['reason']}"
        assert res["checks"]["session"]["ok"] is True
        assert res["checks"]["spread"]["ok"] is True
