# QuantAI - Phân Rã Các Module Hệ Thống

## 1. Web Frontend Module (`web/`)

| File | Trách nhiệm |
|------|-------------|
| `web/app/page.tsx` | Trang chính single-screen "Bloomberg Trading Desk": ticker thời gian thực, chart nến SVG, AI matrix, bảng vị thế mở, lịch sử giao dịch, lịch kinh tế, Copilot Chat. |
| `web/app/components/TradingChart.tsx` | Chart nến dựa trên lightweight-charts - hiển thị dữ liệu và markup từ backend. |
| `web/app/components/CandleChart.tsx` | Chart SVG tự vẽ, hỗ trợ zoom/pan, render 2000 nến không block main thread. |
| `web/app/components/ControlCenter.tsx` | Control Center: arming (DEMO/LIVE), kill switch, risk policy override, MT5 login setup, Telegram bot config, audit log viewer. |
| `web/lib/api.ts` | Client API layer: TypeScript types cho mọi endpoint, WebSocket handler auto-reconnect backoff. |

## 2. FastAPI Backend Module (`dashboard/`)

| Module/File | Trách nhiệm |
|-------------|-------------|
| `server.py` | Điểm khởi chạy: gắn MT5 terminal, tạo telemetry, AI decision loop, interlocks, HTTP routing, CORS, lifespan lifecycle. |
| `command_store.py` | Command store idempotent trên SQLite WAL (`quantai_commands.sqlite3`). Quản lý atomic creation, lease claims, execution receipts. |
| `risk_gate.py` | RiskGate: equity/free margin/daily cap/spread cap/position limit/volume quantization/đúng hướng SLTP. |
| `risk_profiles.py` | Hồ sơ rủi ro theo symbol: XAUUSDm cap spread 0.50, EURUSD cap spread 0.0002... |
| `strategy_core.py` | Engine thuật toán thuần: EMA20/50/200 trend, RSI momentum, ATR volatility confluence. |
| `detectors.py` | Pattern lõi: FVG (3 nến), Order Block, BOS, CHoCH, Swing. |
| `advanced_detectors.py` | Pattern nâng cao: ICT (OTE, Killzones, Judas Swing, SMT...), Price Action nến, SMC mở rộng. |
| `chart_markup.py` | Build markup JSON cho chart frontend. |
| `signal_engines.py` | Sinh tín hiệu 5 phương pháp: PA, SMC, ICT, Sniper, Ultra Confluence. |
| `performance.py` | Realtime equity curve & KPI: Win Rate, Profit Factor, Max Drawdown, Recovery Factor. |
| `ws_hub.py` | WebSocket connection manager broadcast telemetry ~1s. |
| `logging_config.py` | Logger JSON có cấu trúc, ghi ra `logs/quantai_YYYYMMDD.log`. |
| `tests/test_market_analysis.py` | Test đơn vị cho Market Analysis Engine. |

## 3. MQL5 Expert Advisor Module (`QuantAI_XAUUSD.mq5`)

| Thành phần | Trách nhiệm |
|------------|-------------|
| Timer loop | `EventSetTimer(1)` - chạy mỗi 1 giây. |
| Telemetry | Gửi `POST /api/telemetry`: balance, equity, margin, profit, positions, ask, bid. |
| Command claim | Gọi `POST /api/v1/bridge/commands/claim` để nhận lệnh PENDING. |
| Local Guard | Kiểm tra account login/server, symbol, magic, spread, stop level, volume step... |
| CTrade | `CTrade.Buy()`, `Sell()`, `PositionModify()`, `PositionClose()`, `OrderDelete()` - quyền thực thi duy nhất. |
| Receipt | Gửi `POST /api/v1/bridge/commands/{command_id}/receipt`. |

## 4. Mối quan hệ giữa các module (dependencies)

```text
server.py (FastAPI)
   ├── command_store.py  (SQLite ledger)
   ├── risk_gate.py + risk_profiles.py  (risk evaluation)
   ├── strategy_core.py + signal_engines.py  (technical)
   ├── detectors.py + advanced_detectors.py  (pattern)
   ├── chart_markup.py     (frontend objects)
   ├── ws_hub.py          (broadcast)
   ├── performance.py      (KPIs)
   └── logging_config.py   (logging)
        │
        ▼ EA (QuantAI_XAUUSD.mq5) -- claim/telemetry/receipt --► server.py
```

---

*Tài liệu thuộc dự án QuantAI - Nguyễn Quang Tú (QTusdev) | MIT License.*