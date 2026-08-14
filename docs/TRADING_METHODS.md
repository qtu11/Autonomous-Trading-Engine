# QuantAI - 5 Phương Pháp Giao Dịch & Pattern Detection Engines

Tài liệu này giải thích tổng quan và chi tiết cách TradeAI ATE hiện thực hóa 5 phương pháp giao dịch định lượng từ các file Pine Script (`smc.pine`, `structureengine.pine`, `sniper.pine`, `ict.pine`, `priceaction.pine`).

## DANH MỤC ĐẶC TẢ CHI TIẾT TỪNG PHƯƠNG PHÁP:
- [01. SMC - Smart Money Concepts](file:///c:/Users/KIMPC/AppData/Roaming/MetaQuotes/Terminal/C3DCCD4DFDD81FF8F00FFC310CAC0FD8/MQL5/Experts/tradeAI/docs/methods/01_SMC_SMART_MONEY_CONCEPTS.md)
- [02. ICT - Inner Circle Trader](file:///c:/Users/KIMPC/AppData/Roaming/MetaQuotes/Terminal/C3DCCD4DFDD81FF8F00FFC310CAC0FD8/MQL5/Experts/tradeAI/docs/methods/02_ICT_INNER_CIRCLE_TRADER.md)
- [03. Sniper Momentum Flow](file:///c:/Users/KIMPC/AppData/Roaming/MetaQuotes/Terminal/C3DCCD4DFDD81FF8F00FFC310CAC0FD8/MQL5/Experts/tradeAI/docs/methods/03_SNIPER_MOMENTUM_FLOW.md)
- [04. Price Action & Candle Dynamics](file:///c:/Users/KIMPC/AppData/Roaming/MetaQuotes/Terminal/C3DCCD4DFDD81FF8F00FFC310CAC0FD8/MQL5/Experts/tradeAI/docs/methods/04_PRICE_ACTION_CANDLE_DYNAMICS.md)
- [05. Ultra Confluence Matrix](file:///c:/Users/KIMPC/AppData/Roaming/MetaQuotes/Terminal/C3DCCD4DFDD81FF8F00FFC310CAC0FD8/MQL5/Experts/tradeAI/docs/methods/05_ULTRA_CONFLUENCE_MATRIX.md)

## Kiến Trúc Pattern Detection

```text
MT5 REAL DATA (XAUUSD)
      |
      v
MARKET_DATA_ENGINE        # Lấy OHLCV từ MT5
      |
      v
CANDLE_NORMALIZER        # Chuẩn hóa nến, xử lý missing/timeframe
      |
      v
SHARED_SWING_ENGINE      # NGUỒN DUY NHẤT: Swing High/Low dùng chung
      |
      +---------------------------+
      |                           |
      v                           v
MARKET_STRUCTURE_ENGINE   INDICATOR_ENGINE (EMA/RSI/ATR/VWAP/MACD/ADX/Pivot)
      |                           |
      +---------------------------+
      |
      v
----------------------------------------------
|        PATTERN DETECTION ENGINES           |
|  +-----------+ +----------+ +----------+ |
|  | PRICE     | |  SMC     | |   ICT    | |
|  | ACTION    | |          | |          | |
|  +-----------+ +----------+ +----------+ |
|  +-----------+ +-----------+             |
|  | SNIPER   | | ULTRA     |              |
|  +-----------+ +-----------+             |
----------------------------------------------
      |
      v
MARKUP_OBJECTS (JSON) --> Frontend Chart
```

**Nguyên tắc then chốt**: Tất cả pattern đều phát hiện từ dữ liệu nến THỰC (backend), không sinh ngẫu nhiên. Một nguồn Swing duy nhất (SHARED_SWING_ENGINE) được dùng cho mọi engine → đảm bảo tính nhất quán.

---

## 1. PRICE ACTION (25 khái niệm)

| Nhóm | Khái niệm |
|------|-----------|
| Xu hướng & cấu trúc | Trend (EMA alignment), Swing (HH/HL/LH/LL) |
| Vùng giá | Support/Resistance, Trendline, Channel, Range |
| Hành động giá | Breakout, Pullback, Retest, Fake Breakout |
| Mẫu hình nến (14) | Pin Bar, Engulfing, Inside Bar, Outside Bar, Doji, Morning Star, Evening Star, Hammer, Shooting Star, Tweezer Top, Tweezer Bottom, Marubozu, Three White Soldiers, Three Black Crows |
| Mở rộng | Custom Patterns |

**Logic tín hiệu**:
```
TREND = BULLISH
+ SUPPORT = ACTIVE
+ BULLISH REJECTION
+ CONFIRMATION CANDLE
= POTENTIAL BUY
```

---

## 2. SMC - Smart Money Concepts (26 khái niệm)

1. Market Structure (BOS/CHoCH/MSS)
2. Liquidity Sweep, 3. Order Block, 4. FVG (Fair Value Gap), 5. Breaker/Mitigation Block, 6. Rejection Block
7. Equal Highs/Lows, 8. Internal Liquidity, 9. External Liquidity
10. Premium/Discount Zone, 11. Imbalance, 12. Supply/Demand, 13. Volume Imbalance
14. Liquidity Void, 15. Inducement, 16. Stop Hunt, 17. Institutional Order, 18. Manipulation
19. Fair Price Gap, 20. Gap Fill, 21. Displacement, 22. Return to Mean
23. Trend Continuation, 24. Trend Reversal, 25. Range Expansion, 26. Internal/External

**Logic tín hiệu**:
```
LIQUIDITY SWEEP
+ ORDER BLOCK REACTION
+ FVG CREATION
+ RETEST OF FVG
= SMC SETUP
```

---

## 3. ICT - Inner Circle Trader (26 khái niệm)

1. OTE (Optimal Trade Entry), 2. Fibonacci 62-79%, 3. PD Array (OB + FVG), 4. Kill Zones (London/NY/Asia)
5. PDH/PDL, 6. Weekly/Monthly High/Low, 7. FVG, 8. Order Blocks, 9. Liquidity Pools
10. Silver Bullet, 11. Turtle Soup, 12. Judas Swing, 13. SMT Divergence, 14. AMD/PO3
15. BPR (Balanced Price Range), 16. Unicorn Model, 17. Dealing Range, 18. Dealing Curve
19. Fair Price, 20. Equal Highs/Lows, 21. Displacement, 22. Optimal High/Low, 23. Midpoint...

**Logic tín hiệu**:
```
IN KILL ZONE
+ PDH/PDL LIQUIDITY
+ OTE FIB LEVEL
+ FVG RETEST
= ICT SETUP
```

---

## 4. SNIPER (chỉ báo + động lượng)

- **Chỉ báo**: EMA 9/21 (Ribbon), VWAP, ADX(14), RSI(14), MACD(12,26,9).
- **Chấm điểm (tối đa 7 yếu tố)**:
```
Bull Score:
+ Price > VWAP: +1
+ RSI > 50: +1
+ MACD > Signal: +1
+ EMA9 > EMA21: +1
+ ADX > 25 + Price > EMA9: +1
+ Volume > Average: +1
= 6/7 MAX (Buy)
```
- **Vào lệnh**: khi giá retest ribbon EMA 9/21 hoặc VWAP kèm xác nhận momentum (RSI/MACD/ADX).
- **Thoát**: trailing theo EMA/ATR, SL bám ribbon.

---

## 5. ULTRA CONFLUENCE (Matrix 5 lớp)

```
LAYER 1: Market Structure (BOS, CHoCH, Swing HH/HL/LH/LL)
LAYER 2: Supply/Demand (OB, FVG, Liquidity, Imbalance)
LAYER 3: Dynamic (EMA 20/50/200, VWAP, Daily Pivot)
LAYER 4: Momentum (RSI, MACD, ADX, Volume Ratio)
LAYER 5: Time/News (Tokyo/London/NY Session, Kill Zone, News impact)
```

**Trọng số**:
```
STRUCTURE_SCORE  x 0.25
ZONE_SCORE       x 0.25
INDICATOR_SCORE  x 0.20
MOMENTUM_SCORE   x 0.15
TIME_SCORE       x 0.15
TOTAL            = 100%
```

**Ngưỡng**:
- `>= 85%`: QUALIFIED SETUP (có thể vào lệnh)
- `70-84%`: CONSIDER (chờ thêm xác nhận)
- `< 70%`: PASS (bỏ lỡ)

---

## FVG (Fair Value Gap) - Mô hình 3 Nến

```
C1 = candle[i-2]   # cũ nhất
C2 = candle[i-1]   # nến giữa (displacement)
C3 = candle[i]     # mới nhất

BULLISH FVG:  HIGH(C1) < LOW(C3)   → vùng [HIGH(C1), LOW(C3)]
BEARISH FVG:  LOW(C1) > HIGH(C3)   → vùng [HIGH(C3), LOW(C1)]
```

**Các trạng thái FVG**:
| Trạng thái | Ý nghĩa |
|-----------|---------|
| `FORMING` | Mới được phát hiện |
| `ACTIVE` | Chưa chạm |
| `PARTIALLY_FILLED` | Giá đi vào vùng |
| `MITIGATED` | Giá lấp > 50% |
| `INVALIDATED` | Giá đóng cửa qua hết |

**Validation**:
- minimum gap >= 0.5 (đơn vị ATR)
- middle candle body ratio >= 0.55
- require displacement >= 1.5 ATR

---

## Order Block Detection

```
Bullish OB:
- Prior candle bearish (consolidation)
- Current candle bullish displacement
- Displacement breaks trên swing high gần đây
- Body ratio >= 55%
- Body size >= 1.5 x ATR

Zone = [Low(prior), High(prior)]
```

**Breaker / Mitigation / Rejection**:
- **Breaker**: OB cũ bị phá xuyên hẳn → đảo chiều (bull OB → bearish Breaker và ngược lại).
- **Mitigation**: chỉ phá râu (wick) chưa đóng qua → nhẹ hơn.
- **Rejection**: wick mạnh thể hiện từ chối tại level.

---

## Market Structure (BOS / CHoCH / MSS)

```
BOS (Break of Structure):
  Bullish: Close > Recent Swing High (trong uptrend)
  Bearish: Close < Recent Swing Low (trong downtrend)

CHoCH (Change of Character):
  Bullish: Close > Recent Swing High (trong downtrend = đảo chiều)
  Bearish: Close < Recent Swing Low (trong uptrend = đảo chiều)

MSS (Market Structure Shift):
  CHoCH + cây nến xác nhận
```

---

## Object Schema (Markup JSON)

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
  "source": { "c1_index": 123, "c2_index": 124, "c3_index": 125,
              "c1_time": "...", "c2_time": "...", "c3_time": "..." },
  "price": { "top": 3350.50, "bottom": 3348.20, "ce": 3349.35 },
  "time":  { "created_at": "...", "start_time": "...", "end_time": null,
             "first_touch": null, "mitigated_at": null },
  "fill":  { "percentage": 0, "touches": 0 },
  "strategy_tags": ["SMC", "ICT", "ULTRA"]
}
```

**Anti-Clutter Rules** (chống tấp nập trên chart):
1. Chỉ hiện object ACTIVE.
2. Giữ tối đa 10 FVG/OB gần đây.
3. Object cũ giảm opacity.
4. Có thể lọc theo chiến lược (toggle).
5. Priority queue: Price>Ative-Structure>Active-Liquidity>Active-FVG>Active-OB>Historical (<20).

---

## Files Liên Quan

| File | Vai trò |
|------|---------|
| `dashboard/detectors.py` | Pattern lõi (FVG, OB, BOS, Swing) |
| `dashboard/advanced_detectors.py` | Pattern nâng cao (ICT, PA, SMC) |
| `dashboard/chart_markup.py` | Build JSON markup cho chart |
| `dashboard/signal_engines.py` | Sinh tín hiệu 5 phương pháp |
| `dashboard/strategy_core.py` | Confluence & đánh giá lệnh |
| `MARKET_ANALYSIS_SPEC.md` | Đặc tả đầy đủ (validation, schema) |

---

*Tài liệu thuộc dự án QuantAI - Nguyễn Quang Tú (QTusdev) | MIT License.*