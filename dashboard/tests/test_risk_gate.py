"""Unit tests for evaluate_risk_gate function. Phase 4."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from server import evaluate_risk_gate, _config, _account


def test_approved_high_quality():
    """All conditions good → approved."""
    result = evaluate_risk_gate(
        symbol="XAUUSD", signal="BUY",
        entry=3370.0, sl=3360.0, tp=3390.0,
        spread=2.0, atr=15.0, score=75, method="SMC"
    )
    assert result["approved"] is True, f"Should be approved: {result['reason']}"
    assert "spread" in result["checks"]
    assert "volatility" in result["checks"]
    assert "margin" in result["checks"]
    print("test_approved_high_quality: PASS")


def test_rejected_high_spread():
    """High spread > max → rejected."""
    _config["max_spread"] = 4.5
    result = evaluate_risk_gate(
        symbol="XAUUSD", signal="BUY",
        entry=3370.0, sl=3360.0, tp=3390.0,
        spread=10.0, atr=15.0, score=80, method="SMC"
    )
    assert result["approved"] is False
    assert "spread" in result["reason"].lower() or any(k == "spread" for k in result["reason"].split())
    assert result["checks"]["spread"]["ok"] is False
    print("test_rejected_high_spread: PASS")


def test_rejected_high_volatility():
    """ATR % too high → rejected."""
    result = evaluate_risk_gate(
        symbol="XAUUSD", signal="BUY",
        entry=3370.0, sl=3360.0, tp=3390.0,
        spread=2.0, atr=200.0,  # 6% of price
        score=80, method="SMC"
    )
    assert result["approved"] is False
    assert result["checks"]["volatility"]["ok"] is False
    print("test_rejected_high_volatility: PASS")


def test_rejected_low_margin():
    """Insufficient free margin → rejected."""
    _account["margin_free"] = 50.0
    result = evaluate_risk_gate(
        symbol="XAUUSD", signal="BUY",
        entry=3370.0, sl=3300.0, tp=3500.0,
        spread=2.0, atr=15.0, score=80, method="SMC"
    )
    assert result["checks"]["margin"]["ok"] is False
    print("test_rejected_low_margin: PASS")


def test_rejected_max_drawdown():
    """Max drawdown breached → rejected."""
    _account["balance"] = 10000.0
    _account["total_pnl"] = -600.0  # 6% drawdown
    result = evaluate_risk_gate(
        symbol="XAUUSD", signal="BUY",
        entry=3370.0, sl=3360.0, tp=3390.0,
        spread=2.0, atr=15.0, score=80, method="SMC"
    )
    assert result["checks"]["max_drawdown"]["ok"] is False
    print("test_rejected_max_drawdown: PASS")


def test_rejected_daily_loss():
    """Daily loss too high → rejected."""
    _account["balance"] = 10000.0
    _account["total_pnl"] = -350.0  # 3.5% > 3% threshold
    result = evaluate_risk_gate(
        symbol="XAUUSD", signal="BUY",
        entry=3370.0, sl=3360.0, tp=3390.0,
        spread=2.0, atr=15.0, score=80, method="SMC"
    )
    assert result["checks"]["daily_pnl"]["ok"] is False
    print("test_rejected_daily_loss: PASS")


def test_checks_complete():
    """All 9 checks must be present."""
    result = evaluate_risk_gate(
        symbol="XAUUSD", signal="BUY",
        entry=3370.0, sl=3360.0, tp=3390.0,
        spread=2.0, atr=15.0, score=80, method="SMC"
    )
    required = {"spread", "volatility", "news", "margin", "risk_pct",
                "max_drawdown", "max_lot", "daily_pnl", "session"}
    assert required.issubset(result["checks"].keys()), \
        f"Missing checks: {required - set(result['checks'].keys())}"
    print("test_checks_complete: PASS")


if __name__ == "__main__":
    test_approved_high_quality()
    test_rejected_high_spread()
    test_rejected_high_volatility()
    test_rejected_low_margin()
    test_rejected_max_drawdown()
    test_rejected_daily_loss()
    test_checks_complete()
    print("\nALL TESTS PASSED")
