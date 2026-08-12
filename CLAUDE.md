C:\Users\KIMPC\AppData\Roaming\MetaQuotes\Terminal\C3DCCD4DFDD81FF8F00FFC310CAC0FD8\MQL5\Experts\tradeAI
# ATE - Autonomous Trading Engine (ATE)

**Hệ thống Giao Dịch Tự Động cho XAUUSD (Vàng) | Phiên bản 2.4**

---

## Tổng Quan

ATE là nền tảng giao dịch tự động hoàn chỉnh kết hợp phân tích định lượng thời gian thực, trí tuệ nhân tạo đa mô hình và kiểm soát rủi ro fail-closed, vận hành trên MetaTrader 5 với giao diện Bloomberg Terminal:

- **Dữ liệu thời gian thực MT5** (XAUUSD, khung M1 -> D1)
- **Multi-AI Provider Engine**: Mặc định chạy miễn phí trên OpenCode Zen Free Pool (không cần API Key), tự động xoay vòng và failover sang các provider thương mại (Gemini, OpenAI, DeepSeek, Claude...) khi cần
- **5 Phương Pháp Giao Dịch**: Price Action, SMC, ICT, Sniper, Ultra Confluence
- **72+ Mẫu hình thị trường** được phát hiện tự động (FVG, Order Block, BOS, CHoCH, Tick, Breaker...)
- **RiskGate 15 điểm** - chặn lệnh theo nguyên tắc Fail-Closed trước khi đến MT5
- **Web Dashboard toàn diện** (Next.js + FastAPI + WebSocket)

## Kiến Trúc Tổng Quan

```
MT5 REAL DATA (XAUUSDm)
        |
        v
MARKET_DATA_ENGINE
        |
        v
CANDLE_NORMALIZER
        |
        v
SHARED_SWING_ENGINE  <-- NGUỒN DUY NHẤT (ONE CANONICAL SOURCE)
        |
        v
MARKET_STRUCTURE_ENGINE
        |
        +---------------------------------------------------+
        |               PATTERN DETECTION ENGINES           |
        |    Price Action | SMB | ICT | Sniper | Ultra      |
        +---------------------------------------------------+
        |
        v
MARKUP_OBJECTS (JSON)
        |
        +--------> FRONTEND CHART (SVG + lightweight-charts)
        |
        v
AI CONTEXT BUILDER
        |
        v
AI_ENGINE (Multi-AI Failover Router)
        |
        v
RISK_ENGINE (Fail-Closed RiskGate)
        |
        v
MT5 EXECUTION (qua MQL5 EA - đơn vị thực thi duy nhất)
```

## 5 Phương Pháp Giao Dịch

### 1. PRICE ACTION (25 khái niệm)
Xu hướng, Swing HH/HL/LH/LL, Hỗ trợ/Kháng cự, Trendline, Kênh giá, Range, Breakout, Pullback, Retest, Fake Breakout, 14 mẫu hình nến (Pin Bar, Engulfing, Doji...).

### 2. SMC - Smart Money Concepts (26 khái niệm)
Market Structure (BOS, CHoCH, MSS), Order Block, FVG/IFVG, Liquidity Sweep, Equal Highs/Lows, Breaker/Mitigation/Rejection Block, Premium/Discount, Supply/Demand.

### 3. ICT - Inner Circle Trader (26 khái niệm)
OTE (Fibonacci 62-79%), PD Array, Kill Zones, PDH/PDL, Weekly/Monthly High/Low, Turtle Soup, Judas Swing, SMT Divergence, AMD/PO3, Silver Bullet, Unicorn Model.

### 4. SNIPER (chứng khoán chỉ báo)
EMA 9/21 Ribbon, VWAP, ADX(14), RSI(14), MACD - hệ thống chấm điểm 7 yếu tố, vào lệnh khi giá retest ribbon/VWAP với xác nhận động lượng.

### 5. ULTRA CONFLUENCE (Matrix 5 lớp)
```
Layer 1: Market Structure (BOS, CHoCH, Swing)
Layer 2: Supply/Demand (OB, FVG, Liquidity)
Layer 3: Dynamic (EMA, VWAP, Pivot)
Layer 4: Momentum (RSI, MACD, ADX, Volume)
Layer 5: Time/News (Session, Killzone, News impact)
```
Trọng số: Structure 25% + Zone 25% + Indicator 20% + Momentum 15% + Time 15%. Setup >= 85% là QUALIFIED, 70-84% là CONSIDER.

## Cấu Trúc Thư Mục

