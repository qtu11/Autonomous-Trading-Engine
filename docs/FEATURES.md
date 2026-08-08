# QuantAI - Tổng Hợp Tính Năng & Khả Năng Hệ Thống

Tài liệu này tổng hợp toàn bộ tính năng và khả năng của hệ thống **QuantAI - Autonomous Trading Engine (ATE)**, giúp bạn nắm được hệ thống làm được gì, làm như thế nào và giới hạn của nó.

---

## 1. Các Nhóm Tính Năng

### 1.1. Giao dịch tự động (Automated Trading)

| Tính năng | Chi tiết |
|-----------|----------|
| Cặp giao dịch chính | XAUUSD (Vàng) - symbol broker `XAUUSDm`, Magic 888999 |
| Thực thi lệnh | Hoàn toàn qua MQL5 EA - **không** có script Python/trình duyệt nào gọi lệnh trực tiếp lên broker. Một "Execution Authority". |
| Các loại lệnh hỗ trợ | BUY / SELL / MODIFY_SLTP / CLOSE_POSITION / CLOSE_ALL / CANCEL_PENDING |
| Vòng đời lệnh | `PENDING -> CLAIMED -> EXECUTED / REJECTED / FAILED / EXPIRED` với lease & TTL (mặc định 10s) |
| Chống trùng lệnh | Khóa `idempotency_key` duy nhất + receipt id duy nhất (chống race condition, trùng lệnh) |
| Nút điều khiển | Arming DEMO/LIVE, Kill Switch, AI Auto Loop (bật/tắt vòng lặp tự động) |
| Phân tích thời gian thực | Đa khung thời gian M1 -> D1 |

### 1.2. Trí tuệ nhân tạo đa nền (Multi-AI Engine)

| Tính năng | Chi tiết |
|-----------|---------|
| Provider mặc định | **OpenCode Zen Free Pool** - chạy miễn phí, không cần API Key |
| Model default | `deepseek-v4-flash-free` (có thể đổi; pool hỗ trợ 7+ model free) |
| Failover tự động | Khi provider lỗi (429/400/401/network), tự quay sang provider kế tiếp theo Priority Queue |
| Rotation | Xoay vòng mô hình mỗi lượt gọi; model lỗi vào cooldown 300s rồi được thử lại |
| Provider trả phí (tùy chọn) | Gemini Rotation Pool, OpenAI, DeepSeek, Claude, FlatKey/router cá nhân (GATEWAY_URL + GATEWAY_KEY) |
| AI Copilot | Chat trò chuyện với AI để hỏi về thị trường, chiến lược, trạng thái hệ thống |
| AI News Analysis | Phân tích tin tức kinh tế (CPI, FOMC, NFP, GDP...) và đề xuất phòng thủ (khóa giao dịch, dời SL) |

### 1.3. Phân tích kỹ thuật & mẫu hình (Technical & Pattern Analysis)

- **5 phương pháp giao dịch** đầy đủ: Price Action, SMC, ICT, Sniper, Ultra Confluence (xem [TRADING_METHODS.md](./TRADING_METHODS.md)).
- **72+ mẫu hình thị trường** được phát hiện tự động với cơ chế validate khắt khe:
  - FVG (mô hình 3 nến) + trạng thái FORMING/ACTIVE/PARTIALLY_FILLED/MITIGATED/INVALIDATED.
  - Order Block, Breaker, Mitigation, Rejection Block (body ratio >= 55%, displacement >= 1.5 ATR).
  - BOS, CHoCH, MSS, Swing HH/HL/LH/LL, Trendline, Channel, Range, Liquidity Sweep, Equal Highs/Lows, Kill Zones, OTE, Turtle Soup, Judas Swing...
- **Chấm điểm hội tụ (Confluence Scoring)**: Phối hợp xu hướng + RSI + ATR để ra Confidence %.
- **Cách ly nguồn sự thật (Single Source of Truth)**: Chart SVG ở frontend render từ backend markup, không tự sinh ngẫu nhiên.

### 1.4. Quản lý rủi ro (Fail-Closed RiskGate)

| Tính năng | Chi tiết |
|-----------|---------|
| Bộ lọc RiskGate 15 điểm | Kiểm tra số dư, free margin, spread tối đa, vị thế tối đa (SL/TP hợp lệ), timing, trend, confluence... |
| Fail-Closed | Mọi đề xuất lệnh không vượt qua điều kiện => bị từ chối (REJECT) và ghi log |
| 1% Risk Sizing | Khối lượng lệnh được tính tự động: `Risk = Balance*1%`; `SL Distance = max(3.0, ATR*1.5)`; `Lot = Risk/(SL*100)` |
| Caps | max_daily_loss_fraction = 0.02; spread cap 0.50 (XAUUSD) |
| Công tắc khẩn | Kill switch tức thì từ UI |
| Các chi tiết điều kiện | SYMBOL_VOLUME_MIN/MAX/STEP, STOPS_LEVEL, FREEZE_LEVEL đều được EA kiểm tra lần cuối trước khi gửi lệnh |

### 1.5. Giám sát & giao diện (Dashboard)

| Tính năng | Chi tiết |
|-----------|---------|
| Giao diện | Bloomberg Trading Desk - một màn hình đầy đủ, Dark Glassmorphism |
| Chart | SVG candlestick tự vẽ + lightweight-charts, zoom/pan chuột |
| Telemetry thời gian thực | WebSocket ~1s: equity curve, balance, margin, spread, vị thế mở |
| Control Center | Bật/tắt arming, kill switch, login MT5, config Telegram, xem audit logs |
| Audit Log | Log JSON có cấu trúc, mỗi dòng một sự kiện, xoay vòng theo ngày |
| Báo tin Telegram | Thông báo trade/tin tức qua Telegram Bot |

