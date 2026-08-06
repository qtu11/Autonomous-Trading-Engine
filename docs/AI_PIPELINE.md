# QuantAI Multi-Source AI Engine & Decision Pipeline

## Overview
QuantAI utilizes a multi-layered decision pipeline combining deterministic technical confluence, quantitative risk sizing, and fundamental AI sentiment analysis.

## Decision Pipeline Layers

```text
               ┌─────────────────────────────────────┐
               │         1. TECHNICAL LAYER          │
               │  - EMA20 vs EMA50 vs EMA200 Trend  │
               │  - RSI(14) Momentum Range           │
               │  - ATR(14) Volatility Expansion     │
               └──────────────────┬──────────────────┘
                                  │ Proposal (BUY/SELL/NO_TRADE)
                                  ▼
               ┌─────────────────────────────────────┐
               │        2. FUNDAMENTAL LAYER         │
               │  - MT5 Real Economic Calendar Push  │
               │  - USD Macro News Analysis          │
               │  - High Impact NFP/FOMC Sentiment   │
               └──────────────────┬──────────────────┘
                                  │ Confluence Score (0 - 100)
                                  ▼
               ┌─────────────────────────────────────┐
               │        3. RISK SIZING LAYER         │
               │  - Account Equity & Free Margin     │
               │  - Dynamic 1% Risk Sizing Formula   │
               │  - ATR Stop Loss & Take Profit      │
               └──────────────────┬──────────────────┘
                                  │ Sized Proposal
                                  ▼
               ┌─────────────────────────────────────┐
               │         4. RISKGATE FILTER          │
               │  - Fail-Closed Policy Verification  │
               │  - Position Limits & Spread Cap     │
               └──────────────────┬──────────────────┘
                                  │ Approved Intent
                                  ▼
                       CommandStore Ledger (SQLite)
```

## Confluence Scoring Formula
- **Trend Alignment (Max 40 pts)**:
  - BUY: `EMA20 > EMA50` (+30 pts), `EMA50 > EMA200` (+10 pts).
  - SELL: `EMA20 < EMA50` (+30 pts), `EMA50 < EMA200` (+10 pts).
- **RSI Momentum (Max 30 pts)**:
  - BUY: `50 <= RSI <= 70` (+30 pts), `45 <= RSI < 50` (+20 pts).
  - SELL: `30 <= RSI <= 50` (+30 pts), `50 < RSI <= 55` (+20 pts).
- **ATR Volatility (Max 30 pts)**:
  - `ATR >= 4.0` (+20 pts), `ATR < 4.0` (+10 pts).
- **Final Confidence**: `min(98, max(50, Score))%`.

## 1% Risk Lot Sizing Math
$$\text{Risk Amount} = \text{Account Balance} \times 0.01$$
$$\text{SL Distance} = \max(3.0, \text{ATR} \times 1.5)$$
$$\text{Suggested Lot} = \text{Quantize}\left(\frac{\text{Risk Amount}}{\text{SL Distance} \times 100}, \text{Volume Step}\right)$$
