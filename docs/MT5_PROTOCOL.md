# QuantAI MT5 MQL5 Execution Protocol Specification

## Overview
`QuantAI_XAUUSD.mq5` serves as the sole broker execution authority. No Python script, browser client, or third-party process invokes broker trades directly.

## Communication Protocol

### 1. Telemetry & Heartbeat (`POST /api/telemetry`)
- Sent every 1 second via MQL5 `WebRequest()`.
- Headers: `Authorization: Bearer <QUANTAI_BRIDGE_TOKEN>`.
- Payload includes account balance, equity, margin, margin free, profit, open positions, ask, bid.

### 2. Command Claim (`POST /api/v1/bridge/commands/claim`)
- Polled every 1 second.
- Submits executor identity, symbol, magic number, account login, server, company, and trade mode.
- If backend returns `"status": "CLAIMED"`, EA parses command fields (`action`, `volume`, `stop_loss`, `take_profit`, `reason`).

### 3. Local Guard Verification (Fail-Closed)
Before calling `CTrade`, EA verifies:
1. `InpExecutionEnabled == true` and `IsAuthorizedDemoEnvironment() == true`.
2. Symbol equals `InpSymbol` ("XAUUSDm") and Magic equals `InpMagicNumber` (888999).
3. Current spread <= `InpMaxSpread` (0.50).
4. `MatchingPositionCount() < InpMaxPositions` (1).
5. Stop Loss / Take Profit distance >= `SYMBOL_TRADE_STOPS_LEVEL` and `SYMBOL_TRADE_FREEZE_LEVEL`.
6. Volume is within broker limits (`SYMBOL_VOLUME_MIN`, `SYMBOL_VOLUME_MAX`, `SYMBOL_VOLUME_STEP`).

### 4. Trade Execution via MQL5 CTrade
- `m_trade.SetTypeFillingBySymbol(InpSymbol)` automatically resolves broker execution filling mode (`ORDER_FILLING_FOK`, `ORDER_FILLING_IOC`, or `ORDER_FILLING_RETURN`).
- `m_trade.Buy()` / `m_trade.Sell()` with normalized prices to `_Digits`.

### 5. Execution Receipt Posting (`POST /api/v1/bridge/commands/{command_id}/receipt`)
- Generates unique receipt ID: `{InpExecutorId}-{TimeLocal()}-{GetTickCount()}`.
- Status: `EXECUTED` (retcode 10009 / 10008), `REJECTED`, or `FAILED`.
- Submits `retcode`, result message, and order ticket to backend ledger.
