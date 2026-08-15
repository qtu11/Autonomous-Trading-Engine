"""Tests for Institutional Structure Engine (ISE - structureengine.pine)."""

import pandas as pd
import numpy as np
import pytest
from structure_engine import detect_institutional_structure_engine
from method_overlays import compute_confluence_score, compute_structure_engine_overlay


@pytest.fixture
def sample_ohlcv():
    np.random.seed(42)
    n = 200
    dates = pd.date_range("2026-08-01", periods=n, freq="15min")
    price = 2800.0 + np.cumsum(np.random.randn(n) * 2.0)
    high = price + np.random.rand(n) * 3.0
    low = price - np.random.rand(n) * 3.0
    open_p = price + np.random.randn(n) * 0.5
    close = price + np.random.randn(n) * 0.5
    volume = np.random.randint(500, 5000, n)
    return pd.DataFrame({
        "time": dates,
        "open": open_p,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })


def test_structure_engine_detects_envelopes_swings_and_sd(sample_ohlcv):
    res = detect_institutional_structure_engine(sample_ohlcv)
    assert "envelopes" in res
    assert len(res["envelopes"]) == 5
    assert "swings" in res
    assert len(res["swings"]) > 0
    assert "objects" in res
    assert len(res["objects"]) > 0
    assert "confluence_score" in res
    assert 0 <= res["confluence_score"] <= 10


def test_structure_engine_overlay_and_confluence(sample_ohlcv):
    mtf_data = {"M15": sample_ohlcv}
    objs = compute_structure_engine_overlay(mtf_data, primary_tf="M15")
    assert len(objs) > 0
    cf = compute_confluence_score(objs, "STRUCTURE_ENGINE", float(sample_ohlcv["close"].iloc[-1]))
    assert "signal" in cf
    assert cf["signal"] in ("BUY", "SELL", "WAIT")
    assert "score" in cf
