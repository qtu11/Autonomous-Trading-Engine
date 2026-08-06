# Autonomous Trading Engine (ATE) - By QTusdev (Nguyễn Quang Tú)

> **Tác giả / Lead Developer**: Nguyễn Quang Tú (QTusdev)  
> **GitHub**: [https://github.com/qtu11/Autonomous-Trading-Engine](https://github.com/qtu11/Autonomous-Trading-Engine)  
> **Trạng thái an toàn mặc định: `DISABLED`.** Hệ thống giao dịch tự động định lượng đa mô hình AI (Multi-AI Quantitative Trading Engine) & MT5 Execution Bridge dành riêng cho XAUUSD (Gold).

Autonomous Trading Engine (ATE) là một nền tảng giao dịch định lượng cao cấp tích hợp **Multi-AI Engine (OpenAI GPT-5.6 / o-series, Anthropic Claude 5, Google Gemini 3.6, DeepSeek V4 Pro, xAI Grok 4.5, Kimi K3, Qwen3.8 Max)**, **Deterministic Confluence Strategy Core**, **Multi-layer Fail-Closed RiskGate**, **SQLite Audit Command Ledger** và **Pure MQL5 EA Execution Bridge (`ATE_XAUUSD.mq5`)** trên MetaTrader 5 (MT5).

---

## ⚡ Tính năng nổi bật & Kiến trúc lõi

### 1. Multi-AI Provider & Model Engine (2026 Ready)
- **Đa dạng họ mô hình AI hàng đầu**:
  - **OpenAI**: `GPT-5.6 Sol ⭐ (Flagship 07/2026)`, `GPT-5.6 Terra`, `GPT-5.6 Luna`, `GPT-5.5`, `GPT-5.4`, `o3`, `o3-pro`, `o4-mini`, `GPT-4.1`, `GPT-4o`, `GPT-4o Mini`.
  - **Anthropic**: `Claude Fable 5 ⭐ (Flagship)`, `Claude Mythos 5`, `Claude Opus 5`, `Claude Sonnet 5`, `Claude 4.8`, `Claude 3.7 Sonnet`, `Claude 3.5 Sonnet`.
  - **Google DeepMind**: `Gemini 3.6 Flash ⭐ (Mới nhất)`, `Gemini 3.5 Flash`, `Gemini 3.1 Pro`, `Gemini 3 Pro`, `Gemini 2.5 Pro`, `Gemini 2.0 Flash`, `Gemini 1.5 Pro`.
  - **DeepSeek**: `DeepSeek V4 Pro ⭐`, `DeepSeek V4 Flash (0731)`, `DeepSeek V3.2`, `DeepSeek V3.1`, `DeepSeek V3`, `DeepSeek R1 (Thinking Mode)`.
  - **xAI (Grok)**: `Grok 4.5 ⭐ (Flagship)`, `Grok 4`, `Grok 4.3`, `Grok 4.20`, `Grok 4 Fast`, `Grok 3`.
  - **Moonshot AI & Alibaba Qwen**: `Kimi K3 ⭐`, `Kimi K2.6`, `Kimi K2 Thinking`, `Qwen3.8 Max ⭐`, `Qwen3 Thinking/Coder/VL/235B`.
  - **Zhipu GLM, MiniMax, Meta Llama, Mistral, Open Source**: `GLM-5.2 ⭐`, `MiniMax M3 ⭐`, `Llama 4 Maverick ⭐`, `Mistral Magistral Medium ⭐`, `Codestral`, `Microsoft Phi-4`, `Cohere Command A`, `AI21 Jamba Large`, `NVIDIA Nemotron Ultra`, `IBM Granite 4`, `Gemma 3`.
- **Tùy Chọn Custom Model Name**: Cho phép gõ bất kỳ chuỗi model ID tùy chỉnh nào.
- **Tích Hợp API Gateway Router**: Kết nối trực tiếp đến các router trung gian (`OpenRouter`, `Together AI`, `SiliconFlow`, `Groq`, `Fireworks AI`, `Cerebras`, `Cloudflare Workers AI`, `GitHub Models`, `DeepInfra`, v.v.).
- **Auto Token Failover (Tự Động Đổi Key Khi Hết Token)**: Khi mô hình ưu tiên gặp lỗi `429 Too Many Requests` / hết quota / timeout, hệ thống tự động xoay vòng sang key/provider tiếp theo trong hàng đợi không gián đoạn luồng xử lý (`User Custom Gateway` → `User Custom Model` → `Gemini` → `OpenAI` → `FlatKey`).

### 2. RiskGate & Bảo Vệ Tài Khoản Lớp Kép (Defense-in-Depth Fail-Closed)
- **Kiểm soát rủi ro nghiêm ngặt**:
  - Công thức tính khối lượng lệnh chuẩn 1% Risk / Account Lot formula.
  - Khóa chế độ `DISABLED`, `DEMO`, `LIVE` bằng nhiều lớp kiểm tra độc lập (`ATE_LIVE_ARMED=true`, kill switch, account allowlist).
  - Tự động dừng giao dịch khi phát hiện nến sụt giảm peak-to-trough (Max Drawdown Limit), dãn spread (Max Spread Cap), hoặc chuỗi thua liên tiếp (Consecutive Loss Mitigation).

### 3. Giao Diện Bloomberg Trading Terminal Modern Web UI
- Giao diện Next.js App Router, Bloomberg Terminal dark theme, glassmorphism hiệu ứng mượt mà.
- Bảng điều khiển Control Center (`[CFG]`) tập trung quản lý tài khoản MT5, cấu hình rủi ro, kết nối Telegram bot realtime alert và thiết lập AI Engine.

### 4. Realtime Stream & Command Ledger
- **WebSocket Hub**: Truyền dữ liệu telemetry ~1s thời gian thực đến giao diện web client qua `ws://localhost:8080/ws/stream` (bản local) hoặc `<public>:8848/ws/stream` (bản cloud).
- **SQLite WAL Command Ledger**: Đảm bảo tính chống lặp lệnh (Idempotency), ghi lại toàn bộ nhật ký giao dịch và lệnh điều phối.

### 5. Pure MQL5 EA Execution Bridge (`ATE_XAUUSD.mq5`)
- EA MQL5 là thành phần duy nhất có quyền thực thi lệnh `CTrade` trên MT5.
- Tự động re-validate thông số broker, kiểm tra spread, nến bão tin tức trước khi khớp lệnh.

---

## 📐 Kiến trúc dòng dữ liệu (Data Architecture)

```text
┌────────────────────────────────────────────────────────┐
│ Next.js Web Terminal (web/)                            │
│ - Bloomberg Dark UI & Control Center [CFG]             │
│ - Multi-AI Model & API Gateway Configurator            │
└───────────────────────────┬────────────────────────────┘
                            │ WebSocket / REST API
┌───────────────────────────▼────────────────────────────┐
│ FastAPI Backend Engine (dashboard/server.py)           │
│                                                        │
│ Multi-AI Router → Strategy Core → RiskGate → CommandStore
│     │                 │              │            │    │
│ (Failover)      (Proposals)     (Fail-Closed) SQLite WAL
└───────────────────────────┬────────────────────────────┘
                            │ Bearer Auth Local Bridge API
┌───────────────────────────▼────────────────────────────┐
│ ATE_XAUUSD.mq5 (MQL5 EA Bridge)                        │
│ - Pure broker execution authority via CTrade           │
│ - Re-validates account, symbol, spread & news caps     │
└────────────────────────────────────────────────────────┘
```

---

## 📁 Cấu trúc dự án

```text
Autonomous-Trading-Engine/
├── ATE_XAUUSD.mq5            # MQL5 EA Bridge mới nhất cho MetaTrader 5
├── QuantAI_XAUUSD.mq5        # MQL5 EA Legacy Bridge
├── dashboard/
│   ├── server.py             # FastAPI backend API, WebSocket Hub, Multi-AI Engine
│   ├── command_store.py      # SQLite WAL command ledger
│   ├── strategy_core.py      # Deterministic strategy proposals (BUY/SELL/NO_TRADE)
│   ├── risk_gate.py          # Multi-layer fail-closed policy evaluation
│   ├── risk_profiles.py      # Risk profiles per symbol/instrument
│   ├── logging_config.py     # JSON-per-line structured logging system
│   ├── performance.py        # Win-rate, drawdown & KPI calculator
│   └── brain.py              # AI decision evaluation engine
├── backtest/                 # Backtest scripts & evaluation metrics
├── tests/
│   ├── test_quantai_core.py  # ATE core unit & integration test suite (ATECoreTests)
│   ├── test_new_modules.py   # Unit tests for logging, WebSocket, calendar, modes
│   └── fixtures/             # Sample CSV historical bar data
├── web/                      # Next.js Web Terminal Frontend
│   ├── app/
│   │   ├── page.tsx          # Main Bloomberg Trading Desk dashboard
│   │   ├── login/page.tsx    # Admin login & Firebase Auth persistent session
│   │   └── components/       # ControlCenter, EconomicCalendar, etc.
│   ├── lib/api.ts            # Typed API client contracts
│   └── package.json          # Next.js frontend dependencies
├── .env.example              # Template cho tệp cấu hình môi trường (.env)
├── .gitignore                # Quản lý git exclude an toàn (không chứa secret)
├── start.ps1                 # Single-command full-stack launcher script (PowerShell)
├── start.bat                 # Single-command launcher script (Batch)
└── README.md
```

---

## Yêu cầu môi trường

- **Windows 11** (được thiết kế cho môi trường MetaTrader 5 Windows).
- **Python 3.11+** (project đã chạy với Python hiện có; nên dùng venv riêng).
- **Node.js 20+** và npm.
- MetaTrader 5 Terminal và MetaEditor.
- Một **tài khoản demo** đã được cho phép rõ ràng nếu thực hiện demo canary.

Python backend cần tối thiểu:

```text
fastapi
uvicorn
pydantic
MetaTrader5  # chỉ cần cho đường đọc MT5/demo bridge
```

Frontend dùng Next.js và TypeScript; dependencies được khai báo tại `web/package.json`.

---

## Cài đặt và khởi động

### 1. Tạo môi trường Python

Tại thư mục dự án:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install fastapi uvicorn pydantic MetaTrader5
```

> Không cần `MetaTrader5` để chạy core unit tests/backtest offline, nhưng backend telemetry sẽ hiển thị `UNAVAILABLE` khi package hoặc terminal không có.

### 2. Cài dependencies frontend

```powershell
npm --prefix web install
```

### 3. Tạo cấu hình local

```powershell
Copy-Item .env.example .env
```

Giữ cấu hình mặc định an toàn. Điền secret chỉ trong `.env` local, không commit file này.

### 4. Chạy backend

```powershell
python dashboard/server.py
```

Backend chỉ bind `127.0.0.1`, cổng mặc định `8005`.

### 5. Chạy dashboard

Mở terminal khác:

```powershell
npm --prefix web run dev
```

Dashboard mặc định tại `http://localhost:3000`.

### 6. Khởi động toàn bộ hệ thống bằng một lệnh (khuyến nghị)

`start.ps1` dựng toàn bộ chuỗi và tự kiểm chứng từng mắt xích trước khi mở dashboard:

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

Script thực hiện tuần tự:

1. Giải phóng cổng `8005` (backend) và `3000` (frontend).
2. Biên dịch EA `QuantAI_XAUUSD.mq5 → .ex5` qua `MetaEditor64.exe` (dừng và báo lỗi nếu compile fail; backup `.ex5` cũ trước).
3. Đảm bảo MT5 terminal đang chạy (khởi động nếu chưa).
4. Khởi động backend FastAPI (cổng `8005`).
5. Cài `node_modules` nếu thiếu rồi khởi động dashboard Next.js (cổng `3000`).
6. Health-check `GET /api/control-center/status` cho tới khi `mt5_connected=true` (timeout rõ ràng), in bảng trạng thái từng mắt xích.
7. Mở dashboard trên trình duyệt.

> `start.bat` vẫn còn để tương thích, nhưng `start.ps1` là đường khuyến nghị vì có bước biên dịch EA + verify sức khỏe hệ thống.

### 7. Nạp EA vào MT5 (một lần)

1. Mở MT5 terminal → chart `XAUUSDm`.
2. Kéo `QuantAI_XAUUSD` (hoặc `ATE_XAUUSD`) từ Navigator (Experts) vào chart.
3. Trong tab **Common**: bật **Allow Algo Trading**.
4. Trong **Inputs**: điền `InpApiUrl=https://autonomous-trading-engine.vercel.app/api/v1/`, `InpBridgeToken=<QUANTAI_BRIDGE_TOKEN trong .env>`, giữ `InpExecutionEnabled=false` cho tới khi sẵn sàng arm demo.
5. Vào **Tools → Options → Expert Advisors**: thêm `https://autonomous-trading-engine.vercel.app` vào danh sách **Allow WebRequest for listed URL**.

---

## Cấu hình

Sao chép `.env.example` thành `.env`; đây là các nhóm biến quan trọng.

### Runtime và network

| Biến | Mặc định | Ý nghĩa |
|---|---:|---|
| `QUANTAI_EXECUTION_MODE` | `DISABLED` | Mode runtime: giữ `DISABLED` trừ khi đang demo được phê duyệt. |
| `QUANTAI_DASHBOARD_PORT` | `8005` | Cổng FastAPI localhost. |
| `NEXT_PUBLIC_QUANTAI_API_ORIGIN` | `http://127.0.0.1:8005` | Origin API frontend sử dụng. Không đưa secret vào biến `NEXT_PUBLIC_*`. |
| `QUANTAI_ALLOWED_ORIGINS` | localhost:3000 | CORS allowlist phân cách bởi dấu phẩy. |
| `QUANTAI_COMMAND_DB` | `dashboard/quantai_commands.sqlite3` | Đường dẫn ledger SQLite; file runtime bị ignore. |

### Execution safety interlocks

| Biến | Mặc định | Ý nghĩa |
|---|---:|---|
| `QUANTAI_DEMO_ARMED` | `false` | Phải là `true` mới có thể xét demo issuance. |
| `QUANTAI_KILL_SWITCH` | `true` | `true` chặn mọi command demo mới. |
| `QUANTAI_DEMO_LOGIN` | demo allowlist | Login demo được phép. |
| `QUANTAI_DEMO_SERVER` | demo allowlist | Server demo được phép. |

### ## Quy trình quyết định và thực thi

### 1. Phương pháp Giao dịch Cốt lõi (Core Trading Strategy)

Hệ thống AI sử dụng phương pháp giao dịch **GoldQuant Multi-Timeframe Trend Confluence & Breakout Pyramiding (Hội tụ Xu hướng Đa khung thời gian & Nhồi lệnh Bứt phá Rủi ro Cố định)** chuyên biệt cho thị trường Vàng ($XAUUSDm$):

- **Xác định Xu hướng Đa khung (Multi-Timeframe Structure Alignment)**:
  - Sử dụng bộ 3 đường trung bình động hàm mũ `EMA20`, `EMA50`, `EMA200` trên các khung thời gian `M15`, `H1`, `H4`.
  - **Tín hiệu BUY**: Xuất hiện khi `EMA20 > EMA50 > EMA200` và `RSI(14)` nằm trong vùng tăng trưởng ($40 \le RSI \le 85$).
  - **Tín hiệu SELL**: Xuất hiện khi `EMA20 < EMA50 < EMA200` và `RSI(14)` nằm trong vùng giảm giá ($15 \le RSI \le 60$).
- **Lọc biến động & Độ nén giá (Volatility & Momentum Filter)**:
  - Kiểm tra biến động bằng `ATR(14)` trên M15. Nếu $ATR \le 0.50$ (thị trường quá phẳng/thắt cổ chai mất thanh khoản), AI tự động hạ về `NO_TRADE` để tránh dính trap bẫy giá.

### 2. Cơ chế AI Tự động Quyết định Khi Nào & Chọn Loại Lệnh (Decision & Order Type Selection)

Vòng lặp AI (`_ai_decision_loop` hoặc Manual Scan mỗi 2 phút) tự động quét thị trường và phân loại lệnh dựa trên vị thế của giá so với vùng cản:

```text
                                  ┌───────────────────────────────┐
                                  │ Phân tích Đa khung M15/H1/H4  │
                                  └───────────────┬───────────────┘
                                                  │
                                   ┌──────────────┴──────────────┐
                                   ▼                             ▼
                        [Đạt điều kiện Confluence]     [Thiếu Confluence/Nhiễu]
                                   │                             │
                        ┌──────────┴──────────┐                  ▼
                        ▼                     ▼              NO_TRADE
                [Phá Cản / Breakout]   [Nén Cản / Test EMA]
                        │                     │
                        ▼                     ▼
                 Market Order           Pending Order
               (BUY / SELL Deal)     (Stop / Limit Order)
```

1. **Market Deal (Lệnh Thị trường)**:
   - **Khi nào chọn**: Giá nến M15 đã hoàn tất phá vỡ (Breakout) cản tĩnh/động ngay tại thời điểm quét.
   - **Thực thi**: Phát lệnh `BUY` hoặc `SELL` trực tiếp với độ trễ tối thiểu qua `mt5.order_send()`.
2. **Pending Buy Stop / Sell Stop (Lệnh Chờ Bứt Phá Cản)**:
   - **Khi nào chọn**: Giá đang tích lũy nén phía dưới đường cản (Ví dụ: AI nhận định *"BUY nếu phá 2368.50"* trong khi giá hiện tại đang ở `2365.00`).
   - **Thực thi**: AI tự động đặt lệnh **Buy Stop tại 2368.50** (hoặc Sell Stop tại đáy cản). Chỉ khi lực mua thực sự đánh bứt phá mốc `2368.50`, lệnh trên MT5 mới kích hoạt.
3. **Pending Buy Limit / Sell Limit (Lệnh Chờ Hồi Test Pullback)**:
   - **Khi nào chọn**: Thị trường bứt phá mạnh nhưng giá chạy quá xa đường hỗ trợ `EMA20` (vùng quá mua/quá bán).
   - **Thực thi**: AI đặt lệnh **Buy Limit tại vùng EMA20/Fibonacci** đón nhịp re-test trước khi đà tăng tiếp diễn.
4. **Cơ chế Hủy lệnh Chờ Tự động (Pending Lifecycle & TTL)**:
   - Tất cả các lệnh Pending đều được gán `ttl_seconds` (Thời gian sống). Nếu sau 15-30 phút giá đi ngang hỏng mô hình nén, AI phát lệnh `CANCEL_PENDING` xóa lệnh trên MT5 để loại bỏ nguy cơ dính trượt giá (Slippage).

### 3. Quy trình Quản lý Vị thế & Bảo vệ Lợi nhuận Tự động (Dynamic Risk & Trade Management)

- **Cơ chế Dời SL Hòa vốn Ngăn giá quay đầu (Break-Even Lock)**:
  - Khi vị thế đạt lợi nhuận $\ge +1.0\$$ Vàng (10 pips / 100 points), AI tự động dời Stop Loss lên `entry + 0.10$` (Khóa vị thế Risk-Free 0% rủi ro âm tiền).
- **Cơ chế Trailing Stop Khóa Lợi nhuận Cuốn chiếu (Step Trailing + EMA20)**:
  - Khi giá bứt phá mạnh (ví dụ $+15.0\$$ Vàng), AI tự động cuộn SL bám sát phía sau giá ($current\_price - 1.50\$$ hoặc đường `EMA20 - 1.5*ATR`), bảo vệ 100% thành quả lợi nhuận.
- **Cơ chế Nhồi Lệnh An toàn (Risk-Gated Pyramiding)**:
  - AI chỉ quyết định nhồi thêm vị thế khi: Vị thế trước đã được dời SL về hòa vốn + Tổng rủi ro Margin toàn bộ các lệnh nhồi không vượt quá 30% toàn bộ Margin khả dụng.
- **Tự động Đóng lệnh Khẩn cấp khi Đảo chiều (AI Trend Failure Auto-Close)**:
  - Nếu đường `EMA20` cắt ngược `EMA50` hoặc nến đảo chiều mạnh phá vỡ kịch bản, AI lập tức phát lệnh đóng vị thế khẩn cấp tại giá thị trường để bảo vệ vốn.

### 4. Strategy Core Code Structure

`dashboard/strategy_core.py` là pure function nhận indicators và quotes để tạo proposal deterministic.

### 5. RiskGate Guard

`dashboard/risk_gate.py` nhận proposal, account snapshot, symbol spec, quote, số vị thế và policy. Chỉ `approved=True` mới có thể tiếp tục tạo command.

### 6. Command ledger & EA Boundary

`dashboard/command_store.py` tạo row `PENDING`, gắn `idempotency_key` unique, đặt expiry và audit event. EA claim atomically một command thành `CLAIMED`; receipt sẽ đưa command tới terminal state.

### Command state

```text
PENDING → CLAIMED → EXECUTED
                  ├→ REJECTED
                  └→ FAILED
PENDING → EXPIRED
```

`EXECUTED`, `REJECTED`, `FAILED`, `EXPIRED` là terminal states. Retry cùng idempotency key không tạo một command khác.cktest/replay offline và ghi artifact trước khi cân nhắc demo.

### `DEMO` — chỉ sau phê duyệt độc lập

Ngay cả khi `QUANTAI_EXECUTION_MODE=DEMO`, command chỉ có thể được issue khi **toàn bộ** điều kiện sau đúng:

1. `QUANTAI_DEMO_ARMED=true`.
2. `QUANTAI_KILL_SWITCH=false`.
3. MT5 kết nối được.
4. Account login/server/trade mode khớp allowlist demo backend.
5. Symbol demo hợp lệ và có thể trade.
6. Profile risk cho symbol tồn tại.
7. Strategy không trả `NO_TRADE`.
8. RiskGate approve tất cả kiểm tra.
9. Operator token đúng.
10. EA có bridge token, `InpExecutionEnabled=true`, và kiểm tra lại account/symbol/magic/spread/stops/volume thành công.

### `LIVE`

**Không được hỗ trợ như một quy trình vận hành trong repository này.** Không bật `LIVE` chỉ bằng thay đổi biến môi trường. Một quyết định production riêng phải có: forward-demo evidence, OOS/walk-forward analysis, drawdown acceptance, reconciliation, review bảo mật và phê duyệt rõ ràng.

---

## Quy trình quyết định và thực thi

### 1. Strategy Core

`dashboard/strategy_core.py` là pure function, dùng EMA20/50/200, RSI và ATR để trả:

```text
BUY | SELL | NO_TRADE
```

Dữ liệu thiếu, quote invalid, volatility invalid, RSI invalid hoặc thiếu confluence đều tạo `NO_TRADE` kèm reason code.

### 2. RiskGate

`dashboard/risk_gate.py` nhận proposal, account snapshot, symbol spec, quote, số vị thế và policy. Chỉ `approved=True` mới có thể tiếp tục tạo command.

### 3. Command ledger

`dashboard/command_store.py` tạo row `PENDING`, gắn `idempotency_key` unique, đặt expiry và audit event. EA claim atomically một command thành `CLAIMED`; lease hết hạn sẽ cho phép re-claim. Receipt sẽ đưa command tới terminal state.

### 4. EA broker boundary

EA parse command đã claim và kiểm tra độc lập:

- Input mode, token và demo account identity.
- Symbol/magic exact match.
- Spread, position cap và broker trading mode.
- Volume min/max/step.
- SL/TP direction, stop level, freeze level.
- Broker result code sau `CTrade.Buy`/`CTrade.Sell`.

Sau đó EA gửi receipt `EXECUTED`, `FAILED` hoặc `REJECTED` về backend.

### Command state

```text
PENDING → CLAIMED → EXECUTED
                  ├→ REJECTED
                  └→ FAILED
PENDING → EXPIRED
```

`EXECUTED`, `REJECTED`, `FAILED`, `EXPIRED` là terminal states. Retry cùng idempotency key không tạo một command khác.

---

## RiskGate

RiskGate hiện kiểm tra tối thiểu:

- `execution_enabled` của policy.
- `NO_TRADE` proposal.
- Symbol match.
- Giá trị finite (`NaN`/infinity bị từ chối).
- Equity/free margin hợp lệ.
- Daily realized loss limit.
- Maximum open positions thuộc cùng symbol + magic.
- Bid/ask và spread limit.
- Hướng SL/TP chính xác cho BUY/SELL.
- Tick size/tick value, risk monetary và volume min/max/step.

Profile được khai báo tại `dashboard/risk_profiles.py`. Mỗi cặp/symbol phải có policy và spread cap riêng; không tái sử dụng thông số XAUUSD cho mọi Forex pair.

---

## API

Backend chạy local tại `http://127.0.0.1:8005`.

### Read-only/public dashboard endpoints

| Method | Route | Mục đích |
|---|---|---|
| `GET` | `/api/status` | Telemetry, indicators, performance, AI signal cùng `data_status`. |
| `GET` | `/api/market?symbol=XAUUSD&tf=M15` | OHLCV/candles từ MT5 khi có. |
| `GET` | `/api/positions` | Vị thế read-only. |
| `GET` | `/api/history` | Lịch sử deals read-only. |
| `GET` | `/api/control-center/status` | Trạng thái điều kiện vận hành đã được sanitize; không chứa secret/ticket. |
| `POST` | `/api/v1/decisions/evaluate` | Proposal + risk decision, luôn `ANALYSIS_ONLY`. |
| `POST` | `/api/ai_scan_now` | Scan analysis-only, không tạo command. |

### Protected EA bridge endpoints

Các endpoint này yêu cầu:

```http
Authorization: Bearer <QUANTAI_BRIDGE_TOKEN>
```

| Method | Route | Mục đích |
|---|---|---|
| `POST` | `/api/telemetry` | EA gửi telemetry. |
| `POST` | `/api/v1/bridge/commands/claim` | EA atomically claim command phù hợp. |
| `POST` | `/api/v1/bridge/commands/{command_id}/receipt` | EA ghi execution receipt. |
| `GET` | `/api/v1/commands/{command_id}` | Đọc command lifecycle cho bridge reconciliation. |

### Protected demo operator endpoint

```http
Authorization: Bearer <QUANTAI_OPERATOR_TOKEN>
```

| Method | Route | Mục đích |
|---|---|---|
| `POST` | `/api/v1/demo/scan` | Chỉ demo/operator; evaluate → RiskGate → issue command nếu mọi guard pass. |

### Legacy và browser order endpoints

- `/api/signal_command` trả inert `NONE` để tương thích trong lúc migration.
- `/api/signal_ack` trả `410`.
- `/api/order/buy`, `/api/order/sell`, `/api/order/close_all`, `/api/order/modify_tpsl` trả `503 EXECUTION_DISABLED`.

Không xây client browser mới dựa trên các route order legacy.

---

## EA MQL5

File EA: `QuantAI_XAUUSD.mq5`.

### Cài EA vào MetaTrader 5

1. Mở MetaEditor từ terminal MT5.
2. Mở file `QuantAI_XAUUSD.mq5` trong thư mục Experts tương ứng.
3. Compile và xử lý **toàn bộ** compiler errors trước khi attach EA.
4. Attach EA vào chart **XAUUSDm** trên đúng tài khoản demo allowlisted.
5. Trong MT5, thêm `https://autonomous-trading-engine.vercel.app` vào **Tools → Options → Expert Advisors → Allow WebRequest for listed URL**.
6. Giữ `InpExecutionEnabled=false` cho đến khi quy trình demo canary được phê duyệt.

### EA inputs quan trọng

| Input | Mặc định | Vai trò |
|---|---|---:|
| `InpApiUrl` | `https://autonomous-trading-engine.vercel.app/api/v1/` | Bridge API qua Vercel proxy → public IP. |
| `InpMagicNumber` | `888999` | Isolation magic number. |
| `InpSymbol` | `XAUUSDm` | Symbol allowlist. |
| `InpExecutionEnabled` | `false` | Interlock quan trọng nhất tại EA. |
| `InpBridgeToken` | rỗng | Token bridge bắt buộc. |
| `InpExecutorId` | `quantai-ea-local` | Danh tính executor/lease. |
| `InpExpectedLogin` / `Server` / `Company` | demo allowlist | Chỉ allow account demo đúng identity. |
| `InpMaxSpread` | `0.50` | Spread cap raw price XAUUSDm. |
| `InpMaxPositions` | `1` | Cap positions cùng symbol + magic. |
| `InpMaxDeviationPts` | `50` | Broker deviation cap. |

Backend and EA allowlist phải khớp nhau về login, server, symbol và magic.

---

## Backtest và KPI

### Backtest offline

`backtest.py` không import MT5, FastAPI, WebRequest hoặc LLM. Backtest dùng candles đã hoàn thành, theo quy ước:

- Signal tại bar close.
- Entry tại close đã cộng spread/slippage theo hướng.
- Exit tại close của bar kế tiếp.
- Spread, commission, slippage và strategy version được ghi vào result.
- `artifact_hash()` tạo SHA-256 deterministic cho kết quả fixed data/config.

Ví dụ dùng từ Python:

```python
from backtest import BacktestConfig, load_csv, run_backtest, artifact_hash

candles = load_csv("tests/fixtures/eurusd_m15_sample.csv")
result = run_backtest(
    candles,
    BacktestConfig(symbol="EURUSD", timeframe="M15", spread=0.0001),
)
print(result["status"])
print(artifact_hash(result))
```

Mẫu fixture nhỏ không đủ bars để tạo trade; dùng nó để kiểm thử ingest. Với replay thực, cần dataset có provenance, checksum, timezone rõ ràng và tối thiểu số bars strategy yêu cầu.

### KPI live

`dashboard/performance.py` tính KPI từ closed trades đã lọc magic number:

- Sample size
- Win rate
- Profit factor
- Best/worst trade
- Equity curve theo thứ tự đóng lệnh
- Peak-to-trough max drawdown
- Recovery factor

Dashboard chỉ hiển thị KPI theo `data_status`:

| Status | Ý nghĩa |
|---|---|
| `LIVE_VERIFIED` | Tính từ MT5 closed trades đã lọc. |
| `NO_CLOSED_TRADES` | Không có sample đủ điều kiện. |
| `UNAVAILABLE` | MT5/data path không khả dụng. |

`N/A` là trạng thái đúng cho dữ liệu không có; không thay bằng con số giả.

---

## Kiểm thử

### Python core/unit tests

```powershell
python -m unittest discover -s tests -v
```

Các regression test bao gồm tối thiểu:

- Strategy abstains khi thiếu indicators.
- RiskGate reject execution disabled/non-finite/sub-minimum volume.
- Idempotency và receipt retry-safe của command ledger.
- Telemetry unavailable không tạo giá/signal giả.
- Demo mode fail-closed.
- Control center sanitized, không lộ token/ticket.
- KPI drawdown.
- Backtest deterministic và artifact hash ổn định.

### Backend syntax

```powershell
python -m py_compile dashboard/server.py dashboard/command_store.py dashboard/risk_gate.py dashboard/strategy_core.py dashboard/performance.py backtest.py
```

### Frontend typecheck và production build

```powershell
npm --prefix web run lint
npm --prefix web run build
```

### EA

Compile trong MetaEditor. Không xem việc source text tồn tại là bằng chứng EA compile hoặc broker execution thành công.

---

## Vận hành demo có kiểm soát

Chỉ thực hiện sau khi có approval riêng cho demo test.

### Pre-flight

1. Chạy toàn bộ tests/backend/frontend build.
2. Compile EA trong MetaEditor không lỗi.
3. Đảm bảo account là demo và đúng login/server/company allowlist.
4. Xác nhận `QUANTAI_EXECUTION_MODE=DEMO`.
5. Đặt `QUANTAI_DEMO_ARMED=true` **chỉ trong cửa sổ test**.
6. Đặt `QUANTAI_KILL_SWITCH=false` **chỉ trong cửa sổ test**.
7. Đặt bridge/operator token khác nhau và cấu hình cùng bridge token trong EA.
8. Xác nhận `GET /api/control-center/status` trả readiness phù hợp, không chỉ dựa vào UI.
9. Xác nhận EA input `InpExecutionEnabled=true` chỉ sau các bước trên.

### Canary

- Bắt đầu với **một symbol, một EA, một position cap**.
- Dùng volume nhỏ nhất được policy/broker cho phép.
- Gọi operator demo scan một lần, không loop tự động.
- Theo dõi ledger: `PENDING → CLAIMED → terminal receipt`.
- Reconcile ticket/retcode/receipt trong MT5 journal và SQLite audit.
- Test rejection cases: kill switch, expired command, bad token, wrong account, bad stops và retry receipt.

### Dừng ngay

Bật ngay:

```dotenv
QUANTAI_KILL_SWITCH=true
QUANTAI_DEMO_ARMED=false
```

Sau đó restart backend nếu biến được load khi process khởi động, và đặt `InpExecutionEnabled=false` trong EA. Kill switch ngăn command mới; luôn lưu audit/ledger để điều tra thay vì xóa dữ liệu runtime ngay lập tức.

---

## 🌐 Định tuyến Vercel Cloud → Backend Cloudlocal (Unified Cloud Routing)

Kết nối Next.js Website trên Vercel với phần mềm MT5 local **không dùng ngrok/Cloudflare Tunnel** — chỉ dùng IP công khai + port-forward cổng 80 vào nginx Docker (cloudlocal):

### 1. Cách thức hoạt động
- `Cloudlocal/docker-compose.yml` dựng nginx (:80/8080 local, :8848 public) → FastAPI backend (8005), ai-engine (8006), python-bridge (8007), postgres, redis.
- Backend FastAPI (`dashboard/server.py`) chạy **native trên Windows host** (có package `MetaTrader5` → `HAS_MT5=true`); nginx proxy `host.docker.internal:8005` về host. `cloudlocal-fastapi` container bị stop để tránh xung đột port.
- Router của chủ tịch forward cổng `8848` về máy (port 80/443 bị modem VNPT chiếm cho admin portal, UPnP tắt nên forward thủ công trên router); Windows firewall mở cổng 8848.
- Vercel rewrite `/api/:path*` sang `${ATE_BACKEND_URL}/api/:path*` (không tạo vòng lặp vì `ATE_BACKEND_URL` trỏ về IP công khai, không trỏ về chính vercel.app).

### 2. Cấu hình biến môi trường
- **Cấu hình Local (`Cloudlocal/.env`)**: `PUBLIC_IP=<IP/DDNS công khai>`, `ATE_BACKEND_URL=http://<PUBLIC_IP>:8848` (cổng 8848 vì 80/443 bị modem VNPT chiếm làm admin portal).
- **Cấu hình trên Vercel Settings**:
  - `ATE_BACKEND_URL` = `http://<PUBLIC_IP>:8848` (KHÔNG kèm `/api/v1`, KHÔNG có khoảng trắng đầu).
  - `NEXT_PUBLIC_ATE_API_ORIGIN`, `NEXT_PUBLIC_QUANTAI_API_ORIGIN` = `https://autonomous-trading-engine.vercel.app`.
  - MT5 EA dùng trực tiếp `https://autonomous-trading-engine.vercel.app/api/v1/`.

---

## Bảo mật

- Backend chỉ bind localhost (`127.0.0.1`). Không expose port 8005 ra Internet.
- CORS giới hạn theo `QUANTAI_ALLOWED_ORIGINS`.
- Bridge token và operator token là hai secret khác nhau.
- Dùng HTTP local loopback; nếu tách process sang host khác, cần thiết kế lại transport/authentication trước, không port-forward tùy tiện.
- `.env`, database ledger, build artifacts và dependencies không được commit.
- Rotate token nếu có dấu hiệu lộ secret.
- Control center được thiết kế để sanitize secrets, idempotency key, receipt ID và tickets khỏi dashboard response.

---

## Tuyên bố rủi ro

Giao dịch tài chính có rủi ro cao và có thể mất toàn bộ vốn. Phần mềm này phục vụ mục tiêu kỹ thuật/nghiên cứu; người vận hành chịu trách nhiệm độc lập về cấu hình, tuân thủ quy định, quản trị rủi ro và việc sử dụng bất kỳ broker account nào.
