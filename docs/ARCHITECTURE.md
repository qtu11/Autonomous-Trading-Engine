# QuantAI - Đặc tả Kiến trúc Hệ Thống (Architecture Specification)

## Tổng Quan

QuantAI (GoldQuant AI / ATE - Autonomous Trading Engine) là hệ thống giao dịch tự động theo mô hình **kiến trúc lai (Hybrid Architecture)** dành cho MetaTrader 5 trên symbol XAUUSD (Vàng). Kiến trúc phân tách rõ ba phân hệ độc lập nhưng phối hợp đồng bộ: phân hệ thực thi (MQL5 EA), phân hệ phân tích & ra quyết định (FastAPI Backend), và phân hệ trực quan hóa (Next.js Dashboard).

## Kiến Trúc Tổng Thể

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                         NEXT.JS DASHBOARD                                    │
│                     (React 19 / TypeScript)                                   │
│                                                                               │
│   ┌───────────────────────┐  ┌──────────────────┐  ┌────────────────────┐   │
│   │ Chart SVG Realtime    │  │ Telemetry Live    │  │ Control Center     │   │
│   │ (Bloomberg Style)     │  │ Monitoring        │  │ Multi-Interlock UI │   │
│   └───────────────────────┘  └──────────────────┘  └────────────────────┘   │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ WebSocket (HTTP) / REST
┌──────────────────────────────────────▼──────────────────────────────────────┐
│                          FASTAPI BACKEND                                     │
│                        (Python 3.11 / AsyncIO)                               │
│                                                                               │
│  ┌───────────────────────┐  ┌──────────────────┐  ┌─────────────────────┐  │
│  │ MT5 Read Gateway       │  │ Pattern/Strategy │  │ Multi-AI Decision   │  │
│  │ (Tick/Candle/Account) │  │ Engine (72+)     │  │ Router (Failover)   │  │
│  └───────────────────────┘  └──────────────────┘  └─────────────────────┘  │
│                                                                               │
│                              ┌──────────────────────┐                        │
│                              │  RiskGate (Fail-   │                        │
│                              │  Closed 15 điểm)   │                        │
│                              └──────────┬──────────┘                        │
│                                         │ (Chỉ Proposal đã duyệt)           │
│                                         ▼                                    │
│                              ┌──────────────────────┐  ┌────────────────┐   │
│                              │  Command Store    │──►│ SQLite WAL DB   │   │
│                              │  Ledger           │   │ (quantai_commd) │   │
│                              └──────────────────────┘  └────────────────┘   │
└──────────────────────────────────────────────┬───────────────────────────────┘
                                               │ Authenticated Local REST Bridge
┌──────────────────────────────────────────────▼───────────────────────────────┐
│                       METATRADER 5 EXPERT ADVISOR                            │
│                       (QuantAI_XAUUSD.mq5 / MQL5)                            │
│                                                                               │
│  ┌───────────────────────┐  ┌──────────────────┐  ┌─────────────────────┐  │
│  │ Auth Lease & Claim   │──► Local Guard      │──► CTrade Execution     │  │
│  │ Protocol             │   Validation        │   Authority             │  │
│  └───────────────────────┘  └──────────────────┘  └─────────────────────┘  │
└──────────────────────────────────────────────┬───────────────────────────────┘
                                               │ Broker API / Terminal
┌──────────────────────────────────────────────▼───────────────────────────────┐
│                               BROKER TERMINAL                                  │
│                         (Exness / MetaTrader 5)                                │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Ranh Giới & Trách Nhiệm Của Từng Phân Hệ

### 1. Next.js Web Dashboard (`web/`)
- Render thông tin thời gian thực: ticker chạy trực tiếp, chart nến SVG, **AI Intelligence Matrix**, bảng vị thế mở, lịch sử giao dịch, lịch kinh tế, Copilot Chat.
- Cung cấp **Control Center** cho người vận hành: arming (DEMO/LIVE), Kill Switch, ghi đè Policy (risk policy), cấu hình tài khoản MT5, thông báo Telegram, xem Audit Log.
- **KHÔNG BAO GIỜ gọi lệnh broker trực tiếp** - chỉ đọc & điều khiển qua API của backend.

