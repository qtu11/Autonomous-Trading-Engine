# Autonomous Trading Engine (ATE) - Bug Audit Log (BUGS.md)

## Summary of Findings
This document tracks all identified logic errors, boundary failures, runtime deprecations, and integration bugs across the ATE platform codebase.

---

### BUG-001: Strict Greater-Than Boundary Failure in Price Validator
- **Short ID**: BUG-001
- **Severity**: Medium
- **Component**: Backend / Validators
- **File**: [`dashboard/validators.py`](file:///C:/Users/KIMPC/AppData/Roaming/MetaQuotes/Terminal/C3DCCD4DFDD81FF8F00FFC310CAC0FD8/MQL5/Experts/tradeAI/dashboard/validators.py#L229)
- **Reproduction Steps**:
  1. Execute `pytest dashboard/tests/test_validators.py::TestPriceValidation::test_valid_prices`.
  2. Pass `validate_price(0.0001)` where default `min_val = 0.0001`.
  3. Function evaluates `0.0001 > 0.0001`, returning `False`.
- **Expected Behavior**: `validate_price(0.0001)` returns `True` to allow 4-decimal precision instruments (e.g. EURUSD, PIP values).
- **Actual Behavior**: Returned `False` and failed order validation.
- **Resolution**: Updated comparison operator to `price >= min_val` in `dashboard/validators.py`.
- **Test Evidence**: `pytest dashboard/tests/test_validators.py` PASSED (52/52).

---

### BUG-002: Pre-Strip Regex Sanitization Leading Space Artifact
- **Short ID**: BUG-002
- **Severity**: Medium
- **Component**: Backend / Input Sanitization
- **File**: [`dashboard/validators.py`](file:///C:/Users/KIMPC/AppData/Roaming/MetaQuotes/Terminal/C3DCCD4DFDD81FF8F00FFC310CAC0FD8/MQL5/Experts/tradeAI/dashboard/validators.py#L235)
- **Reproduction Steps**:
  1. Execute `pytest dashboard/tests/test_validators.py::TestSanitizeInput::test_sanitize_injection`.
  2. Input `"'; DROP TABLE--"`.
  3. `value.strip()` was executed *before* `re.sub(r'[<>\'\";]', '', value)`.
- **Expected Behavior**: Sanitizer removes quote metacharacters and normalizes whitespace cleanly without leading whitespace artifacts.
- **Actual Behavior**: Result contained un-stripped leading whitespace `" DROP TABLE--"`, failing string comparison assertions.
- **Resolution**: Re-ordered regex replacement and whitespace normalization in `dashboard/validators.py`.
- **Test Evidence**: `pytest dashboard/tests/test_validators.py` PASSED (52/52).

---

### BUG-003: FastAPI & Pydantic V2 Legacy Event/Validator Deprecations
- **Short ID**: BUG-003
- **Severity**: Low (Maintenance / DX)
- **Component**: Backend / Server & Schemas
- **Files**:
  - [`dashboard/server.py`](file:///C:/Users/KIMPC/AppData/Roaming/MetaQuotes/Terminal/C3DCCD4DFDD81FF8F00FFC310CAC0FD8/MQL5/Experts/tradeAI/dashboard/server.py#L828) (FastAPI `@app.on_event("startup")`)
  - [`dashboard/validators.py`](file:///C:/Users/KIMPC/AppData/Roaming/MetaQuotes/Terminal/C3DCCD4DFDD81FF8F00FFC310CAC0FD8/MQL5/Experts/tradeAI/dashboard/validators.py#L110) (Pydantic `@validator`)
- **Reproduction Steps**:
  1. Run `pytest` on Python 3.14 + Pydantic 2.13.
  2. Observe `DeprecationWarning` logs during test setup.
- **Expected Behavior**: Codebase uses Pydantic V2 `@field_validator` and FastAPI `lifespan` handlers.
- **Actual Behavior**: Emits 12 deprecation warnings during execution.
- **Resolution**: Documented for migration.

---

### BUG-004: RiskGate Fail-Closed Verification & Command Idempotency
- **Short ID**: BUG-004
- **Severity**: High (Safety & Trading Control)
- **Component**: RiskGate / SQLite Command Store
- **Files**:
  - [`dashboard/risk_gate.py`](file:///C:/Users/KIMPC/AppData/Roaming/MetaQuotes/Terminal/C3DCCD4DFDD81FF8F00FFC310CAC0FD8/MQL5/Experts/tradeAI/dashboard/risk_gate.py)
  - [`dashboard/command_store.py`](file:///C:/Users/KIMPC/AppData/Roaming/MetaQuotes/Terminal/C3DCCD4DFDD81FF8F00FFC310CAC0FD8/MQL5/Experts/tradeAI/dashboard/command_store.py)
- **Reproduction Steps**:
  1. Replay identical order payload twice with same `idempotency_key`.
  2. Send unauthorized request missing `Authorization: Bearer <TOKEN>`.
- **Expected Behavior**:
  - Unauthorized requests are rejected (HTTP 401/403).
  - Duplicate idempotency keys fail database insert with UNIQUE constraint error and return cached command status.
  - RiskGate returns `REJECTED` if spread, margin, or drawdown limits are violated (Fail-Closed).
- **Actual Behavior**: Behavior confirmed correct after running test suite.

---

### BUG-005: Missing Method-Specific Chart Markup Integration in `/api/market`
- **Short ID**: BUG-005
- **Severity**: High (UI & Feature Functional Defect)
- **Component**: Backend Server & Chart Rendering Engine
- **File**: [`dashboard/server.py`](file:///C:/Users/KIMPC/AppData/Roaming/MetaQuotes/Terminal/C3DCCD4DFDD81FF8F00FFC310CAC0FD8/MQL5/Experts/tradeAI/dashboard/server.py#L935)
- **Reproduction Steps**:
  1. Select trading method SMC, ICT, Price Action, Sniper, or Ultra Confluence in Control Center.
  2. Load Dashboard chart.
  3. Chart only rendered 3 static EMAs and basic FVG/OB without method-specific overlays (Liquidity sweeps, OTE, Killzones, Candlestick patterns, Sniper signals).
- **Expected Behavior**: `/api/market` calls `build_chart_markup()` from `chart_markup.py` and returns full per-method drawing objects.
- **Actual Behavior**: `/api/market` constructed an inline generic list that omitted method-specific drawing layers.
- **Resolution**: Integrated `build_chart_markup(symbol=symbol, mtf_data={"M15": df}, method=method)` in `dashboard/server.py`.
- **Test Evidence**: `/api/market` endpoint now returns full method objects for all 5 trading methods.

---

### BUG-006: Signal Score Threshold Mismatch Preventing SMC/ICT Auto-Trade Execution
- **Short ID**: BUG-006
- **Severity**: High (Trading Execution Defect)
- **Component**: AI Auto-Trade Execution Loop
- **File**: [`dashboard/server.py`](file:///C:/Users/KIMPC/AppData/Roaming/MetaQuotes/Terminal/C3DCCD4DFDD81FF8F00FFC310CAC0FD8/MQL5/Experts/tradeAI/dashboard/server.py#L729)
- **Reproduction Steps**:
  1. Enable AI Auto Trade loop with SMC or ICT method selected.
  2. `analyze_smc()` produces `BUY` signal at score 56 (threshold > 55).
  3. `_ai_trade_loop` checked `if signal in ("BUY", "SELL") and score >= 60`.
- **Expected Behavior**: Trade signal generated by SMC/ICT is evaluated by RiskGate and executed.
- **Actual Behavior**: Trade loop rejected valid SMC/ICT signals between score 55 and 59 due to strict `score >= 60` check.
- **Resolution**: Updated `_ai_trade_loop` condition to `(score >= 55 or score <= 45)` matching detector engine thresholds.
- **Test Evidence**: SMC and ICT signals now pass to RiskGate and auto-execute when armed.
