"""
Trading System Configuration
All settings centralized for easy configuration
"""
from pydantic_settings import BaseSettings
from typing import Optional
from enum import Enum


class TradingMode(str, Enum):
    """Trading mode selection"""
    PAPER = "paper"          # Paper trading (no real money)
    LIVE = "live"            # Live trading
    BACKTEST = "backtest"    # Historical backtesting


class Broker(str, Enum):
    """Supported brokers"""
    BINANCE = "binance"
    BINANCE_FUTURES = "binance_futures"
    FOREX_COM = "forex_com"
    IC_MARKETS = "ic_markets"


class Settings(BaseSettings):
    """Application settings"""
    
    # App
    APP_NAME: str = "Qtus Trading System"
    VERSION: str = "2.0.0"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Trading Mode
    TRADING_MODE: TradingMode = TradingMode.PAPER
    SELECTED_BROKER: Broker = Broker.BINANCE
    
    # Risk Management
    MAX_RISK_PER_TRADE: float = 1.0        # % of equity
    MAX_DAILY_LOSS: float = 3.0            # % of equity
    MAX_CONSECUTIVE_LOSSES: int = 3
    MAX_OPEN_TRADES: int = 2
    POSITION_SIZE_METHOD: str = "fixed"    # fixed, kelly, martingale
    
    # Broker API - BINANCE
    BINANCE_API_KEY: Optional[str] = None
    BINANCE_API_SECRET: Optional[str] = None
    BINANCE_TESTNET: bool = True
    
    # Broker API - FOREX
    FOREX_API_KEY: Optional[str] = None
    FOREX_API_SECRET: Optional[str] = None
    
    # Trading Parameters
    DEFAULT_TIMEFRAME: str = "1h"
    SYMBOLS: list = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
    
    # SMC Settings
    SWING_LOOKBACK: int = 20
    FVG_LOOKBACK: int = 3
    EQUAL_TOLERANCE: float = 0.001
    
    # ICT Settings
    LONDON_KZ_START: str = "08:00"
    LONDON_KZ_END: str = "09:00"
    NY_KZ_START: str = "13:30"
    NY_KZ_END: str = "14:30"
    ASIA_KZ_START: str = "00:00"
    ASIA_KZ_END: str = "09:00"
    
    # OTE Fibonacci
    OTE_382: float = 0.382
    OTE_618: float = 0.618
    OTE_786: float = 0.786
    
    # Sniper Settings
    EMA_9_PERIOD: int = 9
    EMA_21_PERIOD: int = 21
    RSI_PERIOD: int = 14
    RSI_5M_PERIOD: int = 14
    ADX_PERIOD: int = 14
    MACD_FAST: int = 12
    MACD_SLOW: int = 26
    MACD_SIGNAL: int = 9
    ATR_PERIOD: int = 14
    VOL_SMA_PERIOD: int = 20
    
    # Signal Thresholds
    ADX_STRONG_THRESHOLD: float = 25.0
    RSI_NEUTRAL: float = 50.0
    SCORE_MIN_STRONG: int = 8
    SCORE_MIN_VALID: int = 6
    
    # TP/SL
    SL_ATR_MULTIPLIER: float = 1.5
    TP1_RISK_MULT: float = 0.5
    TP2_RISK_MULT: float = 1.0
    TP3_RISK_MULT: float = 2.0
    TP4_RISK_MULT: float = 3.0
    TP5_RISK_MULT: float = 5.0
    
    # Partial TP
    PARTIAL_TP1_PERCENT: float = 0.25
    PARTIAL_TP2_PERCENT: float = 0.25
    
    # Trailing Stop
    TRAILING_START_R: float = 2.0
    TRAILING_DISTANCE_R: float = 1.0
    
    # Filters
    REQUIRE_ADX_FILTER: bool = True
    REQUIRE_VOLUME_FILTER: bool = True
    REQUIRE_HTF_CONFLUENCE: bool = True
    REQUIRE_PATTERN: bool = True
    REQUIRE_FVG: bool = False
    REQUIRE_OB: bool = False
    REQUIRE_LIQUIDITY_SWEEP: bool = False
    KILLZONE_ONLY: bool = False
    
    # WebSocket
    WS_HEARTBEAT: int = 30
    
    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()
