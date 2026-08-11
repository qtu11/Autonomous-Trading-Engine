"""
Trading System Configuration
Standalone version - no pydantic dependency
"""
import os
from typing import Optional, List


class TradingMode:
    PAPER = "paper"
    LIVE = "live"
    BACKTEST = "backtest"


class Broker:
    BINANCE = "binance"
    BINANCE_FUTURES = "binance_futures"
    FOREX_COM = "forex_com"
    IC_MARKETS = "ic_markets"


class Settings:
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
    MAX_RISK_PER_TRADE: float = 1.0
    MAX_DAILY_LOSS: float = 3.0
    MAX_CONSECUTIVE_LOSSES: int = 3
    MAX_OPEN_TRADES: int = 2
    POSITION_SIZE_METHOD: str = "fixed"
    
    # Broker API
    BINANCE_API_KEY: Optional[str] = os.getenv("BINANCE_API_KEY")
    BINANCE_API_SECRET: Optional[str] = os.getenv("BINANCE_API_SECRET")
    BINANCE_TESTNET: bool = True
    
    # Trading Parameters
    DEFAULT_TIMEFRAME: str = "1h"
    SYMBOLS: List[str] = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
    
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
    ADX_PERIOD: int = 14
    MACD_FAST: int = 12
    MACD_SLOW: int = 26
    MACD_SIGNAL: int = 9
    ATR_PERIOD: int = 14
    
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
    
    # Filters
    REQUIRE_ADX_FILTER: bool = True
    REQUIRE_VOLUME_FILTER: bool = True
    REQUIRE_HTF_CONFLUENCE: bool = True
    REQUIRE_PATTERN: bool = True
    KILLZONE_ONLY: bool = False
    
    def __init__(self):
        """Load from environment variables"""
        self._load_env()
    
    def _load_env(self):
        """Load settings from environment"""
        self.BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", self.BINANCE_API_KEY)
        self.BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", self.BINANCE_API_SECRET)
        
        debug = os.getenv("DEBUG")
        if debug is not None:
            self.DEBUG = debug.lower() in ('true', '1', 'yes')
        
        symbols = os.getenv("SYMBOLS")
        if symbols:
            self.SYMBOLS = [s.strip() for s in symbols.split(',')]


# Global settings instance
settings = Settings()
