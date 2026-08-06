# QuantAI API Specification (FastAPI REST & WebSocket)

## Base URL
`http://127.0.0.1:8005`

---

## Public & Dashboard Endpoints

### 1. Telemetry Status
- **Method**: `GET /api/status`
- **Response**: `SystemStatus` JSON containing connection state, balance, equity, margin, spread, technical indicators, today's performance, and AI signal.

### 2. Market Data
- **Method**: `GET /api/market?symbol={symbol}&tf={timeframe}`
- **Response**: `{ symbol: string, timeframe: string, candles: Candle[], indicators: TechnicalIndicators }`

### 3. Control Center Status
- **Method**: `GET /api/control-center/status`
- **Response**: Sanitized operational readiness JSON showing execution mode, safeguards, account identity, risk parameters, and command ledger counts.

### 4. Control Center Settings Overrides
- **Method**: `POST /api/control-center/mode`
- **Payload**: `{ execution_mode: "DISABLED" | "PAPER" | "DEMO" | "LIVE" | "ENABLE", live_armed?: boolean, demo_armed?: boolean }`

- **Method**: `POST /api/control-center/kill-switch`
- **Payload**: `{ active: boolean }`

- **Method**: `POST /api/control-center/ai-auto-loop`
- **Payload**: `{ active: boolean }`

- **Method**: `POST /api/control-center/login`
- **Payload**: `{ login: number, password: string, server: string }`

### 5. Copilot Chat AI
- **Method**: `POST /api/copilot/chat`
- **Payload**: `{ message: string, symbol: string, timeframe: string }`
- **Response**: `{ role: "ai", text: string, time: string }`

### 6. News Analysis
- **Method**: `POST /api/news/analyze`
- **Payload**: `{ title: string, impact: string, actual: string, forecast: string, previous: string }`
- **Response**: Multi-source fundamental reasoning analysis JSON.

---

## Protected EA Bridge Endpoints
*Requires Header: `Authorization: Bearer <QUANTAI_BRIDGE_TOKEN>`*

### 1. Receive Telemetry & EA Heartbeat
- **Method**: `POST /api/telemetry`
- **Payload**: `{ symbol: string, balance: float, equity: float, margin: float, margin_free: float, profit: float, positions: int, ask: float, bid: float }`

### 2. Claim Pending Command
- **Method**: `POST /api/v1/bridge/commands/claim`
- **Payload**: `{ executor_id: string, symbol: string, magic: int, account_login: int, account_server: string, broker_company: string, trade_mode: string }`
- **Response**: `{ status: "CLAIMED" | "EMPTY", command: CommandRow | null }`

### 3. Record Execution Receipt
- **Method**: `POST /api/v1/bridge/commands/{command_id}/receipt`
- **Payload**: `{ executor_id: string, receipt_id: string, status: "EXECUTED" | "REJECTED" | "FAILED", retcode: int, result_message: string, order_ticket: int }`

### 4. Push Economic Calendar
- **Method**: `POST /api/v1/bridge/calendar`
- **Payload**: `{ source: "MT5_CALENDAR", events: CalendarEventItem[] }`

---

## Realtime WebSocket Stream
- **URL**: `ws://127.0.0.1:8005/ws/stream`
- **Cadence**: Full telemetry JSON broadcast every ~1s to connected clients.