### 2. FastAPI Backend Server (`dashboard/`)
- Là **trung tâm xử lý**: log dữ liệu MT5 (tick, nến, account), tính toán offset (EMA20/50/200, RSI, ATR, MACD, Pivot...), chạy Pattern Engine (72+ mô hình), gọi **Multi-AI Decision Router**.
- **RiskGate** áp dụng nguyên tắc **Fail-Closed**: chặn mọi đề xuất không đạt điều kiện về rủi ro.
- Ghi **Command Ledger** idempotent vào SQLite (WAL).

### 3. Command Ledger Store (`dashboard/command_store.py`)
- SQLite WAL DB chứa vòng đời lệnh: `PENDING -> CLAIMED -> EXECUTED / REJECTED / FAILED / EXPIRED`.
- IDEMPOTENCY: dùng khóa hash duy nhất (`idempotency_key`) để nhóm ra lúc lệnh bị lặp (retry) gây lệnh trùng.

### 4. Risk Gate (`dashboard/risk_gate.py`)
- Đánh giá: free margin, equity draw, spread giới hạn theo profiled symbol, DE/TP đúng hướng, daily loss cap, position limit, volume quantization.

### 5. MQL5 EA Bridge (`QuantAI_XAUUSD.mq5`)
- Poll giao diện bridge FastAPI mỗi 1 giây, dùng `WebRequest` với `Bearer Token` xác thực.
- Xác minh tại chỗ (account login/server/symbol/spread/stop level) **trước khi** gọi `CTrade`.
- `CTrade` là đơn vị thực thi duy nhất lên broker, sau đó gửi receipt (kết quả) về backend.

---

## Nguyên Tắc Thiết Kế (Design Principles)

1. **Database-First + Quantitative**: Độ tin cậy và nhất quán toán học được ưu tiên tối đa; quyết định giao dịch sinh ra từ module toán học (không phải cảm tính AI).
2. **Fail-Closed**: Mọi nghi ngờ đều dừng lệnh. AI chỉ là lớp hỗ trợ, không thay thế như RiskGate.
3. **Single Source of Truth**: Swing Engine chia sẻ & canonical; markup chart được sinh từ backend - frontend chỉ render, tuyệt đối không tự sinh object.
4. **Không lệnh trùng**: idempotency key + receipt, khóa duy nhất mỗi lệnh.
5. **Tách trách nhiệm bảo mật**: Token bridge (EA) và operator token (dashboard) được phân quyền riêng biệt.

---

## Thư Mục Mã Nguồn Tương Ứng

| Thành phần | Module/File |
|------------|-------------|
| Dashboard | `dashboard/server.py`, `dashboard/strategy_core.py`, `dashboard/detectors.py`, `dashboard/advanced_detectors.py`, `dashboard/signal_engines.py`, `dashboard/risk_gate.py`, `dashboard/risk_profiles.py`, `dashboard/command_store.py`, `dashboard/ws_hub.py`, `dashboard/performance.py`, `dashboard/logging_config.py` |
| Frontend | `web/app/page.tsx`, `web/app/components/*`, `web/lib/api.ts` |
| EA | `MQL5/Experts/tradeAI/QuantAI_XAUUSD.mq5` |
| Đặc tả Market Analysis | `MARKET_ANALYSIS_SPEC.md` |
| Tài liệu | `docs/ATECOMMENTATION.md`, `docs/DATA_FLOW.md`, `docs/DATABASE_SCHEMA.md` |

---

*Tài liệu thuộc dự án QuantAI - nhà phát triển Nguyễn Quang Tú (QTusdev) | MIT License.*