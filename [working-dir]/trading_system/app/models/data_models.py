"""
Data Models for Trading System
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import pandas as pd


class TimeFrame(str, Enum):
    """Trading timeframes"""
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"


class TradeDirection(str, Enum):
    """Trade direction"""
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


class SignalType(str, Enum):
    """Signal type"""
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    NEUTRAL = "neutral"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


class PatternType(str, Enum):
    """Candlestick pattern types"""
    # Bullish
    BULLISH_PINBAR = "bullish_pinbar"
    BULLISH_ENGULFING = "bullish_engulfing"
    BULLISH_REJECTION = "bullish_rejection"
    HAMMER = "hammer"
    MORNING_STAR = "morning_star"
    TWEEZER_BOTTOM = "tweezer_bottom"
    THREE_WHITE_SOLDIERS = "three_white_soldiers"
    INSIDE_BULL_BREAK = "inside_bull_break"
    
    # Bearish
    BEARISH_PINBAR = "bearish_pinbar"
    BEARISH_ENGULFING = "bearish_engulfing"
    BEARISH_REJECTION = "bearish_rejection"
    SHOOTING_STAR = "shooting_star"
    EVENING_STAR = "evening_star"
    TWEEZER_TOP = "tweezer_top"
    THREE_BLACK_CROWS = "three_black_crows"
    INSIDE_BEAR_BREAK = "inside_bear_break"


class SMCLevel(str, Enum):
    """SMC market structure levels"""
    BULLISH_FVG = "bullish_fvg"
    BEARISH_FVG = "bearish_fvg"
    BULLISH_OB = "bullish_ob"
    BEARISH_OB = "bearish_ob"
    BREAKER_BULL = "breaker_bull"
    BREAKER_BEAR = "breaker_bear"
    IFVG_BULL = "ifvg_bull"
    IFVG_BEAR = "ifvg_bear"
    BS_LIQUIDITY = "bs_liquidity"
    SS_LIQUIDITY = "ss_liquidity"
    BULLISH_BOS = "bullish_bos"
    BEARISH_BOS = "bearish_bos"
    BULL_CHOCH = "bull_choch"
    BEAR_CHOCH = "bear_choch"
    BULL_MSS = "bull_mss"
    BEAR_MSS = "bear_mss"


class KillZone(str, Enum):
    """ICT Killzones"""
    ASIA = "asia"
    LONDON = "london"
    NY = "ny"


# ─────────────────────────────────────────────────────────────
# DATA MODELS
# ─────────────────────────────────────────────────────────────

class OHLCV(BaseModel):
    """OHLCV candlestick data"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    
    @classmethod
    def from_dict(cls, data: dict) -> "OHLCV":
        """Create from dictionary"""
        return cls(**data)
    
    @classmethod
    def from_pandas(cls, df: pd.DataFrame) -> List["OHLCV"]:
        """Create from pandas DataFrame"""
        return [cls(**row) for row in df.to_dict("records")]
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return self.model_dump()


class CandleMetrics(BaseModel):
    """Calculated candlestick metrics"""
    body: float
    range_cand: float
    upper_wick: float
    lower_wick: float
    body_ratio: float
    upper_wick_ratio: float
    lower_wick_ratio: float
    is_bullish: bool
    is_bearish: bool
    is_doji: bool
    is_strong_bull: bool
    is_strong_bear: bool
    is_hammer: bool
    is_shooting_star: bool


class SwingLevels(BaseModel):
    """Swing high/low levels"""
    swing_high: float
    swing_low: float
    swing_high_bar: int
    swing_low_bar: int
    prev_swing_high: float
    prev_swing_low: float
    hh: bool = False      # Higher High
    hl: bool = False      # Higher Low
    lh: bool = False      # Lower High
    ll: bool = False      # Lower Low


class FVGZone(BaseModel):
    """Fair Value Gap zone"""
    type: str  # "bullish" or "bearish"
    top: float
    bottom: float
    mid: float
    start_time: datetime
    end_time: datetime
    is_active: bool = True
    is_filled: bool = False


class OrderBlock(BaseModel):
    """Order Block zone"""
    type: str  # "bullish" or "bearish"
    top: float
    bottom: float
    start_time: datetime
    end_time: datetime
    trigger_candle_time: datetime
    is_active: bool = True
    is_broken: bool = False


class LiquidityZone(BaseModel):
    """Liquidity zone"""
    type: str  # "bsl" or "ssl"
    price: float
    equal_highs: List[float] = []
    equal_lows: List[float] = []
    timestamp: datetime


class Indicators(BaseModel):
    """Technical indicators"""
    ema_9: float
    ema_21: float
    ema_bull_cross: bool
    ema_bear_cross: bool
    
    vwap: float
    price_above_vwap: bool
    
    rsi_14: float
    rsi_5m: float
    rsi_bullish: bool
    rsi_bearish: bool
    
    adx: float
    adx_strong: bool
    
    macd_main: float
    macd_signal: float
    macd_histogram: float
    macd_bullish: bool
    macd_bearish: bool
    
    atr_14: float
    volume_avg: float
    volume_high: bool


class MarketBias(BaseModel):
    """Market bias assessment"""
    direction: str  # "bull", "bear", "neutral"
    strength: str  # "strong", "mild", "weak"
    htf_bullish: bool
    htf_bearish: bool
    in_discount: bool
    in_premium: bool


class ScoreBreakdown(BaseModel):
    """Score breakdown for a signal"""
    smc_buy_score: int = 0
    smc_sell_score: int = 0
    sniper_bull_pct: float = 0.0
    sniper_bear_pct: float = 0.0
    
    # Individual SMC factors
    htf_bullish: bool = False
    htf_bearish: bool = False
    discount_zone: bool = False
    premium_zone: bool = False
    ssl_sweep: bool = False
    bsl_sweep: bool = False
    bull_engulfing: bool = False
    bear_engulfing: bool = False
    bull_pinbar: bool = False
    bear_pinbar: bool = False
    bull_rejection: bool = False
    bear_rejection: bool = False
    bull_displacement: bool = False
    bear_displacement: bool = False
    bull_choch: bool = False
    bear_choch: bool = False
    bull_mss: bool = False
    bear_mss: bool = False
    bull_bos: bool = False
    bear_bos: bool = False
    bull_fvg: bool = False
    bear_fvg: bool = False
    bull_ob: bool = False
    bear_ob: bool = False
    bull_liquidity: bool = False
    bear_liquidity: bool = False
    
    # Price Action
    pattern_score: int = 0
    patterns_found: List[str] = []
    
    # Killzone
    in_killzone: bool = False
    killzone_name: Optional[str] = None
    
    # OTE
    in_ote_zone: bool = False
    ote_level: Optional[float] = None


class TradingSignal(BaseModel):
    """Complete trading signal"""
    # ID
    signal_id: str
    timestamp: datetime
    
    # Symbol & Timeframe
    symbol: str
    timeframe: str
    
    # Direction
    direction: TradeDirection
    signal_type: SignalType
    
    # Price levels
    current_price: float
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    take_profit_3: float
    take_profit_4: float
    take_profit_5: float
    
    # Risk
    risk_amount: float
    risk_reward_1: float
    risk_reward_2: float
    risk_reward_3: float
    
    # Scores
    score_breakdown: ScoreBreakdown
    total_score: int
    confluence_count: int
    
    # Active zones
    active_fvgs: List[FVGZone] = []
    active_obs: List[OrderBlock] = []
    liquidity_zones: List[LiquidityZone] = []
    
    # Patterns
    patterns: List[str] = []
    
    # Market context
    market_bias: Optional[MarketBias] = None
    
    # Reasons
    signal_reasons: List[str] = []
    
    # Status
    is_active: bool = True
    triggered_at: Optional[datetime] = None
    
    # Confidence
    confidence: float = Field(ge=0.0, le=100.0)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class Position(BaseModel):
    """Open position"""
    position_id: str
    symbol: str
    direction: TradeDirection
    
    entry_price: float
    current_price: float
    stop_loss: float
    take_profit: float
    
    quantity: float
    leverage: int = 1
    
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    
    opened_at: datetime
    updated_at: datetime
    
    # Status
    tp1_hit: bool = False
    tp2_hit: bool = False
    tp3_hit: bool = False
    sl_hit: bool = False
    trailing_activated: bool = False
    
    # Partial closes
    tp1_closed_pct: float = 0.0
    tp2_closed_pct: float = 0.0
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class Trade(BaseModel):
    """Closed trade"""
    trade_id: str
    symbol: str
    direction: TradeDirection
    
    entry_price: float
    exit_price: float
    stop_loss: float
    
    quantity: float
    
    pnl: float
    pnl_pct: float
    risk_reward: float
    
    opened_at: datetime
    closed_at: datetime
    
    exit_reason: str  # "tp_hit", "sl_hit", "manual", "trailing"
    signal_type: SignalType
    total_score: int
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class Account(BaseModel):
    """Trading account"""
    balance: float
    equity: float
    available_balance: float
    
    open_positions_count: int
    total_pnl: float
    total_pnl_pct: float
    
    daily_pnl: float
    daily_pnl_pct: float
    
    win_rate: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    
    max_drawdown: float
    max_drawdown_pct: float
    
    consecutive_wins: int
    consecutive_losses: int


class ChartData(BaseModel):
    """Chart data for frontend"""
    symbol: str
    timeframe: str
    candles: List[OHLCV]
    
    # Calculated data
    indicators: Optional[Indicators] = None
    swing_levels: Optional[SwingLevels] = None
    active_zones: Dict[str, Any] = {}
    
    # Signals
    current_signal: Optional[TradingSignal] = None
    recent_signals: List[TradingSignal] = []
    
    # Scores
    scores: Optional[ScoreBreakdown] = None