### 1.6. Kiến trúc Backend an toàn

| Tính năng | Chi tiết |
|-----------|---------|
| Phân quyền Token | `QUANTAI_BRIDGE_TOKEN`(EA) và `QUANTAI_OPERATOR_TOKEN`(UI) tách biệt, chỉ dùng ở backend |
| CORS hạn chế | Chỉ cho phép domain đã khai báo |
| Token không lộ ra browser | Không dùng `NEXT_PUBLIC_*` cho token |
| SQLite WAL | Non-blocking concurrent read; ghi dưới `BEGIN IMMEDIATE` |

---

## 2. Giới hạn & Điều kiện vận hành

1. **Môi trường**: Backend + MT5 tốt nhất chạy trên cùng 1 máy/VPS Windows để latency < 15ms (execution).
2. **MT5 phải bật**: EA phải chạy trong MT5 (terminal timeout mặc định 30s, autostart được cấu hình).
3. **Cần tài khoản broker DEMO**: Khuyến nghị thử nghiệm ở DEMO trước khi chuyển LIVE (LIVE phải bật `QUANTAI_LIVE_ARMED=true` + đồng ý rủi ro).
4. **Spread/news**: Không thể hoàn toàn tránh slippage khi tin tức lớn; RiskGate + EA giảm thiểu.
5. **AI là trợ lý, không phải oracle**: Các lệnh phát sinh từ quyết định định lượng + concurrency; AI Copilot không tự mở lệnh mù.
6. **Rủi ro tài chính**: Luôn đọc [RISK_ANALYSIS.md](./RISK_ANALYSIS.md) và thông báo từ chối trách nhiệm.

---

## 3. Khả năng đo được (mục tiêu hiệu suất)

| Chỉ số | Mục tiêu |
|--------|---------|
| Tick -> Quyết định AI | < 15ms (không bị rớt) |
| Lệnh từ backend -> khớp | < 1s khung (không claim TTL) |
| EA poll / broadcast | 1 giây |
| Broadcast WebSocket | 1 giây cadence |
| Frontend FPS | 60 FPS SVG chart, không block main thread |

Xem chi tiết tại [PERFORMANCE_PLAN.md](./PERFORMANCE_PLAN.md).

---

## 4. Kiến trúc các phân hệ quan trọng (thuyết minh ngắn)

Để có cái nhìn trực quan về mối quan hệ giữa Backend, EA và Dashboard:

```
  ┌──────────────────────────────┐
  │        Next.js Dashboard     │
  │  (Bảng điều khiển US/FX)     │
  └─────────────┬────────────────┘
                │ HTTP + WebSocket
  ┌─────────────▼────────────────┐
  │      FastAPI Backend         │
  │  - MT5 Read Gateway          │
  │  - Strategy/Pattern Engine   │
  │  - Multi-AI Decision Engine │
  │  - RiskGate (Fail-Closed)    │
  │  - CommandStore (SQLite)     │
  └─────────────┬────────────────┘
                │  Bridge REST (Bearer Token)
  ┌─────────────▼────────────────┐
  │   MQL5 Expert Advisor (EA)   │
  │ - Claim command, guard check │
  │ - CTrade execution           │
  │ - Receipt + telemetry        │
  └─────────────┬────────────────┘
                │  Broker terminal
                ▼
         METATRADER 5 / BROKER
```

Chi tiết: [ARCHITECTURE.md](./ARCHITECTURE.md), [MODULES.md](./MODULES.md), [DATA_FLOW.md](./DATA_FLOW.md).

---

## 5. Cấu hình chính trong .env (tổng quan)

| Biến | Vai trò |
|------|---------|
| `MT5_LOGIN/PASSWORD/SERVER/PATH` | Kết nối MT5 terminal |
| `QUANTAI_EXECUTION_MODE` | `DEMO` / `LIVE` / `DISABLED` |
| `QUANTAI_KILL_SWITCH` | Công tắc khẩn |
| `QUANTAI_EXECUTION_SYMBOL` | `XAUUSDm` |
| `QUANTAI_EXECUTION_MAGIC` | `888999` |
| `QUANTAI_DEMO_COMMAND_TTL_SECONDS` | 10s TTL command |
| `OPENAI_API_KEY`, `GEMINI_API_KEY`, `ZPLAY_API_KEY` | Key provider thương mại (tùy chọn) |
| `OPENCODE_BASE_URL` | Zen free endpoint mặc định |
| `QUANTAI_AI_MODEL` | Model mặc định (`deepseek-v4-flash-free`) |
| `GATEWAY_URL`, `GATEWAY_KEY` | Router cá nhân (ưu tiên cao nhất) |
| `ATE_DASHBOARD_PORT/HOST` | Backend custom |
| `ATE_BACKEND_URL` | Nơi dashboard/frontend trỏ vào backend |
| `NEXT_PUBLIC_*` | Cấu hình Firebase web |
| `TELEGRAM_BOT_TOKEN/CHAT_ID` | Thông báo Telegram |

Cấu hình hoàn chỉnh: xem `.env.example` hoặc [OPERATION_GUIDE.md](./OPERATION_GUIDE.md).

---

*Tài liệu thuộc dự án QuantAI - Nguyễn Quang Tú (QTusdev) | MIT License.*