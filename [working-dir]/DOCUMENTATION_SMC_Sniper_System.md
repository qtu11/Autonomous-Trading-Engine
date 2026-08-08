# QTUS SMC-SNIPER TRADING SYSTEM v2.0
## Hướng Dẫn Sử Dụng Chi Tiết

---

## MỤC LỤC
1. [Tổng Quan Hệ Thống](#1-tổng-quan-hệ-thống)
2. [Cài Đặt](#2-cài-đặt)
3. [Cấu Trúc Hệ Thống](#3-cấu-trúc-hệ-thống)
4. [SMC - Smart Money Concepts](#4-smc---smart-money-concepts)
5. [ICT - Inner Circle Trader](#5-ict---inner-circle-trader)
6. [Price Action](#6-price-action)
7. [Sniper Core](#7-sniper-core)
8. [Điểm Signal & Confluence](#8-điểm-signal--confluence)
9. [Auto Trading Engine](#9-auto-trading-engine)
10. [Hướng Dẫn Sử Dụng Chart](#10-hướng-dẫn-sử-dụng-chart)
11. [Alert cho Auto Trade](#11-alert-cho-auto-trade)

---

## 1. TỔNG QUAN HỆ THỐNG

### 1.1 Giới thiệu
Hệ thống **SMC-Sniper** kết hợp 4 phương pháp trading mạnh nhất:
- **SMC**: Smart Money Concepts - giao dịch theo dòng tiền tổ chức
- **ICT**: Inner Circle Trader - định thời điểm vào lệnh theo phiên, OTE, Judas Swing
- **Price Action**: Mẫu hình nến xác nhận điểm vào
- **Sniper**: EMA Ribbon, VWAP, ADX, RSI, MACD - lọc xu hướng

### 1.2 Các file
| File | Mô tả |
|------|--------|
| `SMC_Sniper_System_v2.pine` | Indicator - Hiển thị toàn bộ tín hiệu trên chart |
| `SMC_Sniper_AutoTrader_v2.pine` | Strategy - Auto trading engine có backtest |

### 1.3 Timeframe khuyến nghị
- **Chính**: 15m, 1H, 4H
- **Phụ**: HTF (240/D) để xác định Bias

---

## 2. CÀI ĐẶT

### 2.1 Indicator (SMC_Sniper_System_v2.pine)
```
1. Mở TradingView → Chart
2. Nhấn "Pine Editor" bên dưới chart
3. Copy toàn bộ code từ SMC_Sniper_System_v2.pine
4. Paste vào Pine Editor
5. Nhấn "Add to chart"
```

### 2.2 Strategy (SMC_Sniper_AutoTrader_v2.pine)
```
1. Tạo chart mới
2. Mở Pine Editor
3. Copy code từ SMC_Sniper_AutoTrader_v2.pine
4. Paste vào Pine Editor
5. Nhấn "Add to chart"
6. Strategy sẽ tự backtest và hiện kết quả
```

### 2.3 Webhook cho Auto Trade
```
Để kết nối với broker (3Commas, WunderTrading, etc):
1. Mở Settings → Alerts
2. Tạo Alert mới với điều kiện alert condition
3. Kích hoạt Webhook URL
4. Paste URL từ bot trading của bạn
```

---

## 3. CẤU TRÚC HỆ THỐNG

```
┌─────────────────────────────────────────────────────────────────┐
│                    QTUS SMC-SNIPER SYSTEM                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │      SMC     │  │      ICT     │  │ PRICE ACTION │          │
│  ├──────────────┤  ├──────────────┤  ├──────────────┤          │
│  │ FVG          │  │ Killzones    │  │ Pin Bar      │          │
│  │ Order Block  │  │ OTE Fib      │  │ Engulfing    │          │
│  │ Liquidity    │  │ Judas Swing  │  │ Inside Bar   │          │
│  │ BOS/CHoCH    │  │ Displacement │  │ Tweezer      │          │
│  │ MSS          │  │ PDH/PDL     │  │ Star Pattern │          │
│  │ Breaker Block│  │ Daily Pivots │  │ 3 Soldiers   │          │
│  │ IFVG         │  │ PO3/AMD     │  │ Rejection    │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                 │                  │                   │
│         └────────────┬────┴─────────────────┘                   │
│                      ▼                                          │
│              ┌───────────────┐                                   │
│              │ SNIPER CORE   │                                   │
│              ├───────────────┤                                   │
│              │ EMA Ribbon 9/21│                                   │
│              │ VWAP          │                                   │
│              │ ADX           │                                   │
│              │ RSI(14)       │                                   │
│              │ MACD          │                                   │
│              │ Score System  │                                   │
│              └───────┬───────┘                                   │
│                      ▼                                          │
│              ┌───────────────┐                                   │
│              │ CONFLOW CHECK │                                   │
│              ├───────────────┤                                   │
│              │ BUY Score 0-20│                                   │
│              │ SELL Score 0-20│                                  │
│              │ HTF Bias       │                                   │
│              │ Killzone Check │                                   │
│              │ Risk/Reward    │                                   │
│              └───────┬───────┘                                   │
│                      ▼                                          │
│              ┌───────────────┐                                   │
│              │   DASHBOARD   │                                   │
│              ├───────────────┤                                   │
│              │ Signal Labels │                                   │
│              │ Entry/SL/TP   │                                   │
│              │ TP Hit Status  │                                   │
│              └───────────────┘                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. SMC - SMART MONEY CONCEPTS

### 4.1 Market Structure (MS)

**Bullish Structure**: HH → HL → HH → HL
```
       HH
        │
   HL ──┘
        │
       HH
        │
   HL ──┘
```

**Bearish Structure**: LH → LL → LH → LL
```
   LH ──┐
        │
       LL
        │
   LH ──┘
        │
       LL
```

### 4.2 Fair Value Gap (FVG)

**Bullish FVG** (Tăng giá):
```
    Candle 1 (Bullish)
         │
         │  ← High[2]
    Gap   │     Khoảng trống
         │  ← Low[0]
         │
    Candle 3 (Bullish)
```
- **Logic**: `Low[0] > High[2]`
- **Ý nghĩa**: Dòng tiền lớn đẩy giá lên, để lại vùng trống chưa được lấp
- **Vào lệnh**: Retest về vùng FVG → Buy khi có rejection

**Bearish FVG** (Giảm giá):
```
    Candle 3 (Bearish)
         │
         │  ← Low[2]
    Gap   │     Khoảng trống
         │  ← High[0]
         │
    Candle 1 (Bearish)
```
- **Logic**: `High[0] < Low[2]`

### 4.3 Order Block (OB)

**Bullish OB**:
```
    Candle trước: Bearish
    Candle hiện tại: Bullish + tạo BOS/MSS
    Vùng OB: Open → Low của candle trước
```
- **Logic**: `isBearish[1] AND displacementBullish AND (BOS OR MSS)`
- **Visual**: Box màu xanh dương

**Bearish OB**:
```
    Candle trước: Bullish
    Candle hiện tại: Bearish + tạo BOS/MSS
    Vùng OB: High → Open của candle trước
```

### 4.4 Liquidity (BSL/SSL)

**Buy Side Liquidity (BSL)**:
- Equal Highs (EQH)
- Swing Highs
- Vùng phía trên giá

**Sell Side Liquidity (SSL)**:
- Equal Lows (EQL)
- Swing Lows
- Vùng phía dưới giá

**Liquidity Sweep**:
```
Bullish: Low < SSL → Close > SSL (quét thanh khoản bên dưới rồi bật lên)
Bearish: High > BSL → Close < BSL (quét thanh khoản bên trên rồi rớt xuống)
```

### 4.5 BOS / CHoCH / MSS

**BOS (Break of Structure)**:
```
Bullish: Close > Previous Swing High
Bearish: Close < Previous Swing Low
```

**CHoCH (Change of Character)**:
```
Bullish: Downtrend (LL→LH) → Close > LH
Bearish: Uptrend (HH→HL) → Close < HL
```

**MSS (Market Structure Shift)**:
```
Bullish: SSL Sweep → Bullish Displacement → Break LH → MSS
Bearish: BSL Sweep → Bearish Displacement → Break HL → MSS
```

### 4.6 Breaker Block & IFVG

**Breaker Block**: OB cũ bị phá → trở thành hỗ trợ/kháng cự mới

**IFVG (Inverse FVG)**: FVG cũ bị lấp đầy → vùng đó trở thành hỗ trợ/kháng cự

---

## 5. ICT - INNER CIRCLE TRADER

### 5.1 Killzones

| Killzone | Giờ (UTC) | Màu |
|----------|-----------|-----|
| London (LKZ) | 08:00-09:00 | Vàng |
| NY (NYKZ) | 13:30-14:30 | Đỏ |
| Asia (AKZ) | 00:00-09:00 | Xanh dương |

**Sử dụng**:
- Vào lệnh theo hướng của Killzone
- Chờ FVG, OB, Liquidity trong KZ

### 5.2 OTE (Optimal Trade Entry)

Fibonacci retracement zones:
```
Swing Low ──────────────────────────────────────────────── Swing High
   │                                                              │
   │  38.2%  │           62%        │           79%      │  100%  │
   │         │           │           │           │         │        │
   │         │    OTE ZONE (Vào lệnh tốt nhất)    │         │        │
   │         │           │           │           │         │        │
```

**Logic**:
```
Bullish: Giá pullback về 62%-79% của swing lên → Tìm Buy
Bearish: Giá pullback về 62%-79% của swing xuống → Tìm Sell
```

### 5.3 Judas Swing

**Bullish Judas**:
```
1. Giá mở rộng xuống
2. Sweep SSL
3. Rejection candle
4. MSS
5. Displacement Bullish
→ BUY
```

**Bearish Judas**:
```
1. Giá mở rộng lên
2. Sweep BSL
3. Rejection candle
4. MSS
5. Displacement Bearish
→ SELL
```

### 5.4 PO3 / AMD (Accumulation-Manipulation-Distribution)

```
Phase 1: Accumulation - Volume thấp, range hẹp
    ↓
Phase 2: Manipulation - Spike xuống (bull) hoặc lên (bear), sweep liquidity
    ↓
Phase 3: Distribution - Displacement mạnh ra khỏi vùng
```

### 5.5 Daily/Weekly Levels

| Level | Ý nghĩa |
|-------|----------|
| PDH/PDL | Previous Day High/Low |
| PWH/PWL | Previous Week High/Low |
| R1, R2, R3 | Resistance 1, 2, 3 |
| S1, S2, S3 | Support 1, 2, 3 |
| PP | Pivot Point = (PDH + PDL + Close) / 3 |

---

## 6. PRICE ACTION

### 6.1 Pin Bar / Rejection

**Bullish Pin Bar**:
```
       ▲ Wick (Lower)
       │
───────┤ ← Body
       │
     (Long lower wick ≥ 2× body)
```

**Bearish Pin Bar**:
```
       │
───────┤ ← Body
       │
       ▼ Wick (Upper)
```

**Logic**:
```pine
bullish_pinbar = LWR >= 2 × Body AND UWR ≤ Body × 0.5 AND Close > Open
bearish_pinbar = UWR >= 2 × Body AND LWR ≤ Body × 0.5 AND Close < Open
```

### 6.2 Engulfing

**Bullish Engulfing**:
```
    [1]Bearish
    ┌─────┐
    │     │ ← Open > Close[1]
    │     │
    │     │
    └─────┘
    [0]Bullish
    ┌─────┐
    │     │
    │     │ ← Close > Open[1]
    │     │
    └─────┘
```

**Bearish Engulfing**: Ngược lại

### 6.3 Inside Bar / Outside Bar

**Inside Bar**:
```
[1]    ┌───────────┐
       │           │
[0]    │  Inside   │
       │           │
       └───────────┘
```

**Outside Bar**:
```
       [1]
    ┌───────────┐
    │           │
[0] │  Outside  │
    │           │
    └───────────┘
```

### 6.4 Tweezer

**Tweezer Bottom** (Bullish):
```
[1]    Low ~ Low[1]
[0]    Bearish candle
```

**Tweezer Top** (Bearish):
```
[1]    High ~ High[1]
[0]    Bullish candle
```

---

## 7. SNIPER CORE

### 7.1 EMA Ribbon (9/21)

```
EMA 9 > EMA 21 = Bullish Ribbon (Xanh)
EMA 9 < EMA 21 = Bearish Ribbon (Đỏ)

Độ dày ribbon = momentum strength
```

### 7.2 VWAP

- **Above VWAP**: Price > VWAP → Bullish bias
- **Below VWAP**: Price < VWAP → Bearish bias
- VWAP là "Fair Price" của ngày

### 7.3 ADX (Average Directional Index)

| ADX Value | Ý nghĩa |
|-----------|----------|
| < 20 | No Trend / Range |
| 20-25 | Weak Trend |
| 25-50 | Strong Trend ← ENTRY ZONE |
| 50-75 | Very Strong |
| > 75 | Extreme (có thể đảo chiều) |

### 7.4 RSI (14)

- **> 50**: Bullish momentum
- **< 50**: Bearish momentum
- **> 70**: Overbought
- **< 30**: Oversold

### 7.5 MACD

- **MACD Line > Signal Line**: Bullish
- **MACD Line < Signal Line**: Bearish
- **Histogram**: Momentum strength

### 7.6 Sniper Score

**7 Yếu tố cho Bull/Bear**:
| # | Factor | Bull +1 | Bear +1 |
|---|--------|---------|---------|
| 1 | Price vs VWAP | Above | Below |
| 2 | RSI(14) | > 50 | < 50 |
| 3 | MACD | Main > Signal | Main < Signal |
| 4 | EMA Cross | 9 > 21 | 9 < 21 |
| 5 | ADX Filter | ADX > 25 & Price > EMA9 | ADX > 25 & Price < EMA9 |
| 6 | Volume | High vol & Bullish candle | High vol & Bearish candle |
| 7 | RSI 5m | > 50 | < 50 |

**Market Bias**:
```
Bull Pct - Bear Pct ≥ 40% → STRONG BULL
Bear Pct - Bull Pct ≥ 40% → STRONG BEAR
Bull Pct > Bear Pct       → MILD BULL
Bear Pct > Bull Pct       → MILD BEAR
```

---

## 8. ĐIỂM SIGNAL & CONFLUENCE

### 8.1 SMC Confluence Score (13 factors)

**BUY Score**:
```
+1 HTF Bullish Bias
+1 Discount Zone (Price < EQ)
+1 SSL Sweep
+1 Equal Lows (EQL)
+1 Bullish Engulfing
+1 Bullish Pin Bar
+1 Bullish Rejection
+1 Bullish Displacement
+1 Bullish CHoCH
+1 Bullish MSS
+1 Bullish BOS
+1 Bullish FVG
+1 Bullish OB
```

**SELL Score**: Tương tự ngược lại cho bearish

### 8.2 Signal Strength

| Score | Signal | Màu |
|-------|--------|-----|
| 10-13/13 | STRONG | Xanh dương |
| 7-9/13 | VALID | Vàng |
| 5-6/13 | WEAK | Xám |
| < 5 | NO TRADE | - |

### 8.3 Complete BUY Flow

```
1. HTF Bias: Bullish (4H/D bullish)
2. Zone: Discount (Price < EQ)
3. Liquidity: SSL Sweep / EQL
4. Pattern: SFP / Pin Bar / Engulfing
5. Structure: MSS / CHoCH
6. Momentum: Bullish Displacement
7. Gap: FVG / OB
8. Entry: Retest vùng FVG/OB
9. Confirmation: Bullish candle + Volume
10. RRR: ≥ 1:2
→ SNIPER BUY
```

### 8.4 Dashboard Indicator

```
┌─────────────────────────────┐
│ QTUS SMC-SNIPER SYSTEM v2  │
├─────────────────────────────┤
│ MARKET BIAS      STRONG BULL │
│ SMC BUY SCORE    9/13       │
│ SMC SELL SCORE   3/13        │
│ SNIPER BULL      86%         │
│ SNIPER BEAR      29%         │
│ SIGNAL           SNIPER BUY  │
├─────────────────────────────┤
│ Price/VWAP      ABOVE        │
│ RSI(14)         62.3 BULL   │
│ MACD            BULL         │
│ ADX             28.5 STRONG │
│ EMA(9/21)       BULL        │
│ ATR(14)         15.23       │
│ Volume          HIGH         │
├─────────────────────────────┤
│ ENTRY           1.2345      │
│ STOP LOSS       1.2190      │
│ TP1             1.2490      │
│ TP2             1.2640      │
│ TP3             1.2790      │
├─────────────────────────────┤
│ HTF Bias        BULL        │
│ PATTERN         FVG+        │
│ CONFLUENCE      STRONG+     │
│ RR TP1          1:1.0       │
│ RR TP2          1:2.0       │
│ RR TP3          1:3.0       │
└─────────────────────────────┘
```

---

## 9. AUTO TRADING ENGINE

### 9.1 Strategy Settings

```pine
// Cài đặt quan trọng:
enableAutoTrade    = true        // Bật auto trade
minScoreToTrade    = 7          // Score tối thiểu để vào lệnh
riskPerTrade       = 1.0%       // Risk mỗi lệnh
atrMultiplierSL    = 1.5        // SL = ATR × 1.5
tp1Percent         = 0.5R       // TP1 = Risk × 0.5
tp2Percent         = 1.0R       // TP2 = Risk × 1.0
tp3Percent         = 2.0R       // TP3 = Risk × 2.0
```

### 9.2 Entry Conditions

**Full Buy Condition**:
```pine
fullBuyCond = 
    EMA Cross bullish
    AND ADX > 25
    AND SMC Score ≥ 6
    AND Price Action (Pin/Engulf/DPL)
    AND HTF Bullish (nếu bật)
    AND Volume > Average
```

### 9.3 Exit Management

```
Entry
   │
   ├── SL: ATR × 1.5
   │
   ├── TP1: Risk × 0.5 → Partial 25% (nếu bật)
   │
   ├── TP2: Risk × 1.0 → Partial 25% (nếu bật), Move SL to BE
   │
   ├── TP3: Risk × 2.0 → Full Exit
   │
   └── Trail: Sau TP2, trailing stop
```

### 9.4 Filters

| Filter | Mô tả | Khuyến nghị |
|--------|-------|-------------|
| Require FVG | Cần có FVG | Optional |
| Require OB | Cần có Order Block | Optional |
| Require Liquidity Sweep | Cần có LS | Optional |
| Require Pattern | Cần có PA pattern | BẬT |
| Require ADX > 25 | Cần xu hướng mạnh | BẬT |
| Require Volume | Cần volume cao | BẬT |
| Killzone Only | Chỉ trade trong KZ | Optional |
| OTE Entry | Chờ retest OTE zone | Optional |

### 9.5 Risk Management

```
Max Risk/Trade:    1-2% equity
Max Daily Loss:    3% equity
Max Consecutive Loss: 3 lệnh → Dừng ngày
Max Open Trades:   2 lệnh đồng thời
```

---

## 10. HƯỚNG DẪN SỬ DỤNG CHART

### 10.1 Đọc Dashboard

1. **MARKET BIAS**: Xem trend chính
   - STRONG BULL/BEAR → Trade theo hướng mạnh
   - MILD → Chờ tín hiệu rõ hơn

2. **SMC SCORE**: Đếm các yếu tố SMC
   - ≥ 8 → Strong setup
   - 6-7 → Valid setup
   - < 6 → Wait

3. **SNIPER SCORE**: % agreement của indicators
   - 86%+ → Strong momentum

4. **SIGNAL**: Tín hiệu hiện tại
   - SNIPER BUY/SELL → Confluence đạt ngưỡng
   - WAIT → Chưa có setup

### 10.2 Visual trên Chart

| Element | Màu | Ý nghĩa |
|---------|-----|----------|
| FVG Box | Xanh lá / Đỏ | Vùng mất cân bằng |
| OB Box | Xanh dương / Cam | Khối lệnh tổ chức |
| FVG+ Label | Xanh lá | Bullish FVG |
| FVG- Label | Đỏ | Bearish FVG |
| BSL Label | Đỏ | Thanh khoản phía trên |
| SSL Label | Xanh lá | Thanh khoản phía dưới |
| MSS Label | Xanh/Đỏ | Market Structure Shift |
| BUY/SELL Label | Xanh/Đỏ | Signal điểm vào |

### 10.3 Trade Management

1. **Entry**: Theo label BUY/SELL trên chart
2. **SL**: Đường đỏ
3. **TP1-TP5**: Đường xanh lá (dashed)
4. **TP Hit**: Đường chuyển màu turquoise khi chạm

---

## 11. ALERT CHO AUTO TRADE

### 11.1 Cài đặt Alert trên TradingView

```
1. Alerts → Create Alert
2. Condition: Qtus SMC-Sniper AutoTrader v2
3. Trigger: "BUY SIGNAL" hoặc "SELL SIGNAL"
4. Options:
   ☑ Trigger once per bar
   ☑ Send Email
   ☑ Send Webhook
   ☑ Send SMS
5. Webhook URL: Paste từ bot trading
```

### 11.2 Webhook Format

```json
// BUY Entry
{
  "action": "BUY",
  "symbol": "{{ticker}}",
  "price": "{{close}}",
  "stop_loss": "1.2190",
  "take_profit": "1.2790",
  "quantity": "0.5",
  "signal": "SNIPER_BUY",
  "score": "9/20",
  "confluence": "FVG:1|OB:1|LS:1|MSS:1"
}

// SELL Entry
{
  "action": "SELL",
  "symbol": "{{ticker}}",
  "price": "{{close}}",
  "stop_loss": "1.2500",
  "take_profit": "1.1900",
  "quantity": "0.5",
  "signal": "SNIPER_SELL",
  "score": "8/20",
  "confluence": "FVG:1|OB:0|LS:1|MSS:1"
}

// TP Hit
{
  "action": "CLOSE",
  "reason": "TP3_HIT",
  "profit": "2.0R"
}

// SL Hit
{
  "action": "CLOSE",
  "reason": "SL_HIT",
  "loss": "1.0R"
}
```

### 11.3 Bot Trading hỗ trợ

- **3Commas**: Composite Bot, DCA Bot
- **WunderTrading**: Trading Bot
- **Cornix**: Trading Bot & Alerts
- **Custom Webhook**: Kết nối với broker qua API

---

## 12. SCAN CHECKLIST

### 12.1 BUY Setup Checklist

```
☐ HTF Bias = Bullish (4H/D)
☐ Price = Discount Zone (dưới EQ)
☐ SSL Sweep xảy ra
☐ FVG hình thành
☐ OB (nếu có)
☐ MSS/CHoCH xác nhận
☐ Bullish Displacement candle
☐ EMA 9 > EMA 21 (Ribbon xanh)
☐ Price > VWAP
☐ ADX > 25
☐ RSI > 50
☐ MACD Bullish
☐ Volume cao
☐ Score ≥ 7/20
☐ RRR ≥ 1:2
→ ENTRY BUY
```

### 12.2 SELL Setup Checklist

```
☐ HTF Bias = Bearish (4H/D)
☐ Price = Premium Zone (trên EQ)
☐ BSL Sweep xảy ra
☐ FVG hình thành
☐ OB (nếu có)
☐ MSS/CHoCH xác nhận
☐ Bearish Displacement candle
☐ EMA 9 < EMA 21 (Ribbon đỏ)
☐ Price < VWAP
☐ ADX > 25
☐ RSI < 50
☐ MACD Bearish
☐ Volume cao
☐ Score ≥ 7/20
☐ RRR ≥ 1:2
→ ENTRY SELL
```

---

## 13. BACKTEST RESULTS

### 13.1 Expected Performance

| Metric | Target |
|--------|--------|
| Win Rate | > 55% |
| Avg R:R | > 1.5:1 |
| Max Drawdown | < 15% |
| Sharpe Ratio | > 1.5 |
| Monthly Return | > 5% |

### 13.2 Notes

- Backtest trên multiple pairs để tìm best performers
- Forward test trước khi live
- Điều chỉnh score thresholds theo market conditions
- Kết hợp với news/event filter

---

**© 2024 QtusDev | SMC-Sniper Trading System v2.0**
