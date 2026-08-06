"""Deterministic, offline-testable signal decision functions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Mapping, Optional


class SignalAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    NO_TRADE = "NO_TRADE"


@dataclass(frozen=True)
class StrategyConfig:
    version: str = "trend-confluence-v1"
    minimum_confidence: int = 70
    minimum_atr: float = 0.0
    risk_reward: float = 2.0
    atr_stop_multiplier: float = 1.5


@dataclass(frozen=True)
class DecisionProposal:
    action: SignalAction
    symbol: str
    timeframe: str
    confidence: int
    entry: Optional[float]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    reason_codes: tuple[str, ...] = field(default_factory=tuple)
    strategy_version: str = ""
    created_at: str = ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _no_trade(
    symbol: str,
    timeframe: str,
    config: StrategyConfig,
    *reasons: str,
    created_at: Optional[str] = None,
) -> DecisionProposal:
    return DecisionProposal(
        action=SignalAction.NO_TRADE,
        symbol=symbol,
        timeframe=timeframe,
        confidence=0,
        entry=None,
        stop_loss=None,
        take_profit=None,
        reason_codes=tuple(reasons),
        strategy_version=config.version,
        created_at=created_at or _now_iso(),
    )


def decide_signal(
    *,
    symbol: str,
    timeframe: str,
    indicators: Mapping[str, object],
    bid: float,
    ask: float,
    config: StrategyConfig = StrategyConfig(),
    created_at: Optional[str] = None,
) -> DecisionProposal:
    """Return one structured proposal; missing or invalid inputs always abstain."""
    timestamp = created_at or _now_iso()
    required = ("ema20", "ema50", "ema200", "rsi", "atr")
    if any(key not in indicators or indicators[key] is None for key in required):
        return _no_trade(symbol, timeframe, config, "INSUFFICIENT_INDICATORS", created_at=timestamp)
    if bid <= 0 or ask <= 0 or ask < bid:
        return _no_trade(symbol, timeframe, config, "INVALID_QUOTE", created_at=timestamp)
    try:
        ema20 = float(indicators["ema20"])
        ema50 = float(indicators["ema50"])
        ema200 = float(indicators["ema200"])
        rsi = float(indicators["rsi"])
        atr = float(indicators["atr"])
    except (TypeError, ValueError):
        return _no_trade(symbol, timeframe, config, "INVALID_INDICATORS", created_at=timestamp)
    if atr <= config.minimum_atr or atr <= 0:
        return _no_trade(symbol, timeframe, config, "LOW_VOLATILITY", created_at=timestamp)
    if not 0 <= rsi <= 100:
        return _no_trade(symbol, timeframe, config, "INVALID_RSI", created_at=timestamp)

    if ema20 > ema50 and ema50 > ema200 and 40 <= rsi <= 85:
        action = SignalAction.BUY
        reasons = ["BULLISH_EMA_ALIGNMENT", "BUY_RSI_RANGE"]
    elif ema20 < ema50 and ema50 < ema200 and 15 <= rsi <= 60:
        action = SignalAction.SELL
        reasons = ["BEARISH_EMA_ALIGNMENT", "SELL_RSI_RANGE"]
    else:
        return _no_trade(symbol, timeframe, config, "NO_CONFLUENCE", created_at=timestamp)

    confidence = 80
    stop_distance = atr * config.atr_stop_multiplier
    target_distance = stop_distance * config.risk_reward
    entry = ask if action is SignalAction.BUY else bid
    stop_loss = entry - stop_distance if action is SignalAction.BUY else entry + stop_distance
    take_profit = entry + target_distance if action is SignalAction.BUY else entry - target_distance
    return DecisionProposal(
        action=action,
        symbol=symbol,
        timeframe=timeframe,
        confidence=confidence,
        entry=round(entry, 8),
        stop_loss=round(stop_loss, 8),
        take_profit=round(take_profit, 8),
        reason_codes=tuple(reasons),
        strategy_version=config.version,
        created_at=timestamp,
    )
