# QuantAI Modules Breakdown & Detailed Specifications

## 1. Web Frontend Module (`web/`)
- `web/app/page.tsx`: Single-screen Bloomberg Trading Desk Terminal UI. Displays live market ticker, candlestick chart, AI intelligence matrix, active positions table, trade history, news calendar, and copilot chat.
- `web/app/components/ControlCenter.tsx`: Operational control modal. Handles arming (DEMO/LIVE), kill switch toggle, risk policy overrides, MT5 account login setup, Telegram bot alerts configuration, and audit logs viewer.
- `web/lib/api.ts`: API client layer with typed TypeScript interfaces for all backend endpoints and WebSocket stream handler with auto-reconnect backoff.

## 2. FastAPI Backend Module (`dashboard/`)
- `dashboard/server.py`: Core FastAPI application entry point. Handles MT5 terminal attachment, telemetry generation, AI decision loop, execution interlocks, HTTP routing, CORS, and lifespan lifecycle.
- `dashboard/command_store.py`: Idempotent command store backed by SQLite WAL database (`quantai_commands.sqlite3`). Manages atomic command creation, lease claims, and execution receipts.
- `dashboard/risk_gate.py`: Safety evaluation engine. Evaluates equity, free margin, daily drawdown limit, position caps, bid/ask spread caps, stop loss / take profit direction, and lot size step quantization.
- `dashboard/risk_profiles.py`: Asset-specific risk profiles (e.g. XAUUSDm max spread 0.50, EURUSD max spread 0.0002).
- `dashboard/strategy_core.py`: Pure technical strategy engine evaluating EMA20/50/200 trend, RSI momentum, and ATR volatility confluence.
- `dashboard/performance.py`: Realtime equity curve and KPI calculator (Win Rate, Profit Factor, Max Drawdown, Recovery Factor).
- `dashboard/ws_hub.py`: High-concurrency WebSocket connection manager for broadcasting telemetry updates (~1s cadence).
- `dashboard/logging_config.py`: Structured JSON logger writing per-line event logs to `logs/quantai_YYYYMMDD.log`.

## 3. MQL5 Expert Advisor Module (`QuantAI_XAUUSD.mq5`)
- MQL5 Expert Advisor compiled to `QuantAI_XAUUSD.ex5`.
- Timer-driven execution bridge running every 1 second (`EventSetTimer(1)`).
- Submits telemetry to `/api/telemetry` and claims pending commands from `/api/v1/bridge/commands/claim`.
- Performs local safety verification before invoking `CTrade.Buy()`, `CTrade.Sell()`, `CTrade.PositionModify()`, `CTrade.PositionClose()`, or `CTrade.OrderDelete()`.
- Posts execution receipt back to `/api/v1/bridge/commands/{command_id}/receipt`.
