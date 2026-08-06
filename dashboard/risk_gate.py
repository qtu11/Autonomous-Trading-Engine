"""Fail-closed risk policy evaluation for QuantAI execution intents."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import Iterable, Optional

from strategy_core import DecisionProposal, SignalAction


@dataclass(frozen=True)
class SymbolSpec:
    symbol: str
    volume_min: float
    volume_max: float
    volume_step: float
    tick_size: float
    tick_value: float
    max_spread: float


@dataclass(frozen=True)
class AccountSnapshot:
    equity: float
    margin_free: float
    daily_realized_pnl: float


@dataclass(frozen=True)
class RiskPolicy:
    version: str = "risk-v1"
    execution_enabled: bool = False
    risk_per_trade_fraction: float = 0.005
    max_daily_loss_fraction: float = 0.02
    max_open_positions: int = 5
    max_margin_utilization: float = 0.80
    minimum_margin_free: float = 100.0


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    reason_codes: tuple[str, ...]
    volume: Optional[float]
    policy_version: str


def _normalize_volume(requested: float, spec: SymbolSpec) -> Optional[float]:
    if not isfinite(requested) or not isfinite(spec.volume_min) or not isfinite(spec.volume_max) or not isfinite(spec.volume_step):
        return None
    if requested <= 0 or spec.volume_step <= 0 or requested < (spec.volume_min * 0.5):
        return None
    if requested < spec.volume_min:
        requested = spec.volume_min
    steps = int((requested - spec.volume_min + 1e-12) / spec.volume_step)
    volume = spec.volume_min + steps * spec.volume_step
    if volume > spec.volume_max:
        volume = spec.volume_max
    return round(volume, 2)


def evaluate_risk(
    *,
    proposal: DecisionProposal,
    account: AccountSnapshot,
    spec: SymbolSpec,
    bid: float,
    ask: float,
    open_position_count: int,
    policy: RiskPolicy = RiskPolicy(),
) -> RiskDecision:
    """Approve only safe open proposals; every uncertainty rejects the command."""
    finite_values = (
        account.equity, account.margin_free, account.daily_realized_pnl,
        bid, ask, open_position_count,
        policy.risk_per_trade_fraction, policy.max_daily_loss_fraction,
        policy.minimum_margin_free,
        spec.volume_min, spec.volume_max, spec.volume_step,
        spec.tick_size, spec.tick_value, spec.max_spread,
    )
    if not all(isfinite(float(value)) for value in finite_values):
        return RiskDecision(False, ("REJECT_NON_FINITE_INPUT",), None, policy.version)
    if not policy.execution_enabled:
        return RiskDecision(False, ("REJECT_EXECUTION_DISABLED",), None, policy.version)
    if proposal.action is SignalAction.NO_TRADE:
        return RiskDecision(False, ("NO_TRADE_PROPOSAL", *proposal.reason_codes), None, policy.version)
    if proposal.symbol != spec.symbol:
        return RiskDecision(False, ("REJECT_SYMBOL_MISMATCH",), None, policy.version)
    if account.equity <= 0 or account.margin_free < policy.minimum_margin_free:
        return RiskDecision(False, ("REJECT_MARGIN_OR_EQUITY",), None, policy.version)
    if account.daily_realized_pnl <= -(account.equity * policy.max_daily_loss_fraction):
        return RiskDecision(False, ("REJECT_DAILY_LOSS_LIMIT",), None, policy.version)
    if open_position_count >= policy.max_open_positions:
        return RiskDecision(False, ("REJECT_POSITION_LIMIT",), None, policy.version)
    if bid <= 0 or ask <= 0 or ask < bid or ask - bid > spec.max_spread:
        return RiskDecision(False, ("REJECT_SPREAD_OR_QUOTE",), None, policy.version)
    if proposal.entry is None or proposal.stop_loss is None or proposal.take_profit is None:
        return RiskDecision(False, ("REJECT_MISSING_STOPS",), None, policy.version)
    if not all(isfinite(float(value)) for value in (proposal.entry, proposal.stop_loss, proposal.take_profit)):
        return RiskDecision(False, ("REJECT_NON_FINITE_INPUT",), None, policy.version)

    is_buy = proposal.action is SignalAction.BUY
    if (is_buy and not (proposal.stop_loss < ask < proposal.take_profit)) or (
        not is_buy and not (proposal.take_profit < bid < proposal.stop_loss)
    ):
        return RiskDecision(False, ("REJECT_INVALID_STOP_DIRECTION",), None, policy.version)

    stop_distance = abs(proposal.entry - proposal.stop_loss)
    if stop_distance <= 0 or spec.tick_size <= 0 or spec.tick_value <= 0:
        return RiskDecision(False, ("REJECT_INVALID_RISK_INPUT",), None, policy.version)
    loss_per_lot = (stop_distance / spec.tick_size) * spec.tick_value
    requested_volume = (account.equity * policy.risk_per_trade_fraction) / loss_per_lot
    volume = _normalize_volume(requested_volume, spec)
    if volume is None:
        return RiskDecision(False, ("REJECT_VOLUME_LIMIT",), None, policy.version)
    return RiskDecision(True, ("APPROVE_RISK_POLICY",), volume, policy.version)
