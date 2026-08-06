# QuantAI Ordered Task List & Implementation Roadmap

## Task Sequencing Rule
Tasks MUST be executed sequentially according to strictly ordered priority:
`Architecture` -> `Backend` -> `Trading` -> `MT5` -> `Realtime` -> `Frontend` -> `UI` -> `Performance` -> `Testing`

---

## Phase 9 & 10 Ordered Tasks

### Task 001: Architecture & Ledger Hardening
- **Objective**: Ensure SQLite WAL ledger connection pool safety, database schema migrations, and atomic transaction locks.
- **Files**: `dashboard/command_store.py`
- **Dependencies**: None
- **Acceptance Criteria**: CommandStore unit tests pass with concurrent thread claims.

### Task 002: Backend API & Fail-Closed RiskGate Audit
- **Objective**: Enforce strict validation on order execution endpoints, account identity verification, and multi-mode support (DEMO/LIVE).
- **Files**: `dashboard/server.py`, `dashboard/risk_gate.py`
- **Dependencies**: Task 001
- **Acceptance Criteria**: All fail-closed risk checks return proper `REJECT_*` code on invalid states.

### Task 003: Technical & AI Confluence Engine Verification
- **Objective**: Verify technical indicator calculation routines (RSI, ATR, EMA) and AI signal generation against NaN/null data.
- **Files**: `dashboard/strategy_core.py`, `dashboard/server.py`
- **Dependencies**: Task 002
- **Acceptance Criteria**: Returns `NO_TRADE` with reason code when tick data is missing or non-finite.

### Task 004: MT5 Expert Advisor Protocol & Guard Enhancements
- **Objective**: Ensure MQL5 EA compiles cleanly with 0 errors/warnings, handles reconnect watchdog, and executes orders with correct filling type.
- **Files**: `QuantAI_XAUUSD.mq5`
- **Dependencies**: Task 003
- **Acceptance Criteria**: Clean compilation with MetaEditor64; claims commands and posts valid receipts.

### Task 005: Realtime WebSocket & Heartbeat Synchronization
- **Objective**: Validate ~1s WebSocket telemetry broadcasting and EA heartbeat stale detection.
- **Files**: `dashboard/ws_hub.py`, `dashboard/server.py`, `web/lib/api.ts`
- **Dependencies**: Task 004
- **Acceptance Criteria**: Dashboard receives live socket updates and auto-reconnects when connection drops.

### Task 006: Frontend Control Center & Operator UI Interlocks
- **Objective**: Ensure Control Center modal reflects live account readiness, kill switch status, mode toggles, and Telegram configuration.
- **Files**: `web/app/components/ControlCenter.tsx`, `web/app/page.tsx`
- **Dependencies**: Task 005
- **Acceptance Criteria**: All buttons and switches operate smoothly; changes persist to backend.

### Task 007: UI Aesthetic & Chart Integration Polish
- **Objective**: Verify single-screen Bloomberg Terminal layout, SVG candlestick chart pan/zoom, and live ticker formatting.
- **Files**: `web/app/page.tsx`, `web/app/globals.css`
- **Dependencies**: Task 006
- **Acceptance Criteria**: Flawless visual hierarchy, 0 layout shifts, crisp color palette.

### Task 008: Automated Test Suite & System Verification
- **Objective**: Run Python unittest suite, Next.js typecheck/build, and full system end-to-end sanity check.
- **Files**: `tests/test_quantai_core.py`, `tests/test_new_modules.py`
- **Dependencies**: Task 007
- **Acceptance Criteria**: 100% tests pass; Next.js build succeeds cleanly.
