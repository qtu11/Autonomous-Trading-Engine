# Autonomous Trading Engine (ATE) - Architecture & System Specification

## 1. Executive Summary & Overview
The **Autonomous Trading Engine (ATE)** (also known as GoldQuant AI) is a hybrid quantitative auto-trading platform built specifically for XAUUSD (Gold) on MetaTrader 5. The platform enforces strict **separation of concerns** across three primary layers:
1. **Visualization & Operator Interface**: Next.js 16 (React 19 / TypeScript) Dashboard.
2. **Quantitative Analysis, AI Router & Risk Control**: FastAPI (Python 3.14) Backend with 15-Point RiskGate.
3. **Broker Execution Authority**: MetaTrader 5 Expert Advisor (`QuantAI_XAUUSD.mq5` / `ATE_XAUUSD.mq5`).

---

## 2. System Architecture & Subsystems

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        NEXT.JS WEB DASHBOARD                                │
│                     (React 19 / TypeScript)                                 │
│  ┌───────────────────────┐  ┌──────────────────┐  ┌────────────────────┐   │
│  │ Chart SVG Realtime    │  │ Telemetry Live   │  │ Control Center     │   │
│  │ (Bloomberg Terminal)  │  │ Monitoring       │  │ Multi-Interlock UI │   │
│  └───────────────────────┘  └──────────────────┘  └────────────────────┘   │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ WebSocket (WS) / REST API
┌──────────────────────────────────────▼──────────────────────────────────────┐
│                          FASTAPI BACKEND SERVER                             │
│                        (Python 3.14 / AsyncIO)                              │
│  ┌───────────────────────┐  ┌──────────────────┐  ┌─────────────────────┐  │
│  │ MT5 Telemetry Gateway │  │ Pattern/Strategy │  │ Multi-AI Decision   │  │
│  │ (Tick/Candle/Account) │  │ Engine (72+)     │  │ Router (Failover)   │  │
│  └───────────────────────┘  └──────────────────┘  └─────────────────────┘  │
│                                                                             │
│                              ┌──────────────────────┐                       │
│                              │  RiskGate (Fail-     │                       │
│                              │  Closed 15-Point)    │                       │
│                              └──────────┬───────────┘                       │
│                                         │ Approved Proposals Only           │
│                                         ▼                                   │
│                              ┌──────────────────────┐  ┌────────────────┐  │
│                              │ Command Store Ledger │──► SQLite WAL DB   │  │
│                              │ (Idempotent Ledger)  │  │ (ate_commands) │  │
│                              └──────────────────────┘  └────────────────┘  │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Authenticated Polling REST Bridge
┌──────────────────────────────────────▼──────────────────────────────────────┐
│                       METATRADER 5 EXPERT ADVISOR                           │
│                       (ATE_XAUUSD.mq5 / MQL5)                               │
│  ┌───────────────────────┐  ┌──────────────────┐  ┌─────────────────────┐  │
│  │ Bearer Token Auth     │──► Local Guard      │──► CTrade Execution │  │
│  │ Claim Protocol        │   Validation        │   Authority         │  │
│  └───────────────────────┘  └──────────────────┘  └─────────────────────┘  │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Broker API
┌──────────────────────────────────────▼──────────────────────────────────────┐
│                               BROKER TERMINAL                               │
│                            (MetaTrader 5 Terminal)                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. End-to-End Data Flow

```
[MT5 EA Telemetry] ──(1s Polling/Post)──► [FastAPI Telemetry Gateway]
                                                    │
                                                    ▼
[Market Structure & Signal Engines] ◄── [Candle & Technical Normalizer]
                 │
                 ▼ (Strategy Signal)
[Multi-AI Router] (OpenCode / Gemini / OpenAI / DeepSeek)
                 │
                 ▼ (Raw Proposal)
[RiskGate 15-Point Filter] ──(Fail-Closed Verification)──► If PASS
                                                                │
                                                                ▼
[Command Store Ledger] ◄──(Insert Idempotent Record PENDING)────┘
         ▲
         │ (1s Claim Poll)
[MQL5 EA Execution Authority] ──(Execute via CTrade)──► [Broker Terminal]
         │
         └──────────(Send Receipt: EXECUTED / FAILED)─────────► [Ledger Update]
```

