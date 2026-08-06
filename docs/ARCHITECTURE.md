# QuantAI Architecture Specification

## Overview
GoldQuant AI / QuantAI is a high-frequency trading desk & AI execution bridge system designed for MetaTrader 5 (MT5) on XAUUSD (Gold).

## High-Level System Architecture

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                            NEXT.JS DASHBOARD                                │
│                     (React 19 / TypeScript / Tailwind)                      │
│                                                                             │
│   ┌───────────────────────┐  ┌──────────────────┐  ┌────────────────────┐   │
│   │ Real TradingView SVG  │  │ Live Telemetry   │  │ Control Center     │   │
│   │ Chart Component       │  │ Monitoring       │  │ Multi-Interlock UI │   │
│   └───────────────────────┘  └──────────────────┘  └────────────────────┘   │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ WebSocket stream / HTTP REST
┌──────────────────────────────────────▼──────────────────────────────────────┐
│                            FASTAPI BACKEND                                  │
│                        (Python 3.11 / AsyncIO)                              │
│                                                                             │
│  ┌───────────────────────┐  ┌──────────────────┐  ┌─────────────────────┐  │
│  │ MT5 Read Gateway      │  │ Technical        │  │ Multi-Source AI     │  │
│  │ (Tick/Candle/Account) │  │ Indicator Core   │  │ Decision Engine     │  │
│  └───────────┬───────────┘  └────────┬─────────┘  └──────────┬──────────┘  │
│              │                       │                       │              │
│              └───────────────────────┼───────────────────────┘              │
│                                      ▼                                      │
│                             ┌──────────────────┐                            │
│                             │ Fail-Closed      │                            │
│                             │ RiskGate         │                            │
│                             └────────┬─────────┘                            │
│                                      │ (Approved Proposals Only)            │
│                                      ▼                                      │
│                             ┌──────────────────┐    ┌────────────────────┐  │
│                             │ Command Store    │───►│ SQLite WAL Database│  │
│                             │ Ledger           │    │ (quantai_commands) │  │
│                             └────────┬─────────┘    └────────────────────┘  │
└──────────────────────────────────────┼──────────────────────────────────────┘
                                       │ Authenticated Local REST Bridge API
┌──────────────────────────────────────▼──────────────────────────────────────┐
│                         METATRADER 5 EXPERT ADVISOR                         │
│                        (QuantAI_XAUUSD.mq5 / MQL5)                          │
│                                                                             │
│  ┌───────────────────────┐  ┌──────────────────┐  ┌─────────────────────┐  │
│  │ Authenticated Lease   │  │ Local Execution  │  │ CTrade Execution    │  │
│  │ & Claim Protocol      │──► Guard Validation  │──► Authority            │  │
│  └───────────────────────┘  └──────────────────┘  └─────────────────────┘  │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ FIX Protocol / Native Broker API
┌──────────────────────────────────────▼──────────────────────────────────────┐
│                               BROKER TERMINAL                               │
│                         (Exness / MetaTrader 5)                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Core Module Boundaries & Responsibilities

1. **Next.js Web Dashboard (`web/`)**
   - Renders realtime market telemetry, SVG candlestick chart, active positions, and trade history.
   - Provides operator Control Center for arming execution, toggling kill-switch, adjusting risk policies, and viewing audit logs.
   - Strictly forbidden from executing broker commands directly.

2. **FastAPI Backend Server (`dashboard/server.py`)**
   - Bridges MT5 Python API for telemetry, rates, positions, account info, and economic calendar.
   - Evaluates technical confluence and fundamental AI sentiment.
   - Enforces fail-closed risk management via RiskGate.
   - Writes immutable, idempotent execution commands to SQLite WAL ledger.

3. **Command Ledger Store (`dashboard/command_store.py`)**
   - SQLite WAL database holding command lifecycle: `PENDING` -> `CLAIMED` -> `EXECUTED` / `REJECTED` / `FAILED` / `EXPIRED`.
   - Prevents duplicate order execution through unique idempotency keys.

4. **Risk Gate (`dashboard/risk_gate.py`)**
   - Evaluates account equity, margin free, spread, stop loss/take profit directions, daily loss caps, position limits, and volume step quantization.

5. **MQL5 EA Bridge (`QuantAI_XAUUSD.mq5`)**
   - Polls FastAPI bridge every 1 second over HTTP WebRequest with Bearer Token authentication.
   - Validates account login, server, symbol, spread, and stop levels locally before execution.
   - Executes trade via MQL5 `CTrade` and posts receipt back to backend.
