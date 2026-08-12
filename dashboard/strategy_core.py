"""Deterministic, offline-testable signal decision functions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


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
    entry: float | None
    stop_loss: float | None
    take_profit: float | None
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
        created_at=_now_iso(),
    )


def decide_signal(
    *,
    symbol: str,
    timeframe: str,
    indicators: Mapping[str, object],
    bid: float,
    ask: float,
    config: StrategyConfig = StrategyConfig(),
) -> DecisionProposal:
    """Return one structured proposal; missing or invalid inputs always abstain."""
    timestamp = _now_iso()

    required = ("ema20", "ema50", "ema200", "rsi", "atr")
    if not any(k in indicators for k in required):
        return _no_trade(symbol, timeframe, config, "INSUFFICIENT_INDICATORS")

    if bid <= 0 or ask <= 0:
        return _no_trade(symbol, timeframe, config, "INVALID_QUOTE")

    try:
        v_ema20 = indicators.get("ema20")
        v_ema50 = indicators.get("ema50")
        v_ema200 = indicators.get("ema200")
        v_rsi = indicators.get("rsi")
        v_atr = indicators.get("atr")
        if v_ema20 is None or v_ema50 is None or v_ema200 is None or v_rsi is None or v_atr is None:
            return _no_trade(symbol, timeframe, config, "INVALID_INDICATORS")
        ema20 = float(str(v_ema20))
        ema50 = float(str(v_ema50))
        ema200 = float(str(v_ema200))
        rsi = float(str(v_rsi))
        atr = float(str(v_atr))
    except (TypeError, ValueError):
        return _no_trade(symbol, timeframe, config, "INVALID_INDICATORS")


    if atr < config.minimum_atr:
        return _no_trade(symbol, timeframe, config, "LOW_VOLATILITY")

    if not (0 <= rsi <= 100):
        return _no_trade(symbol, timeframe, config, "INVALID_RSI")

    action = SignalAction.NO_TRADE
    reasons: list[str] = []
    confidence = 0

    # Bullish confluence: ema20 > ema50 > ema200 and RSI 40-85
    if ema20 > ema50 > ema200:
        reasons.append("BULLISH_EMA_ALIGNMENT")
        confidence += 15
        if 40 <= rsi <= 85:
            reasons.append("BUY_RSI_RANGE")
            confidence += 60
            action = SignalAction.BUY

    # Bearish confluence: ema20 < ema50 < ema200 and RSI 15-60
    elif ema20 < ema50 < ema200:
        reasons.append("BEARISH_EMA_ALIGNMENT")
        confidence += 15
        if 15 <= rsi <= 60:
            reasons.append("SELL_RSI_RANGE")
            confidence += 60
            action = SignalAction.SELL

    if action is SignalAction.NO_TRADE:
        return _no_trade(symbol, timeframe, config, "NO_CONFLUENCE")

    if confidence < config.minimum_confidence:
        return _no_trade(symbol, timeframe, config, "NO_CONFLUENCE")

    stop_distance = atr * config.atr_stop_multiplier
    target_distance = stop_distance * config.risk_reward

    if action is SignalAction.BUY:
        entry = ask
        stop_loss = round(entry - stop_distance, 8)
        take_profit = round(entry + target_distance, 8)
    else:
        entry = bid
        stop_loss = round(entry + stop_distance, 8)
        take_profit = round(entry - target_distance, 8)

    return DecisionProposal(
        action=action,
        symbol=symbol,
        timeframe=timeframe,
        confidence=confidence,
        entry=entry,
        stop_loss=stop_loss,
        take_profit=take_profit,
        reason_codes=tuple(reasons),
        strategy_version=config.version,
        created_at=timestamp,
    )
