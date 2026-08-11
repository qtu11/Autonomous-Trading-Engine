# ATE Trading Desk - Feature Specification v3.0

## PHƯƠNG PHÁP LUẬN

**Nguyên tắc thiết kế:**
- UI Institutional grade (tối, chuyên nghiệp)
- Data-driven, không clutter
- Zero errors, zero dead UI elements
- Mobile-first consideration (stretch goal)

---

## NHÓM 1: DATA VISUALIZATION

### 1.1 Equity Curve Chart
**Vị trí:** Panel mới bên dưới Control Center (LEFT COLUMN)
**Mô tả:** Line chart thể hiện equity theo thời gian

**Layout:**
```
┌─ EQUITY CURVE ──────────────────────┐
│  $10,500 ───────────────────────●   │
│        ╲                          │   │
│         ╲    ●───●              │   │
│  $10,000 ●───╱                  │   │
│             ╱                    │   │
│  $9,500 ──●──────────────────────   │
│  [1D] [1W] [1M] [3M] [ALL]           │
└──────────────────────────────────────┘
```

**Tính năng:**
- Timeframe selector: 1D, 1W, 1M, 3M, ALL
- Tooltip on hover: Date, Equity, Change %
- Gradient fill dưới line
- Màu: Line vàng (#D4B483), fill green/red tùy profit/loss
- Auto-scale Y-axis
- Max height: 160px

**Data source:** `/api/performance` → `equity_curve` array

---

### 1.2 Performance Pie Chart  
**Vị trí:** Panel Performance bên trong AI Brain (RIGHT COLUMN)
**Mô tả:** Pie chart thể hiện tỷ lệ Win/Loss/Breakeven

**Layout:**
```
┌─ WIN RATE ─────────────────────────┐
│         ┌───────┐                  │
│    ┌────┤ 65%  ├────┐              │
│    │Win │  WINS │Loss│              │
│    └────┤      ├────┘              │
│          └───────┘                  │
│  ● Wins: 13  ● Losses: 7           │
└─────────────────────────────────────┘
```

**Tính năng:**
- Animated pie chart
- Center text: Win rate %
- Legend: Wins (green), Losses (red), BE (amber)
- Hover: Show count
- Size: 120x120px

**Data source:** `/api/performance` → `win_rate`, `wins`, `losses`

---

### 1.3 Drawdown Chart
**Vị trí:** Bên dưới Equity Curve
**Mô tả:** Area chart thể hiện drawdown theo thời gian

**Layout:**
```
┌─ DRAWDOWN ─────────────────────────┐
│  0% ─────────────────────────────   │
│      ┌──────────────────────┐      │
│ -5% ─┤  ████████          ├─    │
│      │  ████████          │      │
│-10% ─┤  ██████████████    ├─    │
│      │  ████████████████ │      │
│-15% ─┤█████████████████████├─    │
│      └──────────────────────┘      │
│  Max DD: -12.3%  Current: -3.2%    │
└────────────────────────────────────┘
```

**Tính năng:**
- Red gradient fill
- Max drawdown indicator
- Current drawdown display
- Negative Y-axis
- Height: 100px

**Data source:** Calculate from equity_curve

---

### 1.4 Monthly Returns Bar
**Vị trí:** Panel Performance
**Mô tả:** Bar chart thể hiện returns theo tháng

**Layout:**
```
┌─ MONTHLY RETURNS ─────────────────┐
│  Aug  │ ████ │ +$523              │
│  Jul  │ ████ │ +$1,245            │
│  Jun  │ ████ │ -$320             │
│  May  │ ████ │ +$892              │
│  Apr  │ ████ │ +$1,102            │
└───────────────────────────────────┘
```

**Tính năng:**
- 5 most recent months
- Bar color: Green (profit), Red (loss)
- Hover: Show exact value
- Height: Auto (scrollable if needed)

---

## NHÓM 2: TRADING TOOLS

### 2.1 Risk Calculator
**Vị trí:** Panel mới trong Control Center (LEFT COLUMN)
**Mô tả:** Tính position size dựa trên risk parameters

**Layout:**
```
┌─ RISK CALCULATOR ─────────────────┐
│  Account:        $10,000         │
│  Risk %:         [2.0]%          │
│  Stop Loss:      [50] pips        │
│  ─────────────────────────────     │
│  Position Size:  0.40 lots       │
│  Risk Amount:    $200.00         │
│  ─────────────────────────────     │
│  Pip Value:      $0.50/pip      │
│  ─────────────────────────────     │
│  [BUY] [SELL] Quick Buttons       │
└───────────────────────────────────┘
```

**Tính năng:**
- Input: Account balance, Risk %, Stop Loss (pips)
- Output: Position size, Risk amount, Pip value
- Quick buttons: BUY/SELL (với pre-filled params)
- Validate inputs (max risk 5%)
- Real-time calculation

**Formula:**
```
Position Size = (Account × Risk%) / (SL × Pip Value)
```

---

### 2.2 Pip Value Calculator
**Vị trí:** Tooltip hoặc expandable trong Risk Calculator
**Mô tả:** Hiển thị giá trị pip cho các cặp tiền

**Layout:**
```
┌─ PIP VALUES ──────────────────────┐
│  XAUUSD:  $0.50/pip ($5/point)  │
│  EURUSD:  $10.00/pip             │
│  GBPUSD:  $10.00/pip             │
│  USDJPY:  $9.00/pip              │
└───────────────────────────────────┘
```

**Tính năng:**
- Show pip values for major pairs
- XAUUSD: $0.50/pip (per $0.01 move)
- Auto-update based on current price

---

### 2.3 Multi-Symbol Watchlist
**Vị trí:** Panel mới (RIGHT COLUMN, thay thế AI Brain một phần)
**Mô tả:** Theo dõi nhiều cặp tiền cùng lúc

**Layout:**
```
┌─ WATCHLIST ───────────────────────┐
│  🔍 Filter: [________]            │
│  ┌─────────────────────────────┐  │
│  │ XAUUSD  2845.50  +0.85%  ▲ │  │
│  │ EURUSD  1.0845    +0.12%  ▲ │  │
│  │ GBPUSD  1.2650    -0.05% ▼ │  │
│  │ USDJPY  149.80    +0.15% ▲ │  │
│  │ AUDUSD  0.6540    +0.08%  ▲ │  │
│  │ USDCAD  1.3650    -0.02% ▼ │  │
│  └─────────────────────────────┘  │
└───────────────────────────────────┘
```

**Tính năng:**
- List 6-8 pairs
- Symbol, Price, Change %, Direction arrow
- Click row: Select pair cho chart
- Mini sparkline (optional)
- Filter input
- Color: Green if positive, Red if negative

---

### 2.4 Correlation Matrix
**Vị trí:** Expandable trong Watchlist
**Mô tả:** Ma trận tương quan giữa các cặp

**Layout:**
```
┌─ CORRELATION ─────────────────────┐
│       XAU  EUR  GBP  JPY  AUD   │
│  XAU   1.0  0.2  0.3  0.1  0.4  │
│  EUR   0.2  1.0  0.9 -0.8 -0.3  │
│  GBP   0.3  0.9  1.0 -0.7 -0.2  │
│  JPY   0.1 -0.8 -0.7  1.0  0.5  │
│  AUD   0.4 -0.3 -0.2  0.5  1.0  │
│                                 │
│  Red: Negative  Green: Positive  │
└───────────────────────────────────┘
```

**Tính năng:**
- Heatmap colors (red negative, green positive)
- -1.0 to +1.0 scale
- Hover: Show exact value
- Size: Compact grid

---

## NHÓM 3: AI ENHANCEMENTS

### 3.1 Trade Journal with AI
**Vị trí:** Tab mới trong Positions ( CENTER)
**Mô tả:** AI ghi chú tự động cho mỗi trade

**Layout:**
```
┌─ TRADE JOURNAL ───────────────────┐
│  ┌─────────────────────────────┐ │
│  │ 📝 AI Analysis:              │ │
│  │ "Break of structure bullish. │ │
│  │  RSI divergence on H4.        │ │
│  │  Risk:Reward 2.3:1"          │ │
│  └─────────────────────────────┘ │
│  Entry: 2845.50  Exit: 2860.00  │
│  P&L: +$145 (+145 pips)         │
│  Duration: 4h 23m                 │
│  ─────────────────────────────   │
│  Tags: [#BOS #RSI_DIVERGENCE]   │
└───────────────────────────────────┘
```

**Tính năng:**
- AI auto-generate notes khi trade đóng
- Entry/Exit/SL/TP display
- P&L với pips
- Duration
- Auto-tag với pattern names
- Filter by tags
- Scrollable journal

**Data source:** `/api/history` + AI analysis

---

### 3.2 Sentiment Gauge
**Vị trí:** Header bar hoặc AI Brain panel
**Mô tả:** Đồng hồ sentiment thị trường

**Layout:**
```
┌─ SENTIMENT ───────────────────────┐
│      ╭───────────────╮          │
│   0% │      50%     │ 100%     │
│      ┣──────────────●┫          │
│      ╰───────────────╯          │
│         BEARISH: 35%             │
│         BULLISH: 65%             │
└───────────────────────────────────┘
```

**Tính năng:**
- Semi-circle gauge
- Needle position based on AI bias
- Color gradient: Red → Amber → Green
- Label: Current sentiment
- Update: Every 5 minutes

---

### 3.3 Pattern Alert
**Vị trí:** Notifications panel (dropdown)
**Mô tả:** Thông báo khi phát hiện pattern mới

**Layout:**
```
┌─ PATTERN ALERT ───────────────────┐
│  🔔 New Pattern Detected!         │
│  ─────────────────────────────   │
│  FVG BULLISH on M15             │
│  Price: 2845.50                  │
│  Size: 25 pips                   │
│  ─────────────────────────────   │
│  [VIEW CHART]  [DISMISS]         │
└───────────────────────────────────┘
```

**Tính năng:**
- Toast notification style
- Pattern name + type
- Price at detection
- Quick action buttons
- Auto-dismiss 10s
- Sound alert (optional)
- Badge count on icon

**Patterns to detect:**
- FVG (Fair Value Gap)
- OB (Order Block)
- BOS (Break of Structure)
- Liquidity Sweep
- Double Top/Bottom
- Head & Shoulders

---

## NHÓM 5: UX IMPROVEMENTS

### 5.1 Keyboard Shortcuts
**Vị trí:** Hướng dẫn khi hover icon (?) ở header
**Mô tả:** Phím tắt cho thao tác nhanh

**Shortcuts:**
| Key | Action |
|-----|--------|
| `C` | Close selected position |
| `A` | Toggle AI Auto Loop |
| `K` | Kill Switch |
| `E` | Open/Close Equity Chart |
| `M` | Switch MT5 Account |
| `1-9` | Select timeframe |
| `Esc` | Close modal/panel |

**Layout:**
```
┌─ KEYBOARD SHORTCUTS ─────────────┐
│  C    Close Position      Close │
│  A    Toggle AI          Toggle │
│  K    Kill Switch        ⚠️     │
│  E    Equity Chart       Toggle │
│  Esc  Close Modal        Close  │
└──────────────────────────────────┘
```

---

### 5.2 Compact/Expand View
**Vị trí:** Toggle button ở header
**Mô tả:** Chuyển đổi giữa full và compact layout

**Full View (hiện tại):**
```
┌─────────┬─────────┬─────────┐
│ Control │  Chart  │   AI    │
│   +     │  +      │ Brain   │
│ Logs    │ Positions  +     │
│         │         │Copilot  │
└─────────┴─────────┴─────────┘
```

**Compact View:**
```
┌─────────────────────────────────────┐
│ EQ: $10,500 │ P&L: +$234 │ MT5│AI│ │
├─────────────────────────────────────┤
│ Control │ Chart │ Positions │ Copilot │
└─────────────────────────────────────┘
```

**Tính năng:**
- Toggle button trong header
- Smooth transition animation
- Remember preference in localStorage
- Auto-collapse optional

---

### 5.3 Quick Trade Panel
**Vị trí:** Floating button ở góc phải dưới
**Mô tả:** Panel đặt lệnh nhanh

**Layout:**
```
┌─ QUICK TRADE ─────────────────────┐
│  Symbol: [XAUUSD ▼]              │
│  Type:   ○ BUY  ● SELL           │
│  Volume: [0.10] lots            │
│  ─────────────────────────────   │
│  Entry:  [Auto / 2845.50]        │
│  SL:     [50] pips              │
│  TP:     [100] pips             │
│  ─────────────────────────────   │
│  Risk: $25.00 (1%)               │
│  RRR: 2.0:1                     │
│  ─────────────────────────────   │
│  [EXECUTE ORDER]                 │
└───────────────────────────────────┘
```

**Tính năng:**
- Floating button trigger (bottom-right)
- Slide-in panel
- Symbol dropdown
- BUY/SELL toggle
- Volume input
- SL/TP in pips
- Risk preview
- One-click execute
- Validation (confirm dialog)

---

## IMPLEMENTATION ORDER

### Phase 1: Foundation (Không cần backend mới)
1. Risk Calculator
2. Multi-Symbol Watchlist
3. Keyboard Shortcuts
4. Compact/Expand View
5. Quick Trade Panel

### Phase 2: Visualization (Cần API support)
6. Equity Curve Chart
7. Performance Pie Chart
8. Drawdown Chart
9. Monthly Returns Bar
10. Sentiment Gauge

### Phase 3: AI Integration
11. Pattern Alert
12. Trade Journal with AI
13. Correlation Matrix
14. Pip Value Calculator

---

## TECHNICAL NOTES

### API Extensions Needed
```typescript
// /api/performance enhancement
GET /api/performance
Response: {
  ...existing fields,
  equity_curve: Array<{ time: string, value: number }>,
  monthly_returns: Array<{ month: string, pnl: number }>,
  current_drawdown: number,
  max_drawdown: number,
  sentiment: { bullish: number, bearish: number }
}

// /api/market enhancement
GET /api/market?symbols=XAUUSD,EURUSD,GBPUSD
Response: {
  XAUUSD: { price: number, change: number, candles: [] },
  EURUSD: { price: number, change: number, candles: [] },
  ...
}
```

### Performance Considerations
- Lazy load charts
- Debounce frequent updates
- Use CSS transitions (not JS animations)
- Virtual scrolling for long lists

### Responsive Design
- Min-width: 1200px (full features)
- 1024px: Hide correlation matrix
- 768px: Compact view default

---

## OUT OF SCOPE (v3.0)

- Mobile app
- Push notifications
- Multi-account management
- Social trading
- Backtesting interface
