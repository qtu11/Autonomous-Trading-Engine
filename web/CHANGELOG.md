# ATE Trading Desk - Changelog

## v3.0 - Feature Rich Dashboard

### Tính năng mới

#### NHÓM 1: Data Visualization
| # | Tính năng | File | Mô tả |
|---|-----------|------|--------|
| 1.1 | Equity Curve | `EquityCurve.tsx` | Line chart theo dõi equity |
| 1.2 | Performance Pie | `PerformanceCharts.tsx` | Pie chart Win/Loss |
| 1.3 | Drawdown Chart | `PerformanceCharts.tsx` | Area chart drawdown |
| 1.4 | Monthly Returns | `PerformanceCharts.tsx` | Bar chart returns tháng |

#### NHÓM 2: Trading Tools
| # | Tính năng | File | Mô tả |
|---|-----------|------|--------|
| 2.1 | Risk Calculator | `RiskCalculator.tsx` | Tính lot size, risk |
| 2.2 | Pip Value Calc | `RiskCalculator.tsx` | Giá trị pip các cặp |
| 2.3 | Watchlist | `Watchlist.tsx` | Theo dõi 6 cặp |
| 2.4 | Correlation Matrix | `Watchlist.tsx` | Ma trận tương quan |

#### NHÓM 3: AI Enhancements
| # | Tính năng | File | Mô tả |
|---|-----------|------|--------|
| 3.1 | Trade Journal + AI | `TradeJournal.tsx` | AI ghi chú trade |
| 3.2 | Sentiment Gauge | `SentimentGauge.tsx` | Đồng hồ sentiment |
| 3.3 | Pattern Alert | `PatternAlert.tsx` | Toast alert pattern |

#### NHÓM 5: UX Improvements
| # | Tính năng | File | Mô tả |
|---|-----------|------|--------|
| 5.1 | Keyboard Shortcuts | `page.tsx` | Phím tắt C,A,K,E,M,Q |
| 5.2 | Compact View | `page.tsx` | Toggle compact/expand |
| 5.3 | Quick Trade Panel | `QuickTradePanel.tsx` | Floating panel đặt lệnh |

### Components List
```
app/components/
├── ControlCenter.tsx     # MT5, Controls, Actions (238 lines)
├── EconomicCalendar.tsx  # Lịch kinh tế (249 lines)
├── EquityCurve.tsx        # Equity chart (206 lines)
├── PerformanceCharts.tsx  # Pie, Drawdown, Monthly (215 lines)
├── RiskCalculator.tsx    # Risk calc (170 lines)
├── SentimentGauge.tsx     # Gauge (135 lines)
├── TradeJournal.tsx       # Journal (281 lines)
├── Watchlist.tsx          # Watchlist + Correlation (178 lines)
├── PatternAlert.tsx       # Alerts (162 lines)
├── QuickTradePanel.tsx    # Trade panel (218 lines)
└── TradingChart.tsx       # Chart (633 lines)
```

### Keyboard Shortcuts
| Key | Action |
|-----|--------|
| `C` | Close position |
| `A` | Toggle AI Loop |
| `K` | Kill Switch |
| `E` | Toggle Chart |
| `M` | Toggle Compact/Expand |
| `Q` | Quick Trade Panel |
| `1-5` | Switch Timeframe |
| `?` | Show shortcuts |
| `Esc` | Close modal |

---

## v2.5.0
- Notifications system
- Performance metrics
- AI signal details
- Chart toggle
- Recent decisions

## v2.4.0
- Clean unused files
- Rewrite components
- Fix TypeScript errors

## v2.0.0
- AI Brain integration
- MT5 Terminal connection
- Multi-timeframe charts
- Economic calendar
- AI Copilot chat
