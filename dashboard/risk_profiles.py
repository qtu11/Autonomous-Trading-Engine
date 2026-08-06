"""Conservative per-pair policy defaults for demo/paper evaluation."""

from __future__ import annotations

from risk_gate import RiskPolicy


FOREX_RISK_PROFILES = {
    "EURUSD": {
        "max_spread": 0.00020,
        "policy": RiskPolicy(version="forex-major-v1", execution_enabled=True, risk_per_trade_fraction=0.005, max_open_positions=3),
    },
    "XAUUSD": {
        # Gold requires a broker-calibrated raw-price spread cap; execution is enabled.
        "max_spread": 0.50,
        "policy": RiskPolicy(version="xauusd-v2", execution_enabled=True, risk_per_trade_fraction=0.02, max_open_positions=5, max_margin_utilization=0.80),
    },
    "XAUUSDM": {
        "max_spread": 0.50,
        "policy": RiskPolicy(version="xauusd-v2", execution_enabled=True, risk_per_trade_fraction=0.02, max_open_positions=5, max_margin_utilization=0.80),
    },
    "XAGUSD": {
        "max_spread": 0.00020,
        "policy": RiskPolicy(version="forex-v1", execution_enabled=True, risk_per_trade_fraction=0.005, max_open_positions=3),
    },
    "GBPUSD": {
        "max_spread": 0.00030,
        "policy": RiskPolicy(version="forex-v1", execution_enabled=True, risk_per_trade_fraction=0.004, max_open_positions=3),
    },
    "USDJPY": {
        "max_spread": 0.020,
        "policy": RiskPolicy(version="forex-v1", execution_enabled=True, risk_per_trade_fraction=0.004, max_open_positions=3),
    },
    "AUDUSD": {
        "max_spread": 0.00025,
        "policy": RiskPolicy(version="forex-v1", execution_enabled=True, risk_per_trade_fraction=0.004, max_open_positions=3),
    },
}
