# QuantAI Data Flow & Cycle Specification

## End-to-End Execution Sequence

```text
[ Market Tick / Candle ]
          │
          ▼
   (MT5 Terminal)
          │
          ▼ Python mt5.copy_rates_from_pos() / symbol_info_tick()
   (FastAPI Backend)
          │
          ├── 1. Compute Technical Indicators (EMA20/50/200, RSI, ATR, MACD, Pivot)
          ├── 2. Generate Strategy Proposal (BUY / SELL / NO_TRADE)
          ├── 3. Evaluate AI Confluence & Multi-Source Fundamental Sentiment
          │
          ▼
    (RiskGate Engine)
          │
          ├── Pass? ──► NO ──► Return REJECT_* Reason & Log Event
          │
          ▼ YES
   (CommandStore Ledger)
          │
          ├── Create PENDING Command with Idempotency Key & TTL (10s)
          │
          ▼
    (MQL5 EA Bridge)  ◄── WebRequest POST /api/v1/bridge/commands/claim (Bearer Token)
          │
          ├── Claim Command ──► Atomically set state to CLAIMED
          ├── Validate Local Guards (Account Login/Server, Spread, Stops, Position Limit)
          │
          ├── Pass? ──► NO ──► WebRequest POST receipt (REJECTED)
          │
          ▼ YES
   (CTrade Execution)
          │
          ├── Execute Order on Broker Terminal (Buy / Sell / Modify / Close)
          │
          ▼
    (Receipt Posting) ──► WebRequest POST /api/v1/bridge/commands/{id}/receipt
          │
          ▼
   (CommandStore Ledger)
          │
          └── Atomically update state to EXECUTED / FAILED with Order Ticket & Retcode
          │
          ▼ WebSocket Push ~1s
  (Next.js Dashboard) ──► Render Updated Positions, Equity, Logs & Execution Toast
```

## Realtime Telemetry Data Flow

1. **Heartbeat & Telemetry**:
   - EA sends `POST /api/telemetry` every 1 sec -> Backend updates `_LAST_EA_HEARTBEAT`.
   - FastAPI `_telemetry_broadcaster` pushes telemetry JSON over WebSocket stream `ws://127.0.0.1:8005/ws/stream` to Next.js clients every 1s.

2. **Economic Calendar Data Flow**:
   - EA queries `CalendarValueHistory` from MT5 terminal built-in database.
   - Pushes USD macro events to `POST /api/v1/bridge/calendar`.
   - FastAPI caches events for 15 minutes and serves to UI via status endpoints.
