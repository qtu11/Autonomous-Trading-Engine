# QuantAI Risk Analysis & Threat Modeling

## Comprehensive Risk Matrix

| Risk ID | Vulnerability / Threat Area | Potential Impact | Priority | Mitigation / Interlock Mechanism |
|---|---|---|---|---|
| R-001 | Unauthorized live order placement | Financial loss | CRITICAL | Multi-layer arming: `LIVE` mode locked behind `QUANTAI_LIVE_ARMED=true`, `ENABLE_TRADING=true`, `KILL_SWITCH=false`, and `ACCOUNT_TRADE_MODE_REAL`. |
| R-002 | Duplicate order execution (Race condition) | Double lot exposure | CRITICAL | Atomic SQLite command ledger with unique `idempotency_key`, single-command `CLAIMED` lease locks, and unique `receipt_id`. |
| R-003 | EA disconnection / Network drops | Stale telemetry / Unhandled positions | HIGH | Connection watchdog in EA with consecutive failure backoff; backend marks EA status `STALE` if no heartbeat within 10 seconds. |
| R-004 | Extreme spread expansion during news events | High slippage / Poor fills | HIGH | RiskGate rejects proposals if `ask - bid > max_spread` (XAUUSD cap: 0.50). EA re-verifies spread locally before `CTrade`. |
| R-005 | Flash crash / Account drawdown limit breach | Severe capital loss | HIGH | RiskGate enforces daily loss cap (`max_daily_loss_fraction = 0.02`) and minimum free margin threshold. |
| R-006 | API token exposure in client browser | Security credential leak | MEDIUM | Separation of tokens: `QUANTAI_BRIDGE_TOKEN` and `QUANTAI_OPERATOR_TOKEN` are backend-only and never exposed in `NEXT_PUBLIC_*` or client UI. |
| R-007 | Invalid or NaN price tick inputs | Code crash / Invalid SL/TP | MEDIUM | Strict `isfinite()` checks across Python RiskGate and MQL5 price normalization. |
