# 📚 API DOCUMENTATION
## Autonomous Trading Engine (ATE)

---

## BASE URL
```
Production: https://api.yourdomain.com
Local: http://localhost:8000
```

---

## AUTHENTICATION

### Bearer Token
All protected endpoints require:
```
Authorization: Bearer <your-token>
```

### Rate Limiting
- **Public endpoints**: 100 requests/minute
- **Protected endpoints**: 60 requests/minute
- Headers returned: `X-RateLimit-Remaining`

---

## PUBLIC ENDPOINTS

### Health Check
```http
GET /api/health
```

**Response:**
```json
{
  "status": "ok",
  "timestamp": "2026-08-11T10:00:00Z"
}
```

---

### Market Data
```http
GET /api/market?symbol=XAUUSD&tf=M15
```

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| symbol | string | No | Trading symbol (default: XAUUSD) |
| tf | string | No | Timeframe: M1, M5, M15, M30, H1, H4, D1 |

**Response:**
```json
{
  "symbol": "XAUUSD",
  "timeframe": "M15",
  "candles": [
    {
      "t": "10:00",
      "ts": "2026-08-11T10:00:00",
      "o": 2345.50,
      "h": 2350.00,
      "l": 2344.00,
      "c": 2348.50,
      "v": 1500
    }
  ],
  "indicators": {
    "rsi": 55.5,
    "atr": 12.3,
    "ema20": 2345.00,
    "ema50": 2340.00,
    "ema200": 2320.00,
    "macd": "0.85",
    "stoch": "65.4",
    "pivot": 2347.00,
    "r1": 2355.00,
    "r2": 2362.00,
    "s1": 2340.00,
    "s2": 2333.00
  }
}
```

---

### Analyze (Full Analysis)
```http
GET /api/analyze/{symbol}?timeframe=M15&count=2000
```

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| symbol | string | Yes | Trading symbol |
| timeframe | string | No | Timeframe (default: M15) |
| count | int | No | Number of candles (default: 2000, max: 5000) |

**Response:**
```json
{
  "symbol": "XAUUSD",
  "timeframe": "M15",
  "candle_count": 2000,
  "current_price": 2348.50,
  "method1_indicator": {
    "direction": "long",
    "ema_alignment": "bullish",
    "rsi": 55.5,
    "signal": "BUY"
  },
  "method2_smc": {
    "direction": "long",
    "bos": "bullish",
    "ob_detected": true,
    "fvg_detected": false
  },
  "method3_ict": {
    "in_killzone": true,
    "active_kz": "london",
    "ote_zone": "in_zone",
    "daily_levels": {...}
  },
  "method4_priceaction": {
    "direction": "neutral",
    "pattern_score": 2,
    "patterns": ["hammer"]
  },
  "method5_ultra": {
    "direction": "long",
    "strength": "STRONG",
    "buy_confluence": 8,
    "sell_confluence": 2,
    "recommended_signal": "BUY"
  }
}
```

---

### Signals
```http
GET /api/signals?symbol=XAUUSD&is_active=true&limit=100
```

**Response:**
```json
{
  "signals": [
    {
      "signal_id": "SIG-202608111000-ABC123",
      "symbol": "XAUUSD",
      "timeframe": "M15",
      "direction": "long",
      "signal_type": "buy",
      "entry_price": 2348.50,
      "stop_loss": 2340.00,
      "take_profit_1": 2355.00,
      "confidence": 78.5,
      "total_score": 8,
      "is_active": true,
      "created_at": "2026-08-11T10:00:00Z"
    }
  ]
}
```

---

### Positions
```http
GET /api/positions?symbol=XAUUSD
```

**Response:**
```json
{
  "positions": [
    {
      "position_id": "POS-20260811-001",
      "symbol": "XAUUSD",
      "direction": "long",
      "entry_price": 2345.00,
      "current_price": 2348.50,
      "unrealized_pnl": 35.00,
      "unrealized_pnl_pct": 1.4,
      "sl_hit": false,
      "tp1_hit": false,
      "opened_at": "2026-08-11T09:30:00Z"
    }
  ]
}
```

---

### Trades (History)
```http
GET /api/trades?symbol=XAUUSD&limit=100
```

