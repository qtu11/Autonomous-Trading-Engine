# Autonomous Trading Engine (ATE) - Tài Liệu Kỹ Thuật & Model Engine

## Bản Quyền Và Quyền Sở Hữu Trí Tuệ

- **Tên dự án**: QuantAI - Autonomous Trading Engine (ATE) for XAUUSD
- **Tác giả / Lead Developer**: Nguyễn Quang Tú (QTusdev)
- **GitHub Repository**: https://github.com/qtu11/Autonomous-Trading-Engine
- **Phiên bản tài liệu**: 3.0.0 (cập nhật 2026)
- **Giấy phép**: MIT License (xem [COPYRIGHT.md](./COPYRIGHT.md) và file `LICENSE` tại thư mục gốc)

---

## I. Tổng Quan Kiến Trúc Hệ Thống (System Architecture)

QuantAI được thiết kế theo mô hình **Hybrid Architecture** phân rã trách nhiệm cao, tối ưu hóa hiệu suất xử lý dữ liệu thời gian thực và quản lý quyết định thông minh. Hệ thống gồm ba phân hệ lõi hoạt động đồng bộ:

```
                  ┌───────────────────────────────────────────────┐
                  │          MetaTrader 5 (Windows Host)          │
                  │   MQL5 Expert Advisor (QuantAI_XAUUSD.mq5)     │
                  └──────┬────────────────────────────────┬───────┘
                         │ (Push Telemetry / HTTPS Post)  │ (Fetch Commands / HTTP Post)
                         ▼                                ▼
                  ┌───────────────────────────────────────────────┐
                  │           FastAPI Analytics Engine            │
                  │            (Python Web Backend)               │
                  └──────┬────────────────────────────────▲───────┘
                         │ (Broadcast State / WebSockets) │ (Control Commands / REST)
                         ▼                                │
                  ┌───────────────────────────────────────┴───────┐
                  │             Next.js UI Dashboard              │
                  │             (Bloomberg Terminal Style)        │
                  └───────────────────────────────────────────────┘
```

1. **Phân hệ thực thi (MQL5 EA)** - chạy trực tiếp trên MetaTrader 5 (Windows). Thu thập giá (Ask/Bid/Spread), số dư, vị thế mở; gửi telemetry qua HTTPS và poll nhận lệnh được duyệt để thực thi.
2. **Phân hệ Analytics & Logic Engine (FastAPI Backend)** - trung tâm xử lý định lượng: tính chỉ báo kỹ thuật, vận hành Pattern Engine (72+ mẫu hình), Multi-AI Decision Router, và **RiskGate fail-closed** trước khi tạo lệnh.
3. **Phân hệ Visualisation UI (Next.js Dashboard)** - giao diện web Bloomberg-style hiển thị dữ liệu realtime qua WebSocket, cho phép giám sát toàn bộ hoạt động bot và tương tác qua AI Copilot.

---

## II. Phân Hệ Đa Mô Hình AI & Công Cụ Định Tuyến (Multi-AI Provider & Model Engine)

ATE trang bị một lớp trừu tượng hóa model LLM (LLM Abstraction Layer) mạnh mẽ, có khả năng tích hợp, xoay vòng và phòng vệ lỗi API.

### 1. Phân Lớp Mô Hình Mặc Định (OpenCode Zen Free Pool)

- Hệ thống mặc định chạy trên hạ tầng cloud miễn phí qua cổng API OpenCode Zen, **không cần API Key**.
- Các model được hỗ trợ:
  - **DeepSeek V4 Flash Free** - model mặc định, tối ưu cho tốc độ phân tích.
  - **Big Pickle Free (Stealth Reasoning)** - suy luận phức tạp.
  - MiMo V2.5 Free, Nemotron 3 Ultra Free, North Mini Code Free, Laguna S 2.1 Free, LongCat 2.0 Free.
- Endpoint: `https://opencode.ai/zen/v1/chat/completions`

### 2. Danh Sách Các Họ Model AI Hỗ Trợ Tích Hợp Ngoài

Người dùng có thể cấu hình API Key từ các nhà cung cấp thương mại để nâng hiệu suất suy luận:

- **OpenAI (GPT Series)**: GPT-4o, GPT-4.1, o3, o4-mini, GPT-5.x...
- **Anthropic (Claude Series)**: Claude 3.5/3.7 Sonnet, Claude Opus, Claude 4.8, Claude 5.x...
- **Google DeepMind (Gemini Series)**: Gemini 2.5 Pro, Gemini 3.x (Flash/Pro), Gemini 3.6...
- **DeepSeek**: DeepSeek V3.x/V4, R1 (Thinking).
- **xAI (Grok)**, **Kimi**, **Qwen**, **GLM**, **MiniMax**, **Llama**, **Mistral**, **Phi**, **Nemotron**, **Granite**, **Gemma**...

(Lưu ý: tên model phải theo danh sách nhà cung cấp hỗ trợ tại thời điểm cấu hình.)

### 3. Khả Năng Định Tuyến Linh Hoạt (API Gateway Routing)

- **Hỗ trợ Gateway**: OpenRouter, Together AI, SiliconFlow, Groq, Fireworks AI, Cerebras, Cloudflare Workers AI, GitHub Models, DeepInfra...
- Chỉ cần set `GATEWAY_URL` + `GATEWAY_KEY`, hệ thống tự đóng gói payload và forward.

### 4. Thuật Toán Phòng Vựa Lỗi Token (Auto Failover & Rotation)

Khi model lỗi (429/400/401/timeout/network) → Auto Failover Engine chuyển sang provider kế theo Priority Queue (xem [AI_PIPELINE.md](./AI_PIPELINE.md)).

---

## III. Logic Phân Tích Định Lượng & Vai Trò Của AI

Dự án được thiết kế theo triết lý **Database-First** + **Quantitative-First**, đặt độ tin cậy và tính nhất quán toán học lên hàng đầu.

### 1. Cơ Chế Tín Hiệu Thuần Thuật Toán (Quantitative Engines)

- **SMC**: `detectors.py` + `advanced_detectors.py` phân tích nến OHLC, định vị Swing High/Low, nhận diện BOS, CHoCH, FVG, Order Block.
- **ICT**: module định vị phiên giao dịch (Killzones), thuật toán Judas Swing, tối ưu điểm vào OTE Fibonacci 62-79%.
- **Sniper**: EMA 9/21 Ribbon + VWAP + RSI + MACD + ADX, retest về ribbon/VWAP.
- **Ultra Confluence**: matrix 5 lớp có trọng số.
- Chi tiết: [TRADING_METHODS.md](./TRADING_METHODS.md)

### 2. Bộ Lọc Rủi Ro Cương Quyết (15-Point Risk Gate)

Trước khi bất kỳ lệnh nào được ghi vào CommandStore, mọi đề xuất buộc qua `risk_gate.evaluate_risk()`:

- **Kiểm tra biên độ tài khoản**: free margin đủ, drawdown <= max_daily loss cap.
- **Kiểm tra rủi ro/lệnh**: lot size tính theo SL/ATR để mất tối đa ~1%.
- **Kiểm tra điều kiện thị trường**: spread quá cao / thanh khoản thấp → từ chối.

### 3. Vai Trò AI Trong Hệ Thống

1. **AI Copilot Assistant** - chat với trader: trạng thái thị trường, thử nghiệm config, trả lời câu hỏi về hệ thống.
2. **AI News & Calendar Analytics** - quét lịch kinh tế MT5; khi có tin high-impact (CPI, FOMC, NFP...) AI phân tích và đưa ra khuyến nghị: khóa lệnh mới, dời SL về hòa vốn, hoặc đóng lệnh trước công bố 15 phút.

---

## IV. Tích Hợp Dự Án & Cấu Hình Nhanh

### 1. Biến Môi Trường (.env)

```properties
# AI mặc định (free)
OPENCODE_BASE_URL=https://opencode.ai/zen/v1/chat/completions
QUANTAI_AI_MODEL=deepseek-v4-flash-free

# Key thương mại (tùy chọn)
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
OPENAI_API_KEY=YOUR_OPENAI_API_KEY

# Router cá nhân (ưu tiên cao nhất)
GATEWAY_URL=https://openrouter.ai/api/v1
GATEWAY_KEY=sk-or-xxxx

# Địa chỉ backend
ATE_BACKEND_URL=http://127.0.0.1:8005
ATE_DASHBOARD_PORT=8005
```

Tham chiếu đầy đủ: `.env.example` và [OPERATION_GUIDE.md](./OPERATION_GUIDE.md).

### 2. Tổ Chức Thư Mục

```
tradeAI/
+-- dashboard/                 # Backend (Python FastAPI)
|   +-- server.py              # Điểm khởi chạy API & AI loop
|   +-- strategy_core.py       # Logic giao dịch lõi
|   +-- signal_engines.py      # Bộ máy tín hiệu (SMC/ICT/Sniper...)
|   +-- detectors.py           # Pattern lõi
|   +-- advanced_detectors.py  # Pattern nâng cao
|   +-- risk_gate.py           # Bộ lọc rủi ro 15 điểm
|   +-- command_store.py       # Sổ cái lệnh idempotent
+-- web/                       # Dashboard (Next.js)
+-- MQL5/Experts/tradeAI/QuantAI_XAUUSD.mq5   # EA
+-- docs/                      # Thư mục tài liệu này
```

---

*Tài liệu thuộc dự án QuantAI - Nguyễn Quang Tú (QTusdev) | MIT License.*