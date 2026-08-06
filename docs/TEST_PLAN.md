# QuantAI Test Plan & Quality Assurance Protocol

## Test Matrix Overview

### 1. Python Unit & Core Tests (`tests/test_quantai_core.py`)
- **Strategy Core**: Verification of BUY / SELL / NO_TRADE proposals under various trend and NaN indicator inputs.
- **RiskGate Policy**: Test rejection of non-finite inputs, disabled execution, daily loss limits, spread violations, and position limit caps.
- **Command Store**: Verification of unique command creation, idempotent retries, atomic claims, receipt recording, and state transitions (`PENDING` -> `CLAIMED` -> `EXECUTED`).
- **Performance Calculator**: Verification of win rate, drawdown, and profit factor algorithms.

### 2. Python Module Integration Tests (`tests/test_new_modules.py`)
- **WebSocket Manager (`ws_hub.py`)**: Connection, disconnection, and broadcast messaging.
- **Logging Config (`logging_config.py`)**: Event logging structure, line formatting, and log reader filter.

### 3. Frontend Typecheck & Build
- `npm --prefix web run lint`
- `npm --prefix web run build`

### 4. MQL5 Compilation & EA Verification
- MetaEditor64 CLI / UI compilation of `QuantAI_XAUUSD.mq5` -> `QuantAI_XAUUSD.ex5`.
- Verification of 0 compilation errors and 0 warnings.

### 5. System Health Check Automation (`start.ps1`)
- Automatic port release (3000 & 8005).
- Pre-flight MT5 terminal connectivity check.
- Verification of `/api/control-center/status` endpoint readiness before launching web dashboard.
