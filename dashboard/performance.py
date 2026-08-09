"""Verified closed-trade performance metrics without fabricated fallback values."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class ClosedTrade:
    position_id: int
    closed_at: int
    net_profit: float


def calculate_performance(trades: Iterable[ClosedTrade]) -> dict[str, object]:
    ordered = sorted(trades, key=lambda trade: (trade.closed_at, trade.position_id))
    if not ordered:
        return {
            "sample_size": 0,
            "win_rate": None,
            "profit_factor": None,
            "max_drawdown": None,
            "recovery_factor": None,
            "best_trade": None,
            "worst_trade": None,
            "equity_curve": [],
        }

    profits = [trade.net_profit for trade in ordered]
    gross_profit = sum(value for value in profits if value > 0)
    gross_loss = abs(sum(value for value in profits if value < 0))
    wins = sum(value > 0 for value in profits)
    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    curve = []
    for index, trade in enumerate(ordered):
        equity += trade.net_profit
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)
        curve.append({"i": index, "t": trade.closed_at, "v": round(equity, 2)})

    net_profit = sum(profits)
    return {
        "sample_size": len(ordered),
        "win_rate": round((wins / len(ordered)) * 100.0, 2),
        "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss else None,
        "max_drawdown": round(max_drawdown, 2),
        "recovery_factor": round(net_profit / max_drawdown, 4) if max_drawdown else None,
        "best_trade": round(max(profits), 2),
        "worst_trade": round(min(profits), 2),
        "equity_curve": curve,
    }