**Response:**
```json
{
  "trades": [
    {
      "trade_id": "TRD-20260810-001",
      "symbol": "XAUUSD",
      "direction": "long",
      "entry_price": 2330.00,
      "exit_price": 2345.00,
      "pnl": 150.00,
      "pnl_pct": 6.0,
      "exit_reason": "tp_hit",
      "closed_at": "2026-08-10T15:00:00Z"
    }
  ]
}
```

---

### Account
```http
GET /api/account
```

**Response:**
```json
{
  "balance": 10500.00,
  "equity": 10535.00,
  "available_balance": 9500.00,
  "open_positions_count": 2,
  "total_pnl": 500.00,
  "win_rate": 65.5,
  "total_trades": 20,
  "max_drawdown": -250.00
}
```

---

### Dashboard
```http
GET /api/dashboard?symbol=XAUUSD&timeframe=M15
```

**Response:**
```json
{
  "symbol": "XAUUSD",
  "timeframe": "M15",
  "candles": 2000,
  "methods": {
    "indicator": {...},
    "smc": {...},
    "ict": {...},
    "priceaction": {...},
    "ultra": {...}
  }
}
```

---

## PROTECTED ENDPOINTS (Require Authorization)

### Create Signal
```http
POST /api/signals
Authorization: Bearer <operator-token>

{
  "symbol": "XAUUSD",
  "direction": "long",
  "entry_price": 2348.50,
  "stop_loss": 2340.00,
  "take_profit": 2360.00,
  "confidence": 75.0,
  "total_score": 8
}
```

---

### Place Order
```http
POST /api/order/buy
Authorization: Bearer <operator-token>

{
  "symbol": "XAUUSD",
  "quantity": 0.1,
  "entry_price": 2348.50,
  "stop_loss": 2340.00,
  "take_profit": 2360.00
}
```

---

### Close Position
```http
POST /api/order/close
Authorization: Bearer <operator-token>

{
  "position_id": "POS-20260811-001"
}
```

---

### Kill Switch
```http
POST /api/control-center/kill-switch
Authorization: Bearer <operator-token>

{
  "action": "arm" | "disarm" | "kill"
}
```

---

### Update Risk Profile
```http
POST /api/control-center/risk
Authorization: Bearer <operator-token>

{
  "max_risk_per_trade": 1.0,
  "max_daily_loss": 3.0,
  "max_open_trades": 2,
  "position_size_method": "fixed"
}
```

---

## ERROR RESPONSES

### Validation Error (422)
```json
{
  "error": "VALIDATION_ERROR",
  "message": "Invalid request data",
  "details": [
    {
      "field": "symbol",
      "message": "Invalid symbol format",
      "type": "value_error"
    }
  ]
}
```

### Authentication Error (401)
```json
{
  "error": "OPERATOR_AUTH_REQUIRED",
  "message": "Cần token quản trị"
}
```

### Rate Limited (429)
```json
{
  "error": "Too Many Requests",
  "message": "Rate limit exceeded. Try again in a few seconds.",
  "retry_after": 60
}
```

### Server Error (500)
```json
{
  "error": "INTERNAL_ERROR",
  "message": "An unexpected error occurred. Please try again later."
}
```

---

## WEBSOCKET

### Real-time Stream
```javascript
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(data);
};

// Receive:
{
  "symbol": "XAUUSD",
  "candles": 1000,
  "price": 2348.50,
  "method1": {...},
  "method2": {...},
  "method3": {...},
  "method4": {...},
  "method5": {...}
}
```

---

## SYMBOLS

| Symbol | Name | Type |
|--------|------|------|
| XAUUSD | Gold | Spot |
| XAUUSDm | Gold (Futures) | Futures |
| BTCUSDT | Bitcoin | Spot |
| ETHUSDT | Ethereum | Spot |
| BNBUSDT | Binance Coin | Spot |
| SOLUSDT | Solana | Spot |

---

## TIMEFRAMES

| TF | Name | Description |
|----|------|-------------|
| M1 | 1 Minute | Scalping |
| M5 | 5 Minutes | Short-term |
| M15 | 15 Minutes | Medium-term |
| M30 | 30 Minutes | Medium-term |
| H1 | 1 Hour | Intraday |
| H4 | 4 Hours | Swing |
| D1 | Daily | Position |

