# QuantAI Dependency Graph & Module Interdependencies

## Component Dependency Graph

```text
[web/app/page.tsx]
      │
      ├──► [web/app/components/ControlCenter.tsx]
      │           │
      │           └──► [web/lib/api.ts]
      │                     │
      └─────────────────────┴──► HTTP / WebSocket (Port 8005)
                                       │
                                       ▼
                             [dashboard/server.py]
                                  │   │   │   │
        ┌─────────────────────────┘   │   │   └─────────────────────────┐
        ▼                             ▼   ▼                             ▼
[strategy_core.py]               [risk_gate.py]               [command_store.py]
        │                             │                                 │
        ▼                             ▼                                 ▼
(DecisionProposal)             (RiskProfiles)                  (SQLite quantai_commands)
                                      │
                                      ▼
                             [QuantAI_XAUUSD.mq5]
                                      │
                                      ▼
                              (MT5 CTrade API)
```

## Dependency Breakdown Matrix

| Module | Input Sources | Output Artifacts | External Dependencies | Internal Dependencies |
|---|---|---|---|---|
| `web/app/page.tsx` | Telemetry API, WS Stream, User Input | DOM, UI Charts, Order Triggers | React, Next.js, Lucide icons | `api.ts`, `ControlCenter.tsx` |
| `web/lib/api.ts` | Backend REST / WS Endpoints | Typed Data Objects, REST Responses | Fetch API, WebSocket | None |
| `dashboard/server.py` | MT5 Terminal, EA Telemetry, UI Actions | Telemetry JSON, WS Stream, API Responses | FastAPI, Uvicorn, MetaTrader5, Pydantic | `command_store`, `risk_gate`, `strategy_core`, `ws_hub`, `logging_config`, `performance` |
| `dashboard/risk_gate.py` | AccountSnapshot, SymbolSpec, Proposal | RiskDecision (Approved/Rejected) | Standard Python `math` | `strategy_core` |
| `dashboard/command_store.py` | Execution Intent Parameters | Command Row, Receipt Audit | SQLite3, threading, uuid | None |
| `dashboard/strategy_core.py` | OHLCV Rates, Technical Indicators | DecisionProposal | Standard Python | None |
| `QuantAI_XAUUSD.mq5` | HTTP WebRequest, MT5 Terminal Ticks | MQL5 CTrade Execution, HTTP Receipts | MT5 Terminal, MQL5 `Trade\Trade.mqh` | None |
