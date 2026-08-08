# MARKET ANALYSIS ENGINE - COMPLETE SPECIFICATION
**Version: 2.0 | Date: 2026-08-08**

## 📋 Table of Contents
1. [Core Definitions](#core-definitions)
2. [FVG Detection](#fvg-fair-value-gap)
3. [Swing Engine](#swing-engine)
4. [Market Structure](#market-structure)
5. [Order Blocks](#order-blocks)
6. [Five Trading Strategies](#five-trading-strategies)
7. [Object Schema](#object-schema)
8. [Validation Rules](#validation-rules)
9. [Anti-Clutter Rules](#anti-clutter-rules)
10. [Architecture](#architecture)

---

## Core Definitions

### FVG (Fair Value Gap) - 3-CANDLE MODEL

```
C1 = candle[i-2]  # Oldest
C2 = candle[i-1]  # Middle (displacement candle)
C3 = candle[i]    # Newest
```

#### BULLISH FVG
```
Condition: HIGH(C1) < LOW(C3)
Zone:      [HIGH(C1), LOW(C3)]
```

#### BEARISH FVG
```
Condition: LOW(C1) > HIGH(C3)
Zone:      [HIGH(C3), LOW(C1)]
```

#### FVG STATES
- `FORMING`: Just detected
- `ACTIVE`: Untouching
- `PARTIALLY_FILLED`: Price entered zone
- `MITIGATED`: Price filled >50%
- `INVALIDATED`: Price closed through

---

## Swing Engine

```
Algorithm: N-candle lookback
- Swing High: high > all N candles left AND right
- Swing Low: low < all N candles left AND right
```

#### HH/HL/LH/LL Classification
```
HH: Swing High > Previous Swing High
HL: Swing Low > Previous Swing Low
LH: Swing High < Previous Swing High
LL: Swing Low < Previous Swing Low
```

---

## Market Structure

### BOS (Break of Structure)
```
Bullish: Close > Recent Swing High (in uptrend)
Bearish: Close < Recent Swing Low (in downtrend)
```

### CHoCH (Change of Character)
```
Bullish: Close > Recent Swing High (in downtrend = reversal)
Bearish: Close < Recent Swing Low (in uptrend = reversal)
```

### MSS (Market Structure Shift)
```
Definition: CHoCH + Follow-through confirmation
- Price breaks structure
- Follow candle confirms
```

---

## Order Blocks

```
Bullish OB:
- Prior candle is bearish (consolidation)
- Current candle is bullish displacement
- Displacement breaks above recent swing high
- Body ratio >= 55%
- Body size >= 1.5 x ATR

Zone: [Low of prior candle, High of prior candle]
```

### Breaker Block
```
Formed when: Previous OB is mitigated (price breaks through)
Transition: Bullish OB → Bearish Breaker (and vice versa)
```

### Mitigation Block
```
Formed when: OB wick is breached but not closed through
Less severe than Breaker Block
```

### Rejection Block
```
Wick exceeds body significantly
Indicates strong rejection at level
```

---

## Five Trading Strategies

### STRATEGY 1: PRICE ACTION

**Concepts (25):**
1. Trend (EMA alignment, structure)
2. Swing (HH/HL/LH/LL)
3. Support/Resistance
4. Trendline
5. Channel
6. Range
7. Breakout
8. Pullback
9. Retest
10. Fake Breakout
11. Pin Bar
12. Engulfing
13. Inside Bar
14. Outside Bar
15. Doji
16. Morning Star
17. Evening Star
18. Hammer
19. Shooting Star
20. Tweezer Top
21. Tweezer Bottom
22. Marubozu
23. Three White Soldiers
24. Three Black Crows
25. Custom Patterns

**Signal Logic:**
```
TREND = BULLISH
+ SUPPORT = ACTIVE
+ BULLISH REJECTION
+ CONFIRMATION CANDLE
= POTENTIAL BUY
```

---

### STRATEGY 2: SMC (Smart Money Concepts)

**Concepts (26):**
1. Market Structure (BOS/CHoCH/MSS)
2. Liquidity Sweep
3. Order Block
4. Fair Value Gap (FVG)
5. Breaker/Mitigation Block
6. Rejection Block
7. Equal Highs/Lows
8. Internal Liquidity
9. External Liquidity
10. Premium Zone
11. Discount Zone
12. Imbalance
13. Supply/Demand
14. Volume Imbalance
15. Liquidity Void
16. Inducement
17. Stop Hunt
18. Institutional Order
19. Manipulation
20. Fair Price Gap
21. Gap Fill
22. Displacement
23. Return to Mean
24. Trend Continuation
25. Trend Reversal
26. Range Expansion

**Signal Logic:**
```
LIQUIDITY SWEEP
+ ORDER BLOCK REACTION
+ FVG CREATION
+ RETEST OF FVG
= SMC SETUP
```

---

### STRATEGY 3: ICT (Inner Circle Trader)

**Concepts (26):**
1. OTE (Optimal Trade Entry)
2. Fibonacci 62-79% Retracement
3. PD Array (Order Blocks + FVGs)
4. Kill Zones (London/NY/Asia)
5. PDH (Previous Day High)
6. PDL (Previous Day Low)
7. Weekly High/Low
8. Monthly High/Low
9. Fair Value Gap
10. Order Blocks
11. Liquidity Pools
12. Silver Bullet
13. Turtle Soup
14. Judas Swing
15. SMT Divergence
16. AMD (Accumulation Manipulation Distribution)
17. PO3 (Power of Three)
18. BPR (Balanced Price Range)
19. Unicorn Model
20. Dealing Range
21. Dealing Curve
22. Fair Price
23. Equal Highs/Lows
24. Displacement
25. Optimal High/Low
26. Midpoint

**Signal Logic:**
```
IN KILL ZONE
+ PDH/PDL LIQUIDITY
+ OTE FIB LEVEL
+ FVG RETEST
= ICT SETUP
```

---

### STRATEGY 4: SNIPER

**Indicators:**
- EMA 9/21 (Ribbon)
- VWAP
- ADX (14)
- RSI (14)
- MACD (12,26,9)

**Score Calculation:**
```
Bull Score:
+ Price > VWAP: +1
+ RSI > 50: +1
+ MACD > Signal: +1
+ EMA9 > EMA21: +1
+ ADX > 25 + Price > EMA9: +1
+ Volume > Average: +1
= 6/7 MAX
```

---

### STRATEGY 5: ULTRA CONFLUENCE (5-LAYER)

```
LAYER 1: Market Structure (BOS, CHoCH, Swing, HH/HL/LH/LL)
LAYER 2: Supply/Demand (OB, FVG, Liquidity, Imbalance)
LAYER 3: Dynamic (EMA 20/50/200, VWAP, Daily Pivot)
LAYER 4: Momentum (RSI, MACD, ADX, Volume Ratio)
LAYER 5: Time/News (Session, Kill Zone, News impact)
```

**Score Weights:**
```
STRUCTURE_SCORE   x 0.25
ZONE_SCORE       x 0.25
INDICATOR_SCORE  x 0.20
MOMENTUM_SCORE   x 0.15
TIME_SCORE       x 0.15
──────────────────────────────
TOTAL            = 100%
```

**Thresholds:**
- `>= 85%`: QUALIFIED SETUP
- `70-84%`: CONSIDER
- `< 70%`: PASS

---

## Object Schema

```json
{
  "id": "XAUUSD_M15_20260808_1200_FVG_BULL",
  "type": "FVG",
  "subtype": "BULLISH",
  "symbol": "XAUUSD",
  "timeframe": "M15",
  "direction": "BULLISH",
  "status": "ACTIVE",
  "confidence": 0.85,
  
  "source": {
    "c1_index": 123,
    "c2_index": 124,
    "c3_index": 125,
    "c1_time": "2026-08-08T12:00:00",
    "c2_time": "2026-08-08T12:15:00",
    "c3_time": "2026-08-08T12:30:00"
  },
  
  "price": {
    "top": 3350.50,
    "bottom": 3348.20,
    "ce": 3349.35
  },
  
  "time": {
    "created_at": "2026-08-08T12:30:00",
    "start_time": "2026-08-08T12:15:00",
    "end_time": null,
    "first_touch": null,
    "mitigated_at": null
  },
  
  "fill": {
    "percentage": 0,
    "touches": 0
  },
  
  "strategy_tags": ["SMC", "ICT", "ULTRA"]
}
```

---

## Validation Rules

### FVG Validation
```
minimum_gap_points: 0.5 (ATR units)
minimum_middle_candle_body: 0.55 (ratio)
require_displacement: true
displacement_threshold: 1.5 (ATR units)
```

### OB Validation
```
minimum_body_ratio: 0.55
displacement_required: true
displacement_atr_mult: 1.5
swing_break_required: true
```

### BOS Validation
```
break_type: CLOSE  # CLOSE or WICK
confirmation_required: true
```

---

## Anti-Clutter Rules

1. **Active Only Mode**: Show only ACTIVE objects
2. **Recent History**: Keep last 10 FVG/OB
3. **Historical Opacity**: Reduce opacity for old objects
4. **Strategy Toggles**: Filter by strategy
5. **Priority Queue**:
   - Current Price (always top)
   - Active Structure
   - Active Liquidity
   - Active FVG
   - Active OB
   - Historical (< 20 objects)

---

## Architecture

```
REAL MT5 DATA
      │
      ▼
MARKET_DATA_ENGINE
      │
      ▼
CANDLE_NORMALIZER
      │
      ▼
SHARED_SWING_ENGINE ←── ONE CANONICAL SOURCE
      │
      ├──────────────────────┐
      │                      │
      ▼                      ▼
MARKET_STRUCTURE      INDICATOR_ENGINE
      │                      │
      ├──────────────────────┤
      │                      │
      ▼                      ▼
┌─────────────────────────────────────────┐
│         PATTERN DETECTION               │
│  ┌───────┐ ┌───────┐ ┌───────┐       │
│  │ PRICE │ │  SMC  │ │  ICT  │       │
│  │ACTION │ │       │ │       │       │
│  └───────┘ └───────┘ └───────┘       │
│  ┌───────┐ ┌───────┐                 │
│  │SNIPER │ │ ULTRA │                 │
│  └───────┘ └───────┘                 │
└─────────────────────────────────────────┘
      │
      ▼
AI_CONTEXT_BUILDER
      │
      ▼
AI_ENGINE (Claude)
      │
      ▼
RISK_ENGINE
      │
      ▼
EXECUTION_GATE → MT5
```

---

## Files Reference

| File | Description |
|------|-------------|
| `dashboard/detectors.py` | Core patterns (FVG, OB, BOS, Swing) |
| `dashboard/advanced_detectors.py` | Extended patterns (ICT, PA, SMC) |
| `dashboard/chart_markup.py` | Frontend markup builder |
| `dashboard/signal_engines.py` | Strategy signal generation |
| `dashboard/strategy_core.py` | Core trading logic |
| `dashboard/risk_engine.py` | Risk management |
| `dashboard/tests/test_market_analysis.py` | Unit tests |
| `web/app/components/TradingChart.tsx` | lightweight-charts |
| `web/app/components/CandleChart.tsx` | SVG chart |
| `web/lib/api.ts` | API client |

---

## Status: ✅ COMPLETE

All 72+ concepts implemented with:
- ✅ Single source of truth (backend)
- ✅ Shared swing engine
- ✅ Correct FVG geometry (3-candle model)
- ✅ No random object generation
- ✅ Frontend renders from backend only
- ✅ Unit tests passing
