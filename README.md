# Autonomous Trading Engine (ATE) - By QTusdev (Nguyễn Quang Tú)

> **Tác giả / Lead Developer**: Nguyễn Quang Tú (QTusdev)  
> **GitHub**: [https://github.com/qtu11](https://github.com/qtu11)  
> **Trạng thái an toàn mặc định: `DISABLED`.** Đây là hệ thống nghiên cứu định lượng, quan sát thị trường XAUUSD, đánh giá chiến lược và điều phối lệnh **demo có kiểm soát** cho MetaTrader 5.

Autonomous Trading Engine (ATE) gồm dashboard Next.js, backend FastAPI, chiến lược deterministic, RiskGate fail-closed, SQLite command ledger và MQL5 EA bridge. Thiết kế tập trung vào: dữ liệu có nguồn gốc rõ ràng, phân tách quyết định–rủi ro–thực thi, idempotency và khả năng audit.

---

## Mục lục

- [Phạm vi và nguyên tắc an toàn](#phạm-vi-và-nguyên-tắc-an-toàn)
- [Kiến trúc](#kiến-trúc)
- [Cấu trúc dự án](#cấu-trúc-dự-án)
- [Yêu cầu môi trường](#yêu-cầu-môi-trường)
- [Cài đặt và khởi động](#cài-đặt-và-khởi-động)
- [Cấu hình](#cấu-hình)
- [Chế độ vận hành](#chế-độ-vận-hành)
- [Quy trình quyết định và thực thi](#quy-trình-quyết-định-và-thực-thi)
- [RiskGate](#riskgate)
- [API](#api)
- [EA MQL5](#ea-mql5)
- [Backtest và KPI](#backtest-và-kpi)
- [Kiểm thử](#kiểm-thử)
- [Vận hành demo có kiểm soát](#vận-hành-demo-có-kiểm-soát)
- [Bảo mật](#bảo-mật)
- [Khắc phục sự cố](#khắc-phục-sự-cố)
- [Giới hạn hiện tại](#giới-hạn-hiện-tại)

---

## Phạm vi và nguyên tắc an toàn

### Điều hệ thống làm

- Hiển thị telemetry, candles, vị thế và lịch sử từ MT5 khi dữ liệu có sẵn.
- Tạo proposal chiến lược `BUY`, `SELL` hoặc `NO_TRADE`.
- Đánh giá proposal qua RiskGate trước khi bất kỳ command nào được tạo.
- Lưu lifecycle command/receipt trong SQLite WAL để chống lệnh trùng.
- Cho phép một luồng **demo-only, operator-only** tạo command sau nhiều điều kiện xác nhận.
- Để EA MQL5 là thành phần duy nhất có quyền gọi `CTrade`.

### Tính năng realtime & vận hành (cập nhật mới)

- **WebSocket realtime** tại `ws://127.0.0.1:8005/ws/stream`: dashboard nhận telemetry ~1s qua socket (thay polling HTTP), tự reconnect với backoff; HTTP vẫn là bootstrap + fallback.
- **Structured logging** JSON-per-line tại `logs/quantai_YYYYMMDD.log`: ghi đầy đủ sự kiện `APP_STARTED, MT5_CONNECTED/RECONNECT, WS_CONNECTED, AI_REQUEST/RESPONSE, SIGNAL_GENERATED, RISK_APPROVED/REJECTED, ORDER_SENT/FILLED/FAILED, SL_MODIFIED, TP_MODIFIED, POSITION_CLOSED, TRADE_LATENCY, EXCEPTION`. Đọc qua `GET /api/logs` (operator token).
- **Economic Calendar thật** từ MT5 built-in (`CalendarValueHistory`): EA đẩy lên `POST /api/v1/bridge/calendar`, backend phục vụ từ cache — không còn dữ liệu hard-code. Khi chưa có push, trạng thái là `CALENDAR_UNAVAILABLE` (không bịa).
- **Full trade actions**: ngoài `BUY/SELL/CLOSE_ALL`, hỗ trợ `MODIFY_SLTP` (sửa SL/TP), `CLOSE_POSITION` (đóng lệnh lẻ theo ticket), `CANCEL_PENDING` (hủy pending order) — tất cả qua command ledger + EA.
- **EA auto-reconnect**: watchdog phát hiện mất kết nối terminal, backoff tự động, heartbeat trong telemetry để dashboard hiển thị trạng thái EA online/stale.
- **AI Auto-Loop** (mặc định OFF): vòng lặp `AI → RiskGate → Execution` tự động mỗi `QUANTAI_AI_LOOP_SECONDS` (mặc định 120s), chỉ chạy khi readiness READY; bật/tắt từ Control Center.
- **LIVE mode safety path**: LIVE bị khóa nhiều lớp độc lập (`QUANTAI_LIVE_ARMED=true` tường minh + `QUANTAI_ENABLE_TRADING=true` + kill-switch OFF + account `trade_mode=REAL`). Một biến `=ENABLE` lỏng lẻo **không** arm được LIVE.

### Điều hệ thống không làm

- Không tự động bật giao dịch khi cài đặt mới.
- Không cho browser/dashboard gọi broker trực tiếp.
- Không để Python backend gọi `mt5.order_send()`.
- Không trả ticket, P/L, KPI hoặc kết quả “thành công” giả khi MT5/API không khả dụng.
- Không xem AI/copilot là execution authority.
- Không cam kết xác suất thắng hoặc lợi nhuận.

### Nguyên tắc fail-closed

Khi token thiếu, MT5 mất kết nối, market data stale/không hợp lệ, RiskGate từ chối, account sai identity, kill switch bật, command hết hạn hoặc EA validation thất bại, hệ thống **không mở lệnh**.

---

## Kiến trúc

```text
┌──────────────────────────────┐
│ Next.js dashboard (web/)     │
│ - Read-only browser actions  │
│ - Truthful data states       │
└──────────────┬───────────────┘
               │ HTTP localhost
┌──────────────▼────────────────────────────────────────────────────┐
│ FastAPI backend (dashboard/server.py)                              │
│                                                                    │
│  MT5 read gateway → Strategy Core → RiskGate → CommandStore        │
│                        │              │             │              │
│                        │              │             └─ SQLite WAL  │
│                        │              └─ reject / approval reasons │
│                        └─ BUY | SELL | NO_TRADE                    │
└──────────────┬────────────────────────────────────────────────────┘
               │ authenticated local bridge API
┌──────────────▼────────────────────────────────────────────────────┐
│ QuantAI_XAUUSD.mq5                                                 │
│ - Claim one leased command                                         │
│ - Revalidate broker/account/symbol/volume/stops                    │
│ - Execute only after all local guards pass                         │
│ - Post an idempotent receipt                                       │
└───────────────────────────────────────────────────────────────────┘
```

> Lưu ý: ký tự `n` sau đường khung backend trong sơ đồ trên không mang ý nghĩa cấu hình; sơ đồ minh hoạ dòng dữ liệu logic.

### Authority boundaries

| Thành phần | Quyền hạn | Không được phép |
|---|---|---|
| Browser dashboard | Hiển thị, refresh, copilot analysis | Không tạo broker order trực tiếp |
| FastAPI | Đọc MT5, tạo proposal, đánh giá risk, lưu command | Không gọi `mt5.order_send()` |
| RiskGate | Duy nhất approve/reject proposal thành command intent | Không giao dịch trực tiếp |
| CommandStore | Lưu/audit/lease command và receipt | Không ra quyết định trading |
| MQL5 EA | Broker execution authority | Không tin command nếu validation local thất bại |

---

## Cấu trúc dự án

```text
tradeAI/
├── QuantAI_XAUUSD.mq5       # EA MQL5: authenticated command bridge
├── dashboard/
│   ├── server.py            # FastAPI, MT5 read path, protected bridge routes
│   ├── command_store.py     # SQLite WAL idempotent command ledger
│   ├── strategy_core.py     # Pure deterministic BUY/SELL/NO_TRADE proposals
│   ├── risk_gate.py         # Fail-closed policy evaluation & position sizing
│   ├── risk_profiles.py     # Profile risk theo từng symbol/cặp
│   └── performance.py       # KPI từ closed trades đã lọc
├── backtest.py              # Offline deterministic bar-close backtest
├── tests/
│   ├── test_quantai_core.py # Unit/regression tests
│   └── fixtures/            # Dữ liệu test CSV
├── web/
│   ├── app/page.tsx         # Dashboard
│   ├── lib/api.ts           # Typed API contracts
│   └── package.json         # Next.js scripts/dependencies
├── .env.example             # Mẫu biến môi trường, không chứa secret
├── .gitignore
├── start.bat                # Tiện ích chạy backend + dashboard local
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
2. Kéo `QuantAI_XAUUSD` từ Navigator (Experts) vào chart.
3. Trong tab **Common**: bật **Allow Algo Trading**.
4. Trong **Inputs**: điền `InpApiUrl=http://127.0.0.1:8005`, `InpBridgeToken=<QUANTAI_BRIDGE_TOKEN trong .env>`, giữ `InpExecutionEnabled=false` cho tới khi sẵn sàng arm demo.
5. Vào **Tools → Options → Expert Advisors**: thêm `http://127.0.0.1:8005` vào danh sách **Allow WebRequest for listed URL**.

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
5. Trong MT5, thêm `http://127.0.0.1:8005` vào **Tools → Options → Expert Advisors → Allow WebRequest for listed URL**.
6. Giữ `InpExecutionEnabled=false` cho đến khi quy trình demo canary được phê duyệt.

### EA inputs quan trọng

| Input | Mặc định | Vai trò |
|---|---:|---|
| `InpApiUrl` | localhost:8005 | Bridge API local. |
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

## Bảo mật

- Backend chỉ bind localhost (`127.0.0.1`). Không expose port 8005 ra Internet.
- CORS giới hạn theo `QUANTAI_ALLOWED_ORIGINS`.
- Bridge token và operator token là hai secret khác nhau.
- Dùng HTTP local loopback; nếu tách process sang host khác, cần thiết kế lại transport/authentication trước, không port-forward tùy tiện.
- `.env`, database ledger, build artifacts và dependencies không được commit.
- Rotate token nếu có dấu hiệu lộ secret.
- Control center được thiết kế để sanitize secrets, idempotency key, receipt ID và tickets khỏi dashboard response.

---

## Khắc phục sự cố

### Dashboard hiển thị `UNAVAILABLE` / `N/A`

- Kiểm tra backend có chạy trên port 8005.
- Kiểm tra `NEXT_PUBLIC_QUANTAI_API_ORIGIN`.
- Kiểm tra MT5 terminal mở, login hợp lệ và `MetaTrader5` package cài đúng environment.
- Đây là behavior an toàn: UI không được tự điền dữ liệu giả.

### EA không gửi telemetry hoặc claim command

- Kiểm tra MT5 WebRequest allowlist có `http://127.0.0.1:8005`.
- Kiểm tra backend và EA có cùng bridge token.
- Xem Experts/Journal trong MT5.
- Khi token rỗng, EA chặn telemetry/execution polling theo thiết kế.

### `/api/v1/demo/scan` trả `REJECT_*`

Dùng `/api/control-center/status` để xem readiness reason. Các nguyên nhân phổ biến:

- `REJECT_EXECUTION_MODE`: mode không phải `DEMO`.
- `REJECT_DEMO_NOT_ARMED`: demo arm chưa bật.
- `REJECT_KILL_SWITCH`: kill switch đang bật.
- `REJECT_MT5_UNAVAILABLE`: không đọc được MT5.
- `REJECT_ACCOUNT_IDENTITY` / `REJECT_ACCOUNT_NOT_DEMO`: account không khớp allowlist demo.
- `REJECT_SYMBOL_UNAVAILABLE`: symbol không visible/tradable.
- Reason từ RiskGate: spread, margin, stops, daily loss, position cap hoặc volume.

### Build frontend thất bại

```powershell
npm --prefix web install
npm --prefix web run lint
npm --prefix web run build
```

### Ledger bị khóa hoặc cần kiểm tra

SQLite chạy WAL. Không xóa `quantai_commands.sqlite3` trong lúc backend đang chạy. Dừng process trước khi sao lưu/di chuyển database; ưu tiên sao lưu để phục vụ audit.

---

## Giới hạn hiện tại

- Demo path chỉ được thiết kế cho một symbol demo allowlisted tại một thời điểm.
- Strategy hiện tại là deterministic technical confluence đơn giản, không phải một model dự báo đã được chứng minh.
- `win_prob` cũ không phải xác suất thắng được hiệu chuẩn; dashboard không còn trình bày nó như KPI/bảo đảm.
- Backtest bar-close đơn giản không thay thế broker-grade fill model, tick replay, swap, session/calendar handling hay validation out-of-sample.
- Data/provider errors luôn phải được xem là `NO_TRADE` hoặc `UNAVAILABLE`.
- Chưa có deployment remote/multi-user/production workflow; mặc định là local development và demo canary.

---

## Checklist trước mọi thay đổi liên quan execution

- [ ] Có lý do nghiệp vụ/approval cụ thể cho mode mới.
- [ ] Test Python và frontend build pass.
- [ ] EA compile pass trong MetaEditor.
- [ ] Không thay đổi mặc định fail-closed vô tình.
- [ ] Account/symbol/magic allowlist được đối chiếu hai bên backend và EA.
- [ ] Token không bị log, commit hoặc lộ ở frontend.
- [ ] Risk rejection và success receipt đều được kiểm chứng.
- [ ] Có cách bật kill switch ngay lập tức.
- [ ] Có audit trail intent → risk decision → command → receipt.

---

## Tuyên bố rủi ro

Giao dịch tài chính có rủi ro cao và có thể mất toàn bộ vốn. Phần mềm này phục vụ mục tiêu kỹ thuật/nghiên cứu; người vận hành chịu trách nhiệm độc lập về cấu hình, tuân thủ quy định, quản trị rủi ro và việc sử dụng bất kỳ broker account nào.
