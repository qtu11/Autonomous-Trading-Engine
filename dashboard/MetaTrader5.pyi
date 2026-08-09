"""Type stub for MetaTrader5 C extension module.

This provides type information for static analysis tools (Pyright, Pyrefly, mypy)
since MetaTrader5 is a C extension that ships without inline types or py.typed.
"""
from typing import Any

# ── Timeframe constants ────────────────────────────────────────────────────
TIMEFRAME_M1: int
TIMEFRAME_M5: int
TIMEFRAME_M15: int
TIMEFRAME_M30: int
TIMEFRAME_H1: int
TIMEFRAME_H4: int
TIMEFRAME_D1: int
TIMEFRAME_W1: int
TIMEFRAME_MN1: int

# ── Order / Trade constants ────────────────────────────────────────────────
ORDER_TYPE_BUY: int
ORDER_TYPE_SELL: int
ORDER_TYPE_BUY_LIMIT: int
ORDER_TYPE_SELL_LIMIT: int
ORDER_TYPE_BUY_STOP: int
ORDER_TYPE_SELL_STOP: int

ORDER_FILLING_FOK: int
ORDER_FILLING_IOC: int
ORDER_FILLING_RETURN: int

ORDER_TIME_GTC: int
ORDER_TIME_DAY: int
ORDER_TIME_SPECIFIED: int

TRADE_ACTION_DEAL: int
TRADE_ACTION_PENDING: int
TRADE_ACTION_SLTP: int
TRADE_ACTION_MODIFY: int
TRADE_ACTION_REMOVE: int

TRADE_RETCODE_DONE: int
TRADE_RETCODE_REQUOTE: int

DEAL_ENTRY_IN: int
DEAL_ENTRY_OUT: int
DEAL_ENTRY_INOUT: int

COPY_TICKS_ALL: int
COPY_TICKS_INFO: int
COPY_TICKS_TRADE: int


# ── Info result types ──────────────────────────────────────────────────────
class AccountInfo:
    login: int
    server: str
    balance: float
    equity: float
    margin: float
    margin_free: float
    margin_level: float
    profit: float
    currency: str
    leverage: int
    company: str
    name: str
    trade_mode: int


class SymbolInfo:
    name: str
    description: str
    visible: bool
    trade_mode: int
    point: float
    digits: int
    spread: int
    volume_min: float
    volume_max: float
    volume_step: float
    trade_contract_size: float
    trade_tick_size: float
    trade_tick_value: float
    filling_mode: int


class Tick:
    time: int
    bid: float
    ask: float
    last: float
    volume: int
    time_msc: int
    flags: int


class TerminalInfo:
    connected: bool
    community_account: bool
    community_connection: bool
    mqid: bool
    trade_allowed: bool
    trade_expert: bool
    path: str
    data_path: str
    commondata_path: str


class TradeOrder:
    ticket: int
    time_setup: int
    type: int
    state: int
    symbol: str
    volume_initial: float
    volume_current: float
    price_open: float
    sl: float
    tp: float
    price_current: float
    price_stoplimit: float
    magic: int
    comment: str


class TradePosition:
    ticket: int
    time: int
    type: int
    magic: int
    identifier: int
    reason: int
    volume: float
    price_open: float
    sl: float
    tp: float
    price_current: float
    swap: float
    profit: float
    symbol: str
    comment: str


class TradeDeal:
    ticket: int
    order: int
    time: int
    time_msc: int
    type: int
    entry: int
    magic: int
    position_id: int
    reason: int
    volume: float
    price: float
    commission: float
    swap: float
    profit: float
    fee: float
    symbol: str
    comment: str
    external_id: str


class OrderSendResult:
    retcode: int
    deal: int
    order: int
    volume: float
    price: float
    bid: float
    ask: float
    comment: str
    request_id: int
    request: Any


# ── Functions ──────────────────────────────────────────────────────────────
def initialize(
    path: str = ...,
    login: int = ...,
    password: str = ...,
    server: str = ...,
    timeout: int = ...,
    portable: bool = ...,
) -> bool: ...

def shutdown() -> None: ...

def terminal_info() -> TerminalInfo | None: ...

def account_info() -> AccountInfo | None: ...

def last_error() -> tuple[int, str]: ...

def symbol_info(symbol: str) -> SymbolInfo | None: ...

def symbol_info_tick(symbol: str) -> Tick | None: ...

def symbol_select(symbol: str, enable: bool = ...) -> bool: ...

def symbols_get(group: str = ...) -> tuple[SymbolInfo, ...] | None: ...

def positions_get(
    symbol: str = ...,
    group: str = ...,
    ticket: int = ...,
) -> tuple[TradePosition, ...] | None: ...

def orders_get(
    symbol: str = ...,
    group: str = ...,
    ticket: int = ...,
) -> tuple[TradeOrder, ...] | None: ...

def history_deals_get(
    date_from: Any = ...,
    date_to: Any = ...,
    group: str = ...,
    ticket: int = ...,
    position: int = ...,
) -> tuple[TradeDeal, ...] | None: ...

def copy_rates_from_pos(
    symbol: str,
    timeframe: int,
    start_pos: int,
    count: int,
) -> Any: ...

def order_send(request: dict[str, Any]) -> OrderSendResult | None: ...
