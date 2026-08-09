"""Fail-closed risk policy evaluation for QuantAI execution intents."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import isfinite

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
    volume: float | None
    policy_version: str


#--- Dynamic lot sizing / DCA tuning (applies at command-issuance time) ---------
# AI tự quyết định khối lượng dựa trên vốn; mọi lô được clamp trong [volume_min, volume_max].
# DCA tích cực (cùng hướng, giá theo đúng kịch bản): lot lệnh đầu lớn nhất, các lệnh sau nhỏ dần.
# DCA âm (giá chạy ngược): lot theo cấp số cộng tăng dần nhưng tổng rủi ro không vượt cap.
DCA_DEFAULT_MIN_LOT    = 0.01
DCA_DEFAULT_MAX_LOT    = 20.0
# Hệ số thu nhỏ lot khi nhồi cùng hướng (mỗi lệnh sau = lot trước * ratio)
DCA_SAME_DIRECTION_RATIO = 0.60
# Hệ số tăng khi nhồi ngược hướng:   vol(n) = base * (1 + growth * (n-1))
DCA_COUNTER_DIRECTION_GROWTH = 1.20
# Tổng rủi ro nếu toàn bộ basket chạm SL không được vượt quá tỷ lệ equity.
MAX_BASKET_LOSS_FRACTION = 0.50


def _normalize_volume(requested: float, spec: SymbolSpec, volume_max: float | None = None) -> float | None:
    if not isfinite(requested) or not isfinite(spec.volume_min) or not isfinite(spec.volume_max) or not isfinite(spec.volume_step):
        return None
    if requested <= 0 or spec.volume_step <= 0:
        return None
    if requested < spec.volume_min * 0.5:
        return None
    hard_max = spec.volume_max if volume_max is None else min(volume_max, spec.volume_max)
    requested = max(requested, spec.volume_min)
    steps = int((requested - spec.volume_min + 1e-12) / spec.volume_step)
    volume = spec.volume_min + steps * spec.volume_step
    volume = min(volume, hard_max)
    return round(volume, 2)


def compute_dca_volume(
    *,
    base_volume: float,
    entry_index: int,
    same_direction: bool,
    spec: SymbolSpec,
    volume_max: float = DCA_DEFAULT_MAX_LOT,
) -> float | None:
    """Khối lượng cho lệnh thứ `entry_index` (0-based) trong chuỗi DCA.

    - entry_index 0: lệnh đầu tiên dùng đúng volume từ equity-based sizing.
    - same_direction=True  (nhồi đứng hướng, giá đúng kịch bản): lot giảm dần sau mỗi lệnh.
    - same_direction=False (DCA ngược, giá đang chạy ngược vùng SL cũ): lot tăng dần nhưng vẫn <= max.
    Không bao giờ trả > volume_max hoặc < volume_min.
    """
    if base_volume is None or not isfinite(base_volume) or base_volume <= 0:
        return None
    if entry_index <= 0:
        return _normalize_volume(base_volume, spec, volume_max)
    if same_direction:
        scaled = base_volume * (DCA_SAME_DIRECTION_RATIO ** entry_index)
    else:
        scaled = base_volume * (1.0 + DCA_COUNTER_DIRECTION_GROWTH * entry_index)
    return _normalize_volume(scaled, spec, volume_max)


def cap_volume_to_basket_risk(
    *,
    desired_volume: float | None,
    existing_lot_volumes: Iterable[float],
    risk_per_lot: float,
    equity: float,
    spec: SymbolSpec,
    max_basket_loss_fraction: float = MAX_BASKET_LOSS_FRACTION,
) -> float | None:
    """Giới hạn lot của lệnh sắp mở sao cho nếu TOÀN BỘ basket chạm SL thì tổng
    rủi ro = risk_per_lot * (existing_lots + new_lot) không vượt equity * fraction.
    Trả None khi basket đã dùng hết ngân sách rủi ro (chặn nhồi thêm)."""
    if desired_volume is None or equity <= 0 or not isfinite(risk_per_lot) or risk_per_lot <= 0:
        return None
    existing_lots = sum(float(v) for v in existing_lot_volumes)
    if not isfinite(existing_lots) or existing_lots < 0:
        return None
    budget = equity * max(max_basket_loss_fraction, 0.0)
    remaining_budget = budget - (risk_per_lot * existing_lots)
    if remaining_budget <= 0:
        return None
    allowed_lot = remaining_budget / risk_per_lot
    return _normalize_volume(min(desired_volume, allowed_lot), spec)


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