```
tradeAI/
+-- README.md                       # Giới thiệu
+-- LICENSE                         # Giấy phép MIT
+-- MARKET_ANALYSIS_SPEC.md         # Đặc tả Market Analysis Engine
+-- dashboard/                      # Python FastAPI Backend
|   +-- server.py                   # FastAPI + AI decision loop
|   +-- detectors.py                # Pattern lõi (FVG, OB, BOS, Swing)
|   +-- advanced_detectors.py       # Pattern nâng cao (ICT, PA)
|   +-- chart_markup.py             # Markup builder cho chart
|   +-- signal_engines.py           # Sinh tín hiệu 5 phương pháp
|   +-- strategy_core.py            # Logic giao dịch lõi
|   +-- risk_gate.py                # Lớp lọc rủi ro 15 điểm (fail-closed)
|   +-- risk_profiles.py            # Hồ sơ rủi ro theo symbol
|   +-- command_store.py            # Sổ cái lệnh - SQLite WAL (idempotent)
|   +-- performance.py              # KPI & Equity curve
|   +-- ws_hub.py                   # WebSocket hub (~1s)
|   +-- logging_config.py           # Logger JSON có cấu trúc
|   +-- tests/test_market_analysis.py
+-- MQL5/                          # MT5 Expert Advisor
|   +-- Experts/tradeAI/ATE_XAUUSD.mq5
+-- web/                           # Next.js Frontend
    +-- app/page.tsx                # Dashboard chính
    +-- app/components/TradingChart.tsx   # lightweight-charts
    +-- app/components/CandleChart.tsx    # SVG chart
    +-- app/components/ControlCenter.tsx  # Điều khiển trang
    +-- lib/api.ts                  # API client
```

## Khởi Động Nhanh

### Backend
```bash
cd dashboard
pip install -r requirements.txt
python server.py
```

### Frontend
```bash
cd web
npm install
npm run dev
```

### MT5 EA
1. Copy `MQL5/Experts/tradeAI/ATE_XAUUSD.mq5` vào thư mục experts của MT5.
2. Biên dịch và attach vào chart XAUUSD.
3. Cấu hình tham số trong EA settings (symbol, magic, token bridge).

Xem hướng dẫn chi tiết tại [`docs/OPERATION_GUIDE.md`](docs/OPERATION_GUIDE.md).

## API Endpoints Chính

| Endpoint | Method | Mô tả |
|----------|--------|-------|
| `/api/status` | GET | Trạng thái hệ thống tổng hợp |
| `/api/market` | GET | Dữ liệu nến + chỉ báo + markup |
| `/api/control-center/status` | GET | Trạng thái vận hành |
| `/api/control-center/mode` | POST | Đổi mode (DEMO/LIVE/DISABLED) |
| `/api/control-center/kill-switch` | POST | Công tắc khẩn |
| `/api/copilot/chat` | POST | Trò chuyện AI Copilot |
| `/api/news/analyze` | POST | Phân tích tin tức kinh tế |
| `/api/v1/bridge/commands/claim` | POST | EA nhận lệnh (Bearer Token) |
| `/api/v1/telemetry` | POST | EA gửi telemetry mỗi 1s |
| `/ws/stream` | WS | Broadcast telemetry thời gian thực |

Đặc tả đầy đủ tại [`docs/API_SPEC.md`](docs/API_SPEC.md).

## Kiểm Thử

```bash
cd dashboard
python -m pytest tests/test_market_analysis.py -v
```

## Tài Liệu

Toàn bộ tài liệu dự án nằm trong [`docs/`](docs/README.md):
- [Mục lục tài liệu](docs/README.md)
- [Tính năng](docs/FEATURES.md)
- [Kiến trúc](docs/ARCHITECTURE.md)
- [AI Pipeline & Multi-AI Engine](docs/AI_PIPELINE.md)
- [5 Phương pháp giao dịch](docs/TRADING_METHODS.md)
- [Giao thức MT5](docs/MT5_PROTOCOL.md)
- [Cơ sở dữ liệu](docs/DATABASE_SCHEMA.md)
- [Rủi ro & Mối đe dọa](docs/RISK_ANALYSIS.md)
- [Vận hành](docs/OPERATION_GUIDE.md)

## Bản Quyền & Giấy Phép

- Copyright (c) 2024-2026 Nguyễn Quang Tú (QTusdev) - https://github.com/qtu11
- Released under the **MIT License**: [LICENSE](LICENSE)
- Chi tiết: [docs/COPYRIGHT.md](docs/COPYRIGHT.md)

**Cảnh báo rủi ro**: Giao dịch tiền mã hóa/ngoại hối tiềm ẩn rủi ro tổn thất vốn lớn. Hệ thống chỉ nên vận hành ở chế độ DEMO cho đến khi được kiểm chứng kỹ lưỡng.