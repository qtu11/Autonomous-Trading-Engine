# Qtus SMC-Sniper Trading System

AI-powered trading system using Smart Money Concepts (SMC), ICT concepts, Price Action patterns, and Sniper method technical analysis.

## Features

### 1. SMC Module (`app/modules/smc.py`)
- Market Structure Detection (HH, HL, LH, LL)
- Fair Value Gap (FVG) Detection
- Order Block (OB) Detection
- Liquidity Zone Detection (BSL, SSL)
- BOS/CHoCH/MSS Identification

### 2. ICT Module (`app/modules/ict.py`)
- Killzone Detection (London, NY, Asia)
- OTE Fibonacci Calculation (38.2%, 61.8%, 78.6%)
- Judas Swing Detection
- PO3/AMD Pattern Detection
- Daily/Weekly Levels (PDH, PDL, Pivot, R1-R3, S1-S3)

### 3. Price Action Module (`app/modules/price_action.py`)
- Pin Bar / Rejection
- Engulfing Patterns
- Inside Bar / Outside Bar
- Tweezer Top/Bottom
- Morning/Evening Star
- Three White Soldiers / Black Crows
- Displacement Candles

### 4. Sniper Module (`app/modules/sniper.py`)
- EMA Ribbon (9/21)
- VWAP Indicator
- ADX Trend Strength
- RSI Momentum
- MACD Analysis
- Volume Analysis
- Sniper Dual Score System (0-100%)

### 5. Scoring Engine (`app/services/scoring_engine.py`)
- Combined scoring from all modules
- Signal generation with entry, SL, TP levels
- Market bias analysis
- Confidence scoring

### 6. Broker Integration (`app/services/broker.py`)
- Binance Spot/Futures
- Paper Trading Mode
- Mock Broker for backtesting

## Quick Start

### 1. Install Dependencies
```bash
cd trading_system
pip install -r requirements.txt
```

### 2. Configure
Copy `.env.example` to `.env` and add your API keys:
```bash
cp .env.example .env
```

### 3. Run
```bash
# Start API server
python -m uvicorn app.main:app --reload --port 8000

# Or run directly
python app/main.py
```

### 4. Access Dashboard
Open browser: http://localhost:8000/dashboard

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API info |
| `/api/health` | GET | Health check |
| `/api/symbols` | GET | Available symbols |
| `/api/analyze/{symbol}` | GET | Full symbol analysis |
| `/api/candles/{symbol}` | GET | Candle data |
| `/api/signal/{symbol}` | GET | Current trading signal |
| `/api/dashboard` | GET | Dashboard data |
| `/ws` | WebSocket | Real-time updates |

## Example Response

```json
{
  "symbol": "BTCUSDT",
  "timeframe": "1h",
  "current_price": 105000.00,
  "market_bias": {
    "direction": "bull",
    "strength": "strong"
  },
  "scores": {
    "smc_buy_score": 8,
    "sniper_bull_pct": 71.4
  },
  "signal": {
    "direction": "long",
    "signal_type": "buy",
    "entry_price": 105000,
    "stop_loss": 104500,
    "take_profit_1": 105750,
    "risk_reward_1": 0.5,
    "risk_reward_2": 1.0,
    "total_score": 12,
    "confidence": 65.0
  }
}
```

## Trading Modes

1. **Paper Trading** (default) - Simulated trading
2. **Live Trading** - Real money (requires API keys)
3. **Backtest** - Historical testing

## Web Dashboard Features

- Real-time analysis for multiple symbols
- SMC scores and factors
- ICT levels and killzones
- Price action signals
- Sniper indicator scores
- Trading signals with entry/exit levels
- Responsive dark theme UI

## Project Structure

```
trading_system/
├── app/
│   ├── api/           # API routes
│   ├── core/          # Config, settings
│   ├── models/        # Data models
│   ├── modules/       # Trading modules
│   │   ├── price_action.py
│   │   ├── smc.py
│   │   ├── ict.py
│   │   └── sniper.py
│   ├── services/      # Business logic
│   │   ├── scoring_engine.py
│   │   ├── broker.py
│   │   └── bot.py
│   └── main.py        # FastAPI app
├── config/
├── frontend/
├── requirements.txt
└── .env.example
```

## License

MIT
