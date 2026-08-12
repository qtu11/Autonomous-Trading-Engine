"""
Comprehensive Input Validation for Trading System
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Literal
from datetime import datetime
from enum import Enum
import re


class SymbolEnum(str, Enum):
    """Valid trading symbols"""
    BTCUSDT = "BTCUSDT"
    ETHUSDT = "ETHUSDT"
    BNBUSDT = "BNBUSDT"
    SOLUSDT = "SOLUSDT"
    XAUUSD = "XAUUSD"
    XAUUSDm = "XAUUSDm"
    BTCUSD = "BTCUSD"
    ETHUSD = "ETHUSD"
    BTCUSDm = "BTCUSDm"
    ETHUSDm = "ETHUSDm"
    XAGUSD = "XAGUSD"
    XAGUSDm = "XAGUSDm"
    EURUSDm = "EURUSDm"
    GBPJPY = "GBPJPY"
    GBPJPYm = "GBPJPYm"
    XPDUSD = "XPDUSD"
    XPDUSDm = "XPDUSDm"
    USDJPY = "USDJPY"
    USDJPYm = "USDJPYm"
    AUDUSD = "AUDUSD"
    AUDUSDm = "AUDUSDm"
    NZDUSD = "NZDUSD"
    NZDUSDm = "NZDUSDm"
    USDCAD = "USDCAD"
    USDCADm = "USDCADm"
    AUDCAD = "AUDCAD"
    AUDCADm = "AUDCADm"
    AUDJPY = "AUDJPY"
    AUDJPYm = "AUDJPYm"
    EURAUD = "EURAUD"
    EURAUDm = "EURAUDm"
    EURGBP = "EURGBP"
    EURGBPm = "EURGBPm"
    EURJPY = "EURJPY"
    EURJPYm = "EURJPYm"
    EURSGD = "EURSGD"
    EURSGDm = "EURSGDm"
    GBPUSD = "GBPUSD"
    GBPUSDm = "GBPUSDm"
    GBPCAD = "GBPCAD"
    GBPCADm = "GBPCADm"
    GBPCHF = "GBPCHF"
    GBPCHFM = "GBPCHFM"
    GBPAUD = "GBPAUD"
    GBPAUDm = "GBPAUDm"
    GBPNZD = "GBPNZD"
    GBPNZDm = "GBPNZDm"
    GBPSGD = "GBPSGD"
    GBPSGDm = "GBPSGDm"
    XPTUSD = "XPTUSD"
    XPTUSDm = "XPTUSDm"
    XPTJPY = "XPTJPY"
    XPTJPYm = "XPTJPYm"
    XPTGBP = "XPTGBP"
    XPTGBPm = "XPTGBPm"
    XPTCHF = "XPTCHF"
    XPTCHFM = "XPTCHFM"
    XPTAUD = "XPTAUD"
    XPTAUDm = "XPTAUDm"
    XPTNZD = "XPTNZD"
    XPTNZDm = "XPTNZDm"
    XPTCAD = "XPTCAD"
    XPTCADm = "XPTCADm"


class TimeframeEnum(str, Enum):
    """Valid timeframes"""
    M1 = "M1"
    M5 = "M5"
    M15 = "M15"
    M30 = "M30"
    H1 = "H1"
    H4 = "H4"
    D1 = "D1"


class TradingModeEnum(str, Enum):
    """Trading modes"""
    PAPER = "paper"
    LIVE = "live"
    BACKTEST = "backtest"


class DirectionEnum(str, Enum):
    """Trade directions"""
    LONG = "long"
    SHORT = "short"


# ─── Request Validators ────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    """Analyze request validation"""
    symbol: SymbolEnum
    timeframe: TimeframeEnum = TimeframeEnum.M15
    count: int = Field(default=1000, ge=10, le=5000)

    @field_validator('count')
    def validate_count(cls, v):
        if v < 10 or v > 5000:
            raise ValueError('count must be between 10 and 5000')
        return v


class OrderRequest(BaseModel):
    """Order request validation"""
    symbol: SymbolEnum
    direction: DirectionEnum
    quantity: float = Field(gt=0, le=100)
    entry_price: Optional[float] = Field(default=None, gt=0)
    stop_loss: Optional[float] = Field(default=None, gt=0)
    take_profit: Optional[float] = Field(default=None, gt=0)
    
    @field_validator('quantity')
    def validate_quantity(cls, v):
        if v <= 0:
            raise ValueError('quantity must be positive')
        if v > 100:
            raise ValueError('quantity exceeds maximum (100)')
        return v

    @field_validator('stop_loss', 'take_profit', 'entry_price')
    def validate_prices(cls, v):
        if v is not None and v <= 0:
            raise ValueError('price must be positive')
        return v


class RiskProfileRequest(BaseModel):
    """Risk profile request validation"""
    max_risk_per_trade: float = Field(ge=0.1, le=10)
    max_daily_loss: float = Field(ge=0.5, le=50)
    max_open_trades: int = Field(ge=1, le=10)
    position_size_method: Literal["fixed", "kelly", "atr"] = "fixed"


class SignalFilterRequest(BaseModel):
    """Signal filter request validation"""
    symbol: Optional[SymbolEnum] = None
    direction: Optional[DirectionEnum] = None
    min_score: int = Field(default=0, ge=0, le=15)
    timeframe: Optional[TimeframeEnum] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

    @field_validator('end_date')
    def validate_dates(cls, v, info):
        start = info.data.get('start_date') if info.data else None
        if v and start:
            if v < start:
                raise ValueError('end_date must be after start_date')
        return v


# ─── Response Validators ──────────────────────────────────────────────────────

class SignalResponse(BaseModel):
    """Signal response validation"""
    signal_id: str
    symbol: str
    direction: DirectionEnum
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float = Field(ge=0, le=100)
    total_score: int = Field(ge=0, le=15)
    created_at: datetime  # Pydantic V2 serializes datetime -> ISO-8601 natively


class PositionResponse(BaseModel):
    """Position response validation"""
    position_id: str
    symbol: str
    direction: DirectionEnum
    entry_price: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    opened_at: datetime  # Pydantic V2 serializes datetime -> ISO-8601 natively


class AccountResponse(BaseModel):
    """Account response validation"""
    balance: float = Field(ge=0)
    equity: float = Field(ge=0)
    available_balance: float = Field(ge=0)
    open_positions_count: int = Field(ge=0)
    total_pnl: float
    win_rate: float = Field(ge=0, le=100)
    total_trades: int = Field(ge=0)
    max_drawdown: float


# ─── Utility Validators ────────────────────────────────────────────────────────

def validate_symbol(symbol: str) -> bool:
    """Validate trading symbol format"""
    pattern = r'^[A-Z]{3,10}(USDT|USDM?|BTC|ETH)$'
    return bool(re.match(pattern, symbol))


def validate_timeframe(timeframe: str) -> bool:
    """Validate timeframe format"""
    valid_timeframes = ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1', 'W1']
    return timeframe in valid_timeframes


def validate_price(price: float, min_val: float = 0.0001) -> bool:
    """Validate price value"""
    return price >= min_val


def sanitize_input(value: str, max_length: int = 100) -> str:
    """Sanitize user input"""
    if not isinstance(value, str):
        return str(value)
    # Remove potential injection characters while stripping surrounding whitespace
    cleaned = re.sub(r'[<>\'\";]|\bDROP TABLE\b', lambda m: '' if m.group(0) != 'DROP TABLE' else 'DROPTABLE', value, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+', '', cleaned) if 'DROP TABLE' in value else cleaned.strip()
    return cleaned[:max_length]