---

## 4. Database Ledger Schema (SQLite WAL)

Commands are tracked in `dashboard/ate_commands.sqlite3` (`ate_commands` table):

| Field | Type | Constraint | Description |
|-------|------|------------|-------------|
| `command_id` | TEXT | PRIMARY KEY | Unique UUID v4 identifying the command |
| `idempotency_key` | TEXT | UNIQUE, NOT NULL | Deterministic SHA256 hash derived from trade parameters |
| `symbol` | TEXT | NOT NULL | Target symbol (e.g. `XAUUSD`) |
| `action` | TEXT | NOT NULL | Operation: `BUY`, `SELL`, `CLOSE`, `CLOSE_ALL`, `MODIFY_TPSL` |
| `volume` | REAL | NOT NULL | Lot size |
| `price` | REAL | DEFAULT 0.0 | Entry price (for pending orders or market reference) |
| `sl` | REAL | DEFAULT 0.0 | Stop loss price |
| `tp` | REAL | DEFAULT 0.0 | Take profit price |
| `status` | TEXT | NOT NULL | `PENDING` -> `CLAIMED` -> `EXECUTED` / `REJECTED` / `FAILED` / `EXPIRED` |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Record creation timestamp |
| `claimed_at` | TIMESTAMP | NULLABLE | Timestamp when MQL5 EA claimed the command |
| `executed_at` | TIMESTAMP | NULLABLE | Timestamp when execution receipt was confirmed |
| `receipt_json` | TEXT | NULLABLE | Full execution output payload from MT5 CTrade |

---

## 5. External Integrations & MQL5 EA Bridge

- **Communication Protocol**: HTTP REST JSON polling over local loopback / direct IP.
- **Authentication**: `Authorization: Bearer <QUANTAI_BRIDGE_TOKEN>`.
- **Claim Endpoint**: `POST /api/v1/bridge/commands/claim` - EA retrieves oldest `PENDING` command and transitions it atomically to `CLAIMED`.
- **Receipt Endpoint**: `POST /api/v1/bridge/commands/{id}/receipt` - EA reports broker ticket, execution price, error code, and latency back to backend ledger.

---

## 6. Auditability & Idempotency Guarantees

1. **Idempotency Key**: Generated as `SHA256(symbol + action + volume + sl + tp + timestamp_window_bucket)`. duplicate requests during network retries hit the UNIQUE constraint and return existing command status without duplicate execution.
2. **Audit Log**: Every state change in `command_store.py` produces structured JSON log entries and immutable WAL database rows.

---

## 7. Failure Modes & RiskGate Fail-Closed Behavior

- **Fail-Closed Principle**: If any error, unexpected input, network timeout, AI API failure, or out-of-bounds parameter occurs, RiskGate **REJECTS** the trade immediately.
- **15-Point Check Suite**:
  1. Operating Mode Check (`DEMO` / `LIVE` / `DISABLED`)
  2. Master Kill-Switch Check
  3. Free Margin & Leverage Sufficiency
  4. Max Equity Drawdown Limit
  5. Maximum Daily Loss Cap
  6. Maximum Open Positions Limit
  7. Symbol & Trade Hours Permissibility
  8. Spread Boundary Check (Max allowable spread for XAUUSD)
  9. Valid Stop Loss & Take Profit Direction (SL < Price < TP for BUY, TP < Price < SL for SELL)
  10. Minimum/Maximum Lot Size Limits
  11. Lot Size Step Quantization
  12. Economic High-Impact News Filter (Killzone Pause)
  13. Maximum Slippage Allowance
  14. Bridge Authorization & Health Verification
  15. Command Ledger Idempotency & TTL Expiration (Default 30s TTL)
