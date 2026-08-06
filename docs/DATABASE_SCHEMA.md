# QuantAI Database Schema & Audit Ledger Specification

## Database Engine
- **Engine**: SQLite 3
- **File Path**: `dashboard/quantai_commands.sqlite3`
- **Journal Mode**: WAL (Write-Ahead Logging)
- **Foreign Keys**: Enabled (`PRAGMA foreign_keys=ON`)

---

## 1. Table `execution_commands`
Stores all trade directives issued by the decision engine or manual UI triggers.

```sql
CREATE TABLE IF NOT EXISTS execution_commands (
    command_id TEXT PRIMARY KEY,           -- UUID v4
    idempotency_key TEXT NOT NULL UNIQUE,  -- Unique hash preventing duplicates
    action TEXT NOT NULL,                  -- BUY | SELL | MODIFY_SLTP | CLOSE_POSITION | CLOSE_ALL | CANCEL_PENDING
    symbol TEXT NOT NULL,                  -- e.g. XAUUSDm
    magic INTEGER NOT NULL,                -- e.g. 888999
    volume REAL,                           -- Lot size (e.g. 0.10)
    stop_loss REAL,                        -- Stop Loss price
    take_profit REAL,                      -- Take Profit price
    reason TEXT NOT NULL,                  -- Decision reason or trigger source
    state TEXT NOT NULL,                   -- PENDING | CLAIMED | EXECUTED | REJECTED | FAILED | EXPIRED
    created_at TEXT NOT NULL,              -- ISO8601 UTC timestamp
    expires_at TEXT NOT NULL,              -- ISO8601 UTC timestamp (TTL)
    claimed_by TEXT,                       -- EA Executor ID
    claimed_at TEXT,                       -- ISO8601 UTC timestamp
    lease_expires_at TEXT,                 -- ISO8601 UTC timestamp (Lease TTL)
    executed_at TEXT,                      -- ISO8601 UTC timestamp
    order_ticket INTEGER,                  -- Broker order ticket
    deal_ticket INTEGER,                   -- Broker deal ticket
    retcode INTEGER,                       -- Broker return code (e.g. 10009 TRADE_RETCODE_DONE)
    result_message TEXT,                   -- Broker result description
    receipt_id TEXT UNIQUE                 -- Unique receipt hash from EA
);
```

---

## 2. Table `execution_events`
Stores full immutable lifecycle audit history for every command transition.

```sql
CREATE TABLE IF NOT EXISTS execution_events (
    event_id TEXT PRIMARY KEY,             -- UUID v4
    command_id TEXT NOT NULL,              -- Foreign Key to execution_commands(command_id)
    event_type TEXT NOT NULL,              -- CREATED | CLAIMED | RECEIPT | EXPIRED
    created_at TEXT NOT NULL,              -- ISO8601 UTC timestamp
    payload_json TEXT NOT NULL,            -- Detailed event payload JSON
    FOREIGN KEY(command_id) REFERENCES execution_commands(command_id)
);
```

---

## 3. Persistent User Control Config (`dashboard/user_control_config.json`)
Stores persistent operator settings across server restarts:
- `execution_mode`: Runtime mode ("DISABLED", "DEMO", "LIVE", "ENABLE").
- `live_armed`: Boolean safety arm.
- `demo_armed`: Boolean demo arm.
- `kill_switch`: Master emergency stop toggle.
- `enable_trading`: Master execution enable toggle.
- `ai_auto_loop`: Autonomous decision loop toggle.
- `mt5_login`, `mt5_password`, `mt5_server`: Account credentials.
- `telegram_bot_token`, `telegram_chat_id`, `telegram_enabled`: Instant alert settings.
