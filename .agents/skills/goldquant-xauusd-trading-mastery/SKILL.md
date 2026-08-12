# Cloudlocal Trading Engine - Local Cloud for MT5-Website Bridge

Transform your Windows PC into a local cloud server that bridges MetaTrader 5 with your Vercel-deployed website. No ngrok, no third-party tunnels - direct public IP access.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        INTERNET / PUBLIC IP                         │
│                              (YOUR_PUBLIC_IP)                       │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      WINDOWS HOST (Your PC)                         │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    DOCKER ENGINE                            │   │
│  │  ┌─────────────────────────────────────────────────────┐    │   │
│  │  │              NGINX REVERSE PROXY (Port 80)          │    │   │
│  │  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │    │   │
│  │  │  │ Next.js │ │ FastAPI │ │AI Engine│ │MT5 Bridge│   │    │   │
│  │  │  │ (3000)  │ │ (8848)  │ │ (8006)  │ │ (8007)  │   │    │   │
│  │  │  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘   │    │   │
│  │  │       │         │         │         │          │    │   │
│  │  │       ▼         ▼         ▼         ▼          │    │   │
│  │  │  ┌─────────────────────────────────────────────┐  │    │   │
│  │  │  │         SHARED VOLUMES                      │  │    │   │
│  │  │  │  Logs | Models | History | Config | DB      │  │    │   │
│  │  │  └─────────────────────────────────────────────┘  │    │   │
│  │  └─────────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│                              ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              METATRADER 5 (Windows Native)                  │   │
│  │  - Terminal64.exe                                           │   │
│  │  - MT5 Python Bridge (via shared volume)                    │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

## Signal Flow

```
Vercel Website (Cloud)                    Your PC (Local Cloud)
─────────────────────                     ───────────────────
     │                                         │
     │  POST /api/v1/signal (BUY/SELL)        │
     ├────────────────────────────────────────►│
     │                                         │  Nginx (Port 80)
     │                                         │       │
     │                                         ▼       ▼
     │                              FastAPI (8848) ──► Python Bridge (8007)
     │                                         │              │
     │                                         │         MT5 DLL
     │                                         │              │
     │                                         ◄──────────────┘
     │  Response: {success, ticket, price}     │
     ◄─────────────────────────────────────────┤
     │                                         │
     │  GET /api/v1/market/tick (Polling/WS)   │
     ├────────────────────────────────────────►│
     │                                         │
     │  Response: {bid, ask, spread, time}     │
     ◄─────────────────────────────────────────┤
```

## Quick Start

### 1. Prerequisites
- Windows 10/11 Pro/Enterprise
- Docker Desktop installed and running
- MetaTrader 5 installed at `C:\Program Files\MetaTrader 5\terminal64.exe`
- Public IP address (static preferred, or use DDNS)

### 2. Configure Environment
```powershell
cd Cloudlocal
copy .env.template .env
notepad .env
```

**Required values in `.env`:**
```env
PUBLIC_IP=YOUR_ACTUAL_PUBLIC_IP      # Critical! Get from https://api.ipify.org
MT5_LOGIN=12345678
MT5_PASSWORD=your_mt5_password
MT5_SERVER=YourBroker-Demo
QUANTAI_BRIDGE_TOKEN=openssl_rand_hex_32
ADMIN_PASSWORD=secure_admin_password
QUANTAI_AI_MODEL=deepseek-v4-flash-free   # Model AI mặc định (OpenCode Zen Free, không cần key)
OPENCODE_BASE_URL=https://opencode.ai/zen/v1/chat/completions   # Gateway OpenCode Zen Free
# GATEWAY_URL=            # (tùy chọn) Gateway khách hàng riêng — ưu tiên cao nhất
# GATEWAY_KEY=            # (tùy chọn) Key gateway riêng
```

**AI Provider Priority (từ cao → thấp):** `GATEWAY_URL+KEY` → Key/Model khách hàng (`*_API_KEY` + `custom_model_id`) → `OpenCode Zen Free Pool` (mặc định) → default keys khác. Hệ thống chạy hoàn toàn miễn phí trên OpenCode khi chưa cấu hình key nào.

### 3. Install as Windows Service (Auto-start on boot)
```powershell
# Run PowerShell as Administrator
.\scripts\install-windows-service.ps1
```

This creates a Task Scheduler job that runs on system startup (SYSTEM account, highest privileges).

### 4. Configure Firewall & Port Forwarding
```powershell
# Run PowerShell as Administrator
.\scripts\setup-firewall-portforward.ps1
```

Or manually forward these ports on your router:
| External Port | Internal IP | Internal Port | Protocol |
|---------------|-------------|---------------|----------|
| 80            | YOUR_LOCAL_IP | 80          | TCP      |
| 443           | YOUR_LOCAL_IP | 443         | TCP      |
| 8848          | YOUR_LOCAL_IP | 8848        | TCP      |
| 8006          | YOUR_LOCAL_IP | 8006        | TCP      |
| 8007          | YOUR_LOCAL_IP | 8007        | TCP      |
| 8080          | YOUR_LOCAL_IP | 8080        | TCP      |

### 5. Start Manually (First Time)
```cmd
.\scripts\start-cloudlocal.bat
```

### 6. Verify Health
```cmd
.\scripts\health-check.bat
```

### 7. Monitor Real-time
```powershell
.\scripts\monitor-cloudlocal.ps1
```

## Vercel Configuration

In your Vercel project settings, add this environment variable:

```
ATE_BACKEND_URL=http://YOUR_PUBLIC_IP:80
```

**NOT** `https://autonomous-trading-engine.vercel.app` - that would create an infinite loop!

## API Endpoints

### Website → MT5 (via Vercel → Your Public IP)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/order` | Execute trade (BUY/SELL/CLOSE) |
| GET | `/api/v1/market/tick` | Get current bid/ask |
| GET | `/api/v1/account` | Get account info |
| GET | `/api/v1/positions` | Get open positions |
| WS | `/ws` | Real-time market data |

### Bridge Authentication
All mutating endpoints require header:
```
Authorization: Bearer YOUR_QUANTAI_BRIDGE_TOKEN
```

## Container Ports

| Service | Internal Port | External (Nginx) | Direct Access |
|---------|---------------|------------------|---------------|
| Nginx | 80 | 80 | http://PUBLIC_IP:80 |
| Next.js | 3000 | 80/ | http://PUBLIC_IP:3000 |
| FastAPI | 8848 | 80/api/ | http://PUBLIC_IP:8848 |
| AI Engine | 8006 | 80/ai/ | http://PUBLIC_IP:8006 |
| MT5 Bridge | 8007 | 80/bridge/ | http://PUBLIC_IP:8007 |
| PostgreSQL | 5432 | - | localhost only |
| Redis | 6379 | - | localhost only |

## Management Commands

```cmd
# Start all services
.\scripts\start-cloudlocal.bat

# Stop all services
.\scripts\stop-cloudlocal.bat

# Health check
.\scripts\health-check.bat

# Real-time monitor
powershell -ExecutionPolicy Bypass -File .\scripts\monitor-cloudlocal.ps1

# View logs
docker-compose logs -f fastapi
docker-compose logs -f python-bridge

# Restart single service
docker-compose restart fastapi

# Update and rebuild
docker-compose pull
docker-compose build --no-cache
docker-compose up -d
```

## Troubleshooting

### MT5 Not Connecting
1. Verify MT5 is running and logged in
2. Check `MT5_PATH` in `.env` points to `terminal64.exe`
3. Check bridge logs: `docker-compose logs python-bridge`
4. Ensure MT5 allows DLL imports: Tools → Options → Expert Advisors → "Allow WebRequest for listed URL"

### Website Can't Reach API
1. Verify `PUBLIC_IP` in `.env` matches your actual public IP
2. Check port forwarding on router (port 80 → local IP:80)
3. Test locally: `curl http://localhost/health`
4. Test externally: `curl http://YOUR_PUBLIC_IP/health`

### Docker Containers Keep Restarting
```cmd
docker-compose logs fastapi
# Check for Python import errors, missing dependencies
```

### Windows Firewall Blocking
```powershell
# Run as Admin
.\scripts\setup-firewall-portforward.ps1 -ShowOnly
# Verify rules exist for ports 80, 8848, 8006, 8007, 8080
```

## Security Notes

- **Never expose PostgreSQL/Redis ports (5432, 6379) to internet**
- Use strong `QUANTAI_BRIDGE_TOKEN` (32+ hex chars)
- Use strong `ADMIN_PASSWORD`
- Consider IP whitelisting on router for port 80
- Enable Windows Firewall logging for audit

## Auto-Start Verification

After reboot, verify:
```powershell
Get-ScheduledTask -TaskName "Cloudlocal-Trading-Engine"
docker-compose ps
```

## Logs Location

```
Cloudlocal/
├── volumes/
│   ├── logs/
│   │   ├── nginx/
│   │   ├── fastapi/
│   │   ├── python-bridge/
│   │   ├── ai-engine/
│   │   └── nextjs/
│   ├── models/
│   ├── history/
│   └── config/
```

## License

Internal use only - GoldQuant AI Trading System

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


# 🌐 Environment Configuration - FIXED

## Vấn đề đã fix
MT5 EA gọi đến `https://autonomous-trading-engine.vercel.app/api/v1/*`
nhưng Vercel chỉ có frontend, không có backend.

## Giải pháp
Vercel rewrite tất cả `/api/v1/*` requests về Home Server.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DEPLOYMENT FIXED                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   ┌─────────┐                                                      │
│   │   MT5  │──────┐                                                 │
│   │    EA   │      │                                                 │
│   └─────────┘      │                                                 │
│                     ▼                                                 │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │              VERCEL (Frontend + Rewrites)                   │   │
│   │                                                                 │   │
│   │  /api/v1/* ────────────────────────────────────────────────┐ │   │
│   │          │                                                  │ │   │
│   │          ▼                                                  │ │   │
│   │  rewrite to: http://192.168.1.12:8848/api/v1/*           │ │   │
│   │                                                                 │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                                    │                                 │
│                                    ▼                                 │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │              HOME SERVER (Backend)                            │   │
│   │                                                                 │   │
│   │  192.168.1.12:8848                                           │   │
│   │  - FastAPI (Dashboard)                                       │   │
│   │  - MT5 Terminal                                               │   │
│   │  - SQLite Database                                            │   │
│   │                                                                 │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## URLs

| Component | URL |
|------------|-----|
| **Website** | `https://autonomous-trading-engine.vercel.app/` |
| **MT5 API** | Vercel rewrite → `http://192.168.1.12:8848/api/v1/*` |
| **Backend** | `http://192.168.1.12:8848` |

## Vercel Rewrites

```json
{
  "source": "/api/v1/(.*)",
  "destination": "http://192.168.1.12:8848/api/v1/$1"
}
```

## Deploy Steps

### 1. Home Server (Backend)
```bash
# Trên server 192.168.1.12
cd /path/to/dashboard
python server.py
# Chạy trên port 8848
```

### 2. Vercel (Frontend)
```bash
cd web
vercel --prod
```

## MT5 EA Configuration

Trong MT5 EA settings:
```env
API_URL=https://autonomous-trading-engine.vercel.app/api/v1
BRIDGE_TOKEN=20022007@Tu
```

# Autonomous Trading Engine (ATE) - By QTusdev (Nguyễn Quang Tú)

> **Tác giả / Lead Developer**: Nguyễn Quang Tú (QTusdev)  
> **GitHub**: [https://github.com/qtu11/Autonomous-Trading-Engine](https://github.com/qtu11/Autonomous-Trading-Engine) 



# 4 PHƯƠNG PHÁP TRADING + PD ARRAYS + PYTHON MT5 PIPELINE
## Indicator-Based · SMC · ICT · Ultra Confluence — Kiến thức chi tiết & Code detect thật

> **Symbol tham chiếu:** XAUUSD (XAUUSDm — Exness)
> **Timeframe sử dụng:** M1, M5, M15, H1, H4
> **Phạm vi tài liệu:** Kiến thức kỹ thuật đầy đủ + pipeline Python lấy dữ liệu MT5 → dựng nến → quy hoạch phát hiện OB/FVG/CHoCH/PD Arrays → sinh tín hiệu → khung risk gate trước khi gửi lệnh.

---

## ⚠️ GHI CHÚ QUAN TRỌNG TRƯỚC KHI ĐỌC

Tài liệu này trình bày **logic kỹ thuật** của 4 phương pháp và cách lập trình để phát hiện chúng bằng Python. Đây là kiến thức có thể kiểm chứng: định nghĩa OB là gì, FVG hình thành như thế nào, CHoCH xác nhận ra sao — những khái niệm này có định nghĩa rõ ràng và code detect có thể test được ngay.

**Điều tài liệu này KHÔNG làm:** đưa ra con số winrate cụ thể (ví dụ "70-80%" hay ">90%") như thể đó là sự thật đã kiểm chứng. Winrate của bất kỳ phương pháp nào — kể cả khi code detect hoàn toàn đúng — chỉ có thể biết được bằng cách **backtest trên dữ liệu lịch sử thật** của XAUUSDm qua nhiều điều kiện thị trường (trending, sideway, high volatility news). Phần cuối tài liệu có khung backtest để bạn tự đo winrate thật trên dữ liệu của mình, thay vì tin vào con số giả định.

Một hệ thống "AI trade auto mở lệnh" chỉ nên đi vào live/demo sau khi:
1. Code detect PD Arrays đã unit-test đúng trên dữ liệu lịch sử đã biết trước kết quả.
2. Backtest full lịch sử (tối thiểu 1-2 năm M15/H1) cho ra equity curve, drawdown, winrate, R:R thực tế.
3. Risk gate (Chương VI) đã chặn được các trường hợp entry sai trước khi CTrade nhận lệnh.

---

## MỤC LỤC

- **Chương I** — Nền tảng PD Arrays (Premium/Discount Arrays): định nghĩa, phân loại, quy tắc nhận diện từng loại
- **Chương II** — Phương pháp 1: Indicator-Based Trading (EMA/RSI/ATR/Pivot)
- **Chương III** — Phương pháp 2: Smart Money Concepts (SMC)
- **Chương IV** — Phương pháp 3: Inner Circle Trader (ICT)
- **Chương V** — Phương pháp 4: Ultra Confluence Matrix (Hybrid đa lớp)
- **Chương VI** — Python Pipeline: Kết nối MT5 → OHLCV → Swing Points
- **Chương VII** — Python Pipeline: Detect Order Block, Breaker Block, Mitigation Block
- **Chương VIII** — Python Pipeline: Detect FVG, CHoCH/MSS, Liquidity Sweep
- **Chương IX** — Python Pipeline: Killzone Filter, OTE, Premium/Discount Zone
- **Chương X** — Signal Engine: Ghép tầng Confluence → Sinh tín hiệu BUY/SELL
- **Chương XI** — Risk Gate & Order Dispatch (kết nối MT5 gửi lệnh có kiểm soát)
- **Chương XII** — Khung Backtest để đo Winrate thật trên dữ liệu của bạn

---

# CHƯƠNG I: NỀN TẢNG PD ARRAYS (PREMIUM/DISCOUNT ARRAYS)

## 1.1 PD Array là gì?

**PD Array (Premium/Discount Array)** là thuật ngữ ICT dùng để gọi chung tất cả các **vùng giá trên biểu đồ mà thuật toán/tổ chức lớn (Smart Money) để lại dấu vết**, và giá có xu hướng quay lại (return/retest) các vùng này trước khi tiếp diễn hoặc đảo chiều xu hướng.

Tên gọi "Premium/Discount" xuất phát từ việc mỗi PD Array chỉ có ý nghĩa giao dịch cao khi nó nằm đúng phía của range (dựa theo Fibonacci 50%):
- **Discount Zone** (dưới 50% của range Swing Low → Swing High): vùng giá "rẻ" — ưu tiên tìm PD Array để **BUY**.
- **Premium Zone** (trên 50% của range): vùng giá "đắt" — ưu tiên tìm PD Array để **SELL**.

PD Array không phải một chỉ báo đơn lẻ, mà là **một họ các cấu trúc hình học** được phân loại theo bản chất hình thành. Việc gọi chung nhóm này giúp thuật toán AI có một tầng trừu tượng thống nhất: thay vì viết logic riêng lẻ cho từng loại, ta có thể xây một `PDArray` object chung với các thuộc tính `type`, `top`, `bottom`, `mitigated`, `strength_score`.

## 1.2 Phân loại đầy đủ 9 loại PD Array chuẩn ICT

ICT phân loại PD Array thành **7 cặp kinh điển** (mỗi cặp có phiên bản Bullish/Bearish) cộng **2 cấu trúc phái sinh** — tổng cộng 9 khái niệm gốc. Phần này trình bày từng loại theo đúng thứ tự ICT dạy, với công thức phân biệt chính xác để code detect không bị nhầm lẫn giữa các loại gần giống nhau (đặc biệt là Breaker vs Mitigation, và OB vs Rejection Block).

### 1. Old High / Old Low — Buy-side & Sell-side Liquidity (BSL/SSL)

**Định nghĩa:** Đây là nền tảng của mọi PD Array khác — không phải vùng entry, mà là **nơi tập trung thanh khoản chờ sẵn** mà mọi cấu trúc khác (OB, Breaker, FVG...) đều phải tham chiếu tới để xác định tính hợp lệ.

- **BSL (Buy-side Liquidity)**: nằm tại đỉnh cũ (Old High) — nơi tập trung lệnh Stop Loss của phe đang SELL và lệnh chờ Buy Stop của phe muốn mua breakout. Giá có xu hướng bị "hút" lên đây trước khi đảo chiều xuống.
- **SSL (Sell-side Liquidity)**: nằm tại đáy cũ (Old Low) — nơi tập trung SL của phe đang BUY và lệnh chờ Sell Stop. Giá có xu hướng bị "hút" xuống đây trước khi đảo chiều lên.

**Phân cấp Old High/Low theo khung thời gian** (càng cao khung càng nhiều thanh khoản tích luỹ):
```
Old High/Low cấp 1 (yếu nhất): Swing High/Low nội bộ M5/M15 (vài giờ gần nhất)
Old High/Low cấp 2: Đỉnh/đáy phiên (Asian High/Low, London High/Low)
Old High/Low cấp 3: Đỉnh/đáy ngày hôm trước (Previous Day High/Low — PDH/PDL)
Old High/Low cấp 4 (mạnh nhất): Đỉnh/đáy tuần trước (Previous Week High/Low — PWH/PWL)
```

**Nguyên tắc dùng cho AI:** một BSL/SSL càng nhiều lần bị test mà chưa bị quét (untested) và càng nằm ở khung thời gian cao, xác suất giá "cố tình" hướng tới để quét càng lớn — đây là cơ sở để tính `liquidity_strength_score` khi xếp hạng nhiều mục tiêu cùng lúc.

### 2. Rejection Block (Khối từ chối)

**Định nghĩa:** Khác với Order Block (dùng toàn bộ range nến để xác định vùng), Rejection Block chỉ dùng phần **wick** (râu nến) tại vùng đỉnh/đáy — biểu thị vùng giá bị từ chối mạnh bởi một nhóm nến liên tiếp (không nhất thiết chỉ 1 nến).

- **Bearish Rejection Block**: tại vùng đỉnh, vùng giá tính từ **mức Open/Close cao nhất** của cụm nến đến **đỉnh cao nhất của các râu nến** trong cụm đó. Đây là vùng kháng cự.
- **Bullish Rejection Block**: tại vùng đáy, vùng giá tính từ **mức Open/Close thấp nhất** của cụm nến đến **đáy thấp nhất của các râu nến** trong cụm đó. Đây là vùng hỗ trợ.

**Công thức xác định (khác biệt cốt lõi so với OB):**
```
Xét cụm N nến quanh 1 Swing High:
  body_extreme = max(Open, Close) của TẤT CẢ nến trong cụm  (không lấy High)
  wick_extreme = max(High) của TẤT CẢ nến trong cụm

  Bearish Rejection Block: top = wick_extreme, bottom = body_extreme

Xét cụm N nến quanh 1 Swing Low:
  body_extreme = min(Open, Close) của TẤT CẢ nến trong cụm  (không lấy Low)
  wick_extreme = min(Low) của TẤT CẢ nến trong cụm

  Bullish Rejection Block: top = body_extreme, bottom = wick_extreme
```

**Phân biệt với OB:** OB lấy toàn bộ range (High-Low) của **một nến cụ thể** (nến đối lập cuối cùng); Rejection Block lấy phần **wick tổng hợp** của **một cụm nến** tại vùng đỉnh/đáy. Rejection Block thường cho vùng entry hẹp hơn OB vì chỉ tính phần râu bị từ chối, không tính toàn bộ thân nến.

### 3. Order Block (OB) — Khối lệnh

**Định nghĩa:** Nến (hoặc chuỗi nến) đối lập xu hướng **cuối cùng** trước khi giá tạo ra một dịch chuyển mạnh (displacement) phá vỡ cấu trúc thị trường (MSS/CHoCH/BOS).

- **Bullish OB**: Nến giảm cuối cùng trước khi giá tăng mạnh (phá vỡ cấu trúc thị trường theo hướng tăng).
- **Bearish OB**: Nến tăng cuối cùng trước khi giá giảm mạnh (phá vỡ cấu trúc thị trường theo hướng giảm).

**Vùng giá của OB:**
- `top = high của nến OB`, `bottom = low của nến OB` (dùng toàn bộ range nến — khác Rejection Block ở mục 2).

**Điều kiện OB hợp lệ (Valid OB):**
1. Phải có **displacement** ngay sau đó (nến/chuỗi nến thân lớn, đóng cửa vượt swing point).
2. Displacement phải để lại **FVG** đi kèm (OB không có FVG theo sau thường yếu, gọi là "weak OB").
3. OB chưa bị **mitigated** (giá chưa quay lại xuyên thủng toàn bộ vùng OB).

**Phân cấp OB:**
- **HTF OB** (H4/H1): độ tin cậy cao hơn, dùng làm vùng entry chính.
- **LTF OB** (M15/M5): dùng để tinh chỉnh entry (refinement) bên trong vùng HTF OB.

### 4. Fair Value Gap (FVG) — SIBI / BISI

**Định nghĩa:** Khoảng trống giá hình thành khi nến giữa trong chuỗi 3 nến di chuyển quá nhanh khiến nến 1 và nến 3 không có phần wick chồng lấp lên nhau — biểu thị mất cân bằng giữa lực mua và lực bán.

ICT gọi tên riêng theo hướng:
- **BISI (Buyside Imbalance Sellside Inefficiency)** = **Bullish FVG**: khoảng trống tạo bởi mô hình 3 nến tăng.
- **SIBI (Sellside Imbalance Buyside Inefficiency)** = **Bearish FVG**: khoảng trống tạo bởi mô hình 3 nến giảm.

**Công thức xác định (3-candle pattern), với index nến `i-2, i-1, i`:**
- **Bullish FVG (BISI)**: `low[i] > high[i-2]` → khoảng trống nằm giữa `high[i-2]` (bottom) và `low[i]` (top).
- **Bearish FVG (SIBI)**: `high[i] < low[i-2]` → khoảng trống nằm giữa `high[i]` (bottom) và `low[i-2]` (top).

**CE (Consequent Encroachment):** điểm giữa của FVG — `(top + bottom) / 2`. Mức giá ICT coi là "50% fill" — nơi entry lý tưởng nhất vì xác suất giá phản ứng cao nhất trước khi FVG bị lấp hoàn toàn.

**Phân loại FVG theo mức độ lấp đầy:** Virgin (chưa chạm) → Partially Filled (chạm nhưng chưa qua CE) → CE Filled (đã chạm CE, vùng bắt đầu yếu) → Fully Filled (đã đi xuyên hết, vô hiệu).

### 5. Liquidity Void (Khoảng trống thanh khoản)

**Định nghĩa:** Khác với FVG (chỉ cần 3 nến để hình thành), Liquidity Void là vùng giá di chuyển **cực mạnh liên tục nhiều nến** với thân nến dài, gần như không có wick đối ứng — biểu thị giá "chạy quá nhanh" khiến gần như không có giao dịch hai chiều nào diễn ra tại vùng đó.

- **Bullish Liquidity Void**: chuỗi nhiều nến tăng thân dài liên tiếp, wick dưới rất ngắn hoặc gần như không có, để lại một khoảng trống thanh khoản lớn phía dưới giá hiện tại.
- **Bearish Liquidity Void**: chuỗi nhiều nến giảm thân dài liên tiếp, wick trên rất ngắn hoặc gần như không có.

**Công thức xác định (khác FVG ở việc xét N nến liên tiếp, không phải pattern 3 nến cố định):**
```
Xét chuỗi N nến liên tiếp cùng hướng (N >= 3):
  Với mỗi nến trong chuỗi: body_ratio >= ngưỡng cao (ví dụ 0.75)
                            wick đối ứng (upper wick cho nến giảm,
                            lower wick cho nến tăng) rất nhỏ so với body

  Nếu TẤT CẢ nến trong chuỗi thoả điều kiện trên
  → Liquidity Void = [Low của nến đầu chuỗi, High của nến cuối chuỗi]
    (hoặc ngược lại tuỳ hướng)
```

**Phân biệt với FVG:** FVG là một "khe hở" cụ thể giữa 2 nến biên trong pattern 3-nến (có toạ độ top/bottom rõ ràng, hẹp). Liquidity Void là **toàn bộ vùng di chuyển** của một chuỗi nến dài (rộng hơn nhiều, không có công thức 3-nến cố định) — về bản chất Liquidity Void thường "chứa" nhiều FVG nhỏ bên trong nó.

### 6. Breaker Block (BB) — Khối phá vỡ

**Định nghĩa:** Một Order Block đã **thất bại** (bị giá xuyên thủng), NHƯNG với điều kiện bắt buộc: sự thất bại đó xảy ra **sau khi giá đã quét thanh khoản (BSL/SSL)** — đây là điểm khác biệt quan trọng ICT nhấn mạnh so với định nghĩa Breaker "chung chung" của SMC.

- **Bearish Breaker**: Bullish OB cao nhất trong một chuỗi bị giá xuyên thủng xuống dưới, với điều kiện: **trước đó giá đã quét BSL (đỉnh cũ)**. Cơ chế: giá quét thanh khoản đỉnh (thu hút lệnh Buy Stop + kích SL của Sell) → sau đó đảo chiều giảm mạnh xuyên qua toàn bộ Bullish OB → vùng OB cũ giờ trở thành kháng cự khi giá hồi lại.
- **Bullish Breaker**: Bearish OB thấp nhất bị giá xuyên thủng lên trên, với điều kiện: **trước đó giá đã quét SSL (đáy cũ)**.

**Công thức xác định (bắt buộc có bước quét thanh khoản trước):**
```
Bearish Breaker hợp lệ khi VÀ CHỈ KHI theo đúng thứ tự thời gian:
  1. Giá quét BSL (High[i] > BSL_target, xác nhận sweep — mục Chương VIII.3)
  2. SAU sweep đó, giá đảo chiều và đóng cửa (close) xuyên thủng
     xuống dưới đáy của Bullish OB gần nhất trước sweep
  → Breaker = vùng của Bullish OB đó, direction đổi thành BEARISH

Bullish Breaker: đối xứng, sweep SSL trước, rồi close xuyên lên trên Bearish OB
```

**Ý nghĩa với AI:** Vì đã có 2 lớp xác nhận (sweep thanh khoản + phá vỡ OB bằng close), Breaker Block theo đúng chuẩn ICT là một trong những PD Array có độ tin cậy cấu trúc cao nhất — nhưng đồng thời cũng hiếm gặp hơn (2 điều kiện phải khớp đúng thứ tự).

### 7. Mitigation Block (MB) — Khối giảm thiểu

**Định nghĩa:** Tương tự cơ chế Breaker Block về mặt hình học (OB cũ bị phá và đổi vai trò), NHƯNG khác biệt cốt lõi: sóng di chuyển trước đó **THẤT BẠI trong việc quét thanh khoản** — tức giá chưa kịp chạm tới BSL/SSL thì đã đảo chiều rồi phá luôn OB theo hướng ngược lại.

- **Bearish Mitigation Block**: giống cơ chế Bearish Breaker, nhưng sóng tăng trước đó **không quét được đỉnh cũ (BSL)** — giá tăng chưa đủ để chạm BSL thì đã đảo chiều giảm và phá xuyên Bullish OB.
- **Bullish Mitigation Block**: giống Bullish Breaker, nhưng sóng giảm trước đó **không quét được đáy cũ (SSL)**.

**Công thức phân biệt Breaker vs Mitigation (đây là điểm hay bị nhầm nhất khi code):**
```
Nếu (đã có sweep BSL/SSL hợp lệ TRƯỚC khi OB bị phá) → Breaker Block
Nếu (KHÔNG có sweep hợp lệ, giá đảo chiều sớm rồi mới phá OB) → Mitigation Block
```

**Ý nghĩa với AI:** Vì thiếu bước "dọn thanh khoản" trước, Mitigation Block về lý thuyết có độ tin cậy thấp hơn Breaker Block — thị trường "chưa lấy đủ" thanh khoản ở phía đối diện, nên khả năng còn quay lại lấy nốt (tạo nhiễu, hoặc phá luôn Mitigation Block) cao hơn.

### 8. Inversion FVG (iFVG) — Cấu trúc phái sinh 1

**Định nghĩa:** Một FVG (mục 4) đã bị giá xuyên thủng **hoàn toàn** (Fully Filled) — khi đó bản chất của vùng đó đảo ngược vai trò: từ vùng hỗ trợ/kháng cự nguyên thuỷ trở thành vùng đối lập.

**Ví dụ cụ thể:** Một Bullish FVG (kỳ vọng giá bật lên khi hồi về) bị giá xuyên thủng hoàn toàn xuống dưới đáy FVG đó → khi giá sau này quay lại retest đúng vùng này từ phía dưới lên, vùng đó giờ đóng vai trò **kháng cự** (gọi là Bearish iFVG).

**Công thức xác định:**
```
Với 1 FVG đã Fully Filled (theo hàm get_fvg_fill_state() — Chương VIII.1):
  Bullish FVG bị Fully Filled (giá đóng cửa dưới bottom của FVG)
    → tạo Bearish iFVG tại đúng vùng [bottom, top] cũ

  Bearish FVG bị Fully Filled (giá đóng cửa trên top của FVG)
    → tạo Bullish iFVG tại đúng vùng [bottom, top] cũ
```

**Phân biệt với Breaker/Mitigation Block:** Breaker/Mitigation áp dụng cho **Order Block**; Inversion FVG áp dụng cho **Fair Value Gap**. Cùng một cơ chế logic (thất bại → đổi vai trò) nhưng khác loại PD Array gốc.

### 9. Propagator Block / Propulsion Block — Cấu trúc phái sinh 2

**Định nghĩa:** Một Order Block đặc biệt hình thành **ngay sau khi giá vừa phản ứng và bật lên/xuống thành công từ một OB trước đó** — tức đây là OB "thế hệ thứ 2", xác nhận rằng OB gốc vẫn còn hiệu lực và động lượng đang tiếp diễn.

**Cơ chế hình thành:**
```
1. Có OB gốc (ví dụ Bullish OB #1) — giá chạm vào và bật lên thành công
2. Giá tăng tạo ra một đợt đẩy mới (thường có FVG mới đi kèm)
3. Trong đợt đẩy mới đó, nến đối lập cuối cùng trước displacement tiếp theo
   → chính là Propagator Block (Bullish OB #2)
```

**Ý nghĩa với AI:** Propagator Block dùng để **xác nhận xu hướng đang tiếp diễn khoẻ mạnh** — nếu giá liên tục tạo ra chuỗi Propagator Block cùng hướng (OB #1 → phản ứng → OB #2 → phản ứng → OB #3...), đây là tín hiệu trend mạnh, khác với trường hợp chỉ có 1 OB đơn lẻ rồi đảo chiều ngay. Về mặt code, Propagator Block chính là kết quả của việc chạy lại `detect_order_blocks()` (Chương VII.2) trên đoạn dữ liệu **sau** khi OB gốc đã được test thành công — không cần thuật toán riêng, chỉ cần thêm điều kiện lọc "OB này có nằm sau một lần test-thành-công của OB liền trước cùng hướng không".

## 1.3 Bảng tổng hợp 9 loại PD Array

| # | Loại PD Array | Vai trò | Điều kiện xác nhận cốt lõi | Độ ưu tiên entry |
|---|---|---|---|---|
| 1 | Old High/Low (BSL/SSL) | Mục tiêu / điều kiện sweep | Đỉnh/đáy theo cấp khung thời gian | Không phải entry — target/filter |
| 2 | Rejection Block | Vùng entry (dựa wick cụm nến) | Vùng wick tổng hợp tại đỉnh/đáy | Trung bình-Cao |
| 3 | Order Block (OB) | Vùng entry chính | Nến đối lập cuối + displacement + FVG theo sau | Cao (nếu HTF) |
| 4 | Fair Value Gap (FVG/BISI/SIBI) | Vùng entry tinh chỉnh | 3-candle imbalance pattern | Cao (đặc biệt tại CE) |
| 5 | Liquidity Void | Vùng "chân không" giá, ít dùng làm entry trực tiếp | Chuỗi N nến thân dài liên tiếp cùng hướng | Thấp (dùng làm target/context hơn entry) |
| 6 | Breaker Block | Vùng entry sau thất bại + đã sweep | OB cũ bị phá bằng close, SAU khi đã sweep BSL/SSL | Rất cao (2 lớp xác nhận) |
| 7 | Mitigation Block | Vùng entry sau thất bại, chưa sweep | OB cũ bị phá bằng close, KHÔNG có sweep trước đó | Trung bình |
| 8 | Inversion FVG (iFVG) | Vùng entry sau FVG thất bại | FVG bị Fully Filled, đổi vai trò | Cao |
| 9 | Propagator Block | Xác nhận trend tiếp diễn | OB thế hệ 2 sau khi OB gốc test thành công | Dùng để xác nhận trend, không phải entry độc lập |

## 1.4 Nguyên tắc Premium/Discount áp dụng lên PD Array

Bất kể loại PD Array nào, AI chỉ nên xem xét entry nếu **vị trí của PD Array đó nằm đúng phía Premium/Discount** so với range HTF đang xét:

```
range = swing_high_HTF - swing_low_HTF
fib_50 = swing_low_HTF + range * 0.5

Nếu PD_Array.top < fib_50  → nằm trong Discount → chỉ xét BUY
Nếu PD_Array.bottom > fib_50 → nằm trong Premium → chỉ xét SELL
Nếu PD_Array giao cắt fib_50 → vùng mơ hồ → giảm điểm confidence hoặc bỏ qua
```

Đây chính là LỚP 1 trong ma trận Ultra Confluence (Chương V) — mọi PD Array phát hiện được ở LTF đều phải lọc qua điều kiện này trước khi được coi là ứng viên entry.

---

# CHƯƠNG II: PHƯƠNG PHÁP 1 — INDICATOR-BASED TRADING

## 2.1 Triết lý phương pháp

Phương pháp dựa trên chỉ báo kỹ thuật cổ điển: dùng các đường trung bình động và dao động động lượng để xác định xu hướng và điểm entry, không quan tâm đến cấu trúc thanh khoản hay hành vi tổ chức. Đây là phương pháp có độ trễ (lagging) cao nhất trong 4 phương pháp vì tất cả chỉ báo đều tính toán từ giá đã đóng cửa (trailing).

## 2.2 Bộ chỉ báo sử dụng

| Chỉ báo | Tham số | Vai trò |
|---|---|---|
| EMA | 20, 50, 200 | Xác định xu hướng theo stacking (xếp tầng) |
| RSI | 14 | Lọc vùng quá mua/quá bán, xác nhận động lượng |
| ATR | 14 | Đo biến động, dùng tính SL/TP động |
| Pivot Points | Daily (PP, R1, R2, S1, S2) | Vùng hỗ trợ/kháng cự tĩnh trong ngày |

## 2.3 Công thức tính chỉ báo (chuẩn hoá để code)

**EMA (Exponential Moving Average):**
```
multiplier = 2 / (period + 1)
EMA[i] = (Close[i] - EMA[i-1]) * multiplier + EMA[i-1]
EMA[0] = SMA(period)  # giá trị khởi tạo dùng SMA
```

**RSI (Relative Strength Index, Wilder's smoothing):**
```
delta = Close[i] - Close[i-1]
gain = delta nếu delta > 0 else 0
loss = -delta nếu delta < 0 else 0

avg_gain[i] = (avg_gain[i-1] * (period-1) + gain) / period
avg_loss[i] = (avg_loss[i-1] * (period-1) + loss) / period

RS = avg_gain / avg_loss
RSI = 100 - (100 / (1 + RS))
```

**ATR (Average True Range, Wilder's smoothing):**
```
TR[i] = max(
    High[i] - Low[i],
    abs(High[i] - Close[i-1]),
    abs(Low[i] - Close[i-1])
)
ATR[i] = (ATR[i-1] * (period-1) + TR[i]) / period
```

**Pivot Points (Standard, tính từ OHLC ngày trước):**
```
PP = (High_yesterday + Low_yesterday + Close_yesterday) / 3
R1 = 2*PP - Low_yesterday
S1 = 2*PP - High_yesterday
R2 = PP + (High_yesterday - Low_yesterday)
S2 = PP - (High_yesterday - Low_yesterday)
```

## 2.4 Quy tắc vào lệnh chi tiết

**Điều kiện BUY (tất cả phải đúng đồng thời):**
1. `Close[i] > EMA20[i]`
2. Xếp tầng: `EMA20[i] > EMA50[i] > EMA200[i]`
3. `50.0 <= RSI14[i] <= 70.0`
4. `ATR14[i] >= ngưỡng biến động tối thiểu` (tránh sideway — ngưỡng nên tự tính bằng percentile ATR lịch sử của symbol, không hardcode một số cố định vì biến động vàng thay đổi theo giai đoạn thị trường)

**Điều kiện SELL (đối xứng):**
1. `Close[i] < EMA20[i]`
2. Xếp tầng: `EMA20[i] < EMA50[i] < EMA200[i]`
3. `30.0 <= RSI14[i] <= 50.0`
4. `ATR14[i] >= ngưỡng biến động tối thiểu`

**Quy tắc SL/TP (ATR-based, không cố định pip):**
```
BUY:  SL = Entry - (1.5 * ATR14)     TP = Entry + (3.0 * ATR14)
SELL: SL = Entry + (1.5 * ATR14)     TP = Entry - (3.0 * ATR14)
```

## 2.5 Điểm mạnh / điểm yếu (khách quan, không gắn số winrate)

**Điểm mạnh:**
- Tốc độ tính toán cực nhanh, không cần phân tích cấu trúc phức tạp.
- Logic if-then đơn giản, dễ debug, dễ backtest, ít lỗi logic khi code.
- Hoạt động ổn định trên thị trường trending rõ ràng.

**Điểm yếu cấu trúc (không phải ý kiến, mà là hệ quả toán học của phương pháp):**
- EMA là hàm trung bình trượt → luôn có độ trễ so với hành động giá thật. Trong giai đoạn sideway, `EMA20` cắt qua cắt lại đường giá liên tục → sinh tín hiệu giả (whipsaw) nhiều nhất trong 4 phương pháp vì không có bộ lọc cấu trúc/thanh khoản nào chặn lại.
- RSI trong xu hướng mạnh có thể duy trì vùng quá mua/quá bán rất lâu (RSI divergence không được xử lý ở đây) khiến điều kiện lọc `50-70` hoặc `30-50` bỏ lỡ phần lớn nhịp trend mạnh nhất.
- Không có khái niệm thanh khoản/OB/FVG → không phân biệt được đâu là entry tại vùng tổ chức lớn thật sự tham gia và đâu là entry ngẫu nhiên theo giá.

---

# CHƯƠNG III: PHƯƠNG PHÁP 2 — SMART MONEY CONCEPTS (SMC)

## 3.1 Triết lý phương pháp

SMC dựa trên giả thuyết rằng thị trường được vận hành bởi dòng tiền lớn (ngân hàng, quỹ tổ chức), và dòng tiền này để lại dấu vết hình học trên biểu đồ thông qua: nơi họ đặt lệnh (Order Block), nơi họ quét thanh khoản trước khi di chuyển (Liquidity), và cách cấu trúc thị trường thay đổi khi họ đảo hướng (BOS/CHoCH). Khác với Phương pháp 1, SMC không dùng chỉ báo trễ mà phân tích trực tiếp hình học của nến.

## 3.2 Cấu trúc thị trường: BOS vs CHoCH (phân biệt chính xác)

Đây là 2 khái niệm hay bị dùng lẫn lộn nhất trong SMC, nên cần tách bạch rõ trước khi vào quy trình entry:

| | BOS (Break of Structure) | CHoCH (Change of Character) |
|---|---|---|
| Ý nghĩa | **Tiếp diễn** xu hướng hiện tại | **Đảo chiều** xu hướng hiện tại |
| Điều kiện | Trong uptrend: giá phá HH cũ tạo HH mới. Trong downtrend: giá phá LL cũ tạo LL mới | Trong uptrend: giá phá vỡ HL gần nhất (không tạo được HL mới, quay đầu giảm qua đáy cũ). Trong downtrend: giá phá vỡ LH gần nhất |
| Vai trò với entry | Xác nhận trend còn khoẻ → tìm entry tiếp diễn (continuation) tại OB cùng hướng trend | Tín hiệu đầu tiên trend có thể đổi hướng → tìm entry đảo chiều (reversal) tại OB hướng mới |

**Công thức xác định (close-based):**
```
Trong UPTREND (đang có chuỗi HH-HL):
  BOS Bullish: Close[i] > HH gần nhất (đỉnh trước đó)  → tiếp diễn tăng
  CHoCH Bearish: Close[i] < HL gần nhất (đáy tăng gần nhất) → khả năng đảo chiều giảm

Trong DOWNTREND (đang có chuỗi LH-LL):
  BOS Bearish: Close[i] < LL gần nhất  → tiếp diễn giảm
  CHoCH Bullish: Close[i] > LH gần nhất (đỉnh giảm gần nhất) → khả năng đảo chiều tăng
```

**Điểm mấu chốt cho thuật toán:** BOS và CHoCH dùng CÙNG một sự kiện "giá đóng cửa vượt một swing point" — điều phân biệt chúng không phải công thức khác nhau, mà là **swing point nào bị phá** (swing point cùng hướng trend hiện tại = BOS; swing point ngược hướng = CHoCH) và **trend hiện tại đang là gì** trước khi sự kiện đó xảy ra. Vì vậy code phải luôn biết trend hiện tại (`classify_trend_structure()` — Chương VI.3) trước khi phân loại sự kiện phá vỡ là BOS hay CHoCH.

## 3.3 Khung thời gian sử dụng

- **HTF (High Timeframe)**: H4/H1 — xác định bias (thiên hướng) tổng thể qua chuỗi BOS.
- **LTF (Low Timeframe)**: M15 — tìm điểm entry chính xác bên trong bias HTF, dùng CHoCH nội bộ M15 để bắt điểm hồi (retracement) trước khi vào theo hướng HTF.

## 3.4 Các công cụ bổ sung của SMC

### IFC (Institutional Funded Candle)

**Định nghĩa:** Nến "được tổ chức tài trợ" — một nến quét thanh khoản (quét qua SL của đám đông tại một vùng cụ thể) rồi **ngay lập tức** rút râu ngược lại với lực cực mạnh, đóng cửa xa khỏi điểm quét.

**Công thức xác định (khác Liquidity Sweep ở Chương VIII.3 chủ yếu ở mức độ "lực" đóng cửa):**
```
IFC Bullish (quét SSL rồi bật mạnh):
  Low[i] xuyên qua SSL_target
  Close[i] không chỉ > SSL_target mà còn nằm ở nửa TRÊN của range nến
    (close_position = (Close - Low) / (High - Low) >= 0.7)
  → body_ratio của nến cũng nên >= mức trung bình (không phải doji yếu ớt)

IFC Bearish: đối xứng, wick xuyên BSL, Close nằm nửa DƯỚI range (<=0.3), body_ratio đủ lớn
```

IFC về bản chất là một Liquidity Sweep "chất lượng cao" — thêm điều kiện về vị trí đóng cửa trong range để lọc ra những cú quét có lực đảo chiều mạnh nhất, loại bỏ các cú quét yếu (chỉ rút râu nhẹ, đóng cửa gần giữa range).

### Trendline Liquidity

**Định nghĩa:** Ngoài thanh khoản nằm ngang tại Old High/Low (Chương I mục 1), SMC còn xét thanh khoản nằm **dọc theo một đường xu hướng** — nơi các đáy tăng dần (uptrend) hoặc đỉnh giảm dần (downtrend) tạo thành một đường chéo, và đám đông có xu hướng đặt SL ngay dưới/trên đường đó theo kiểu "trailing".

**Cách xác định bằng thuật toán:**
```
1. Lấy 3+ Swing Low liên tiếp trong uptrend (hoặc Swing High trong downtrend)
2. Fit một đường thẳng (linear regression đơn giản) qua các điểm đó
3. Trendline Liquidity = vùng giá nằm ngay dưới đường thẳng đó (uptrend)
   hoặc ngay trên (downtrend)
4. Khi giá đảo chiều xuyên qua đường trendline này (phá trendline bằng wick
   rồi bật lại, tương tự cơ chế Liquidity Sweep) → coi là 1 dạng sweep hợp lệ
```

Trendline Liquidity khó code chính xác hơn Old High/Low vì cần fit đường thẳng động — trong triển khai thực tế nên coi đây là bộ lọc bổ sung (tăng điểm confidence) chứ không phải điều kiện bắt buộc.

### Equilibrium & Premium/Discount (chi tiết hoá từ Chương I.4)

**Equilibrium** là tên SMC gọi mức 50% Fibonacci — đúng bằng `fib_50` đã định nghĩa ở Chương I.4, không phải khái niệm mới:

```
Equilibrium = Swing_Low + (Swing_High - Swing_Low) * 0.5
Premium Zone = (Equilibrium, Swing_High]   → chỉ tìm SELL
Discount Zone = [Swing_Low, Equilibrium)   → chỉ tìm BUY
```

SMC nhấn mạnh: một OB/FVG hợp lệ về mặt hình học nhưng nằm SAI phía Equilibrium (ví dụ Bullish OB nằm trong vùng Premium) có xác suất thất bại cao hơn — đây là lý do LỚP 1 của Ultra Confluence Matrix (Chương V) luôn bắt buộc kiểm tra Premium/Discount trước tiên.

## 3.5 Quy trình 4 bước Entry chi tiết

### Bước 1 — Xác định xu hướng H1/H4 bằng chuỗi BOS

Xu hướng được xác định bằng chuỗi đỉnh/đáy Swing và các sự kiện BOS liên tiếp cùng hướng (Chương III.2). Swing Point được xác định bằng thuật toán Fractal (Chương VI.3).

### Bước 2 — Phát hiện Liquidity Sweep / IFC tại M15

Giá M15 phải xuyên qua BSL/SSL (hoặc Trendline Liquidity) bằng wick, đóng cửa rút lại vào trong range — lý tưởng nhất nếu đạt tiêu chuẩn IFC (đóng cửa mạnh về phía đối diện điểm quét, không chỉ "vừa đủ" rút lại).

### Bước 3 — Xác nhận CHoCH nội bộ M15

Sau sweep, chờ nến M15 đóng cửa xác nhận CHoCH theo đúng hướng bias HTF (Chương III.2) — đây là dấu hiệu phe quét thanh khoản đã thực sự đảo chiều, không phải chỉ là một cú rút râu đơn lẻ không có tiếp diễn.

### Bước 4 — Entry tại Order Block

Sau khi có CHoCH hợp lệ:
1. Xác định nến OB: nến đối lập cuối cùng **ngay trước** chuỗi nến tạo ra CHoCH (Chương I mục 3).
2. Đặt lệnh chờ:
   - **BUY LIMIT** tại `high` của Bullish OB (hoặc tại CE của FVG nếu OB có FVG đi kèm).
   - **SELL LIMIT** tại `low` của Bearish OB.

## 3.6 Quy tắc SL/TP

```
BUY:  SL = Low(OB) - buffer(2 pips tương đương ~0.20 với XAUUSD)
      TP = Swing High H1 tiếp theo (không cố định R:R — target theo cấu trúc)

SELL: SL = High(OB) + buffer
      TP = Swing Low H1 tiếp theo
```

## 3.7 ★ BỘ TIÊU CHÍ "ENTRY ĐẸP" TRONG SMC

Một entry SMC không tự động "đẹp" chỉ vì thoả mãn 4 bước tối thiểu ở trên — 4 bước đó là điều kiện **cần**, không phải **đủ**. Dưới đây là các tiêu chí phân tầng chất lượng, dùng để tính `entry_quality_score` thay vì chỉ có APPROVED/REJECTED nhị phân:

| # | Tiêu chí | Vì sao quan trọng | Cách kiểm tra |
|---|---|---|---|
| 1 | **OB có FVG đi kèm** (không phải "weak OB") | OB không để lại FVG nghĩa là displacement sau đó yếu — giá không thực sự "vội vã" rời khỏi vùng đó | `ob.has_fvg_confluence == True` (Chương VIII.1, hàm `link_fvg_to_order_blocks`) |
| 2 | **OB nằm đúng phía Discount/Premium** | OB đúng phía Equilibrium có thêm 1 lớp xác nhận độc lập | `classify_pd_array_zone(ob, pd_zone) == "DISCOUNT"` (cho BUY) hoặc `"PREMIUM"` (cho SELL) |
| 3 | **Sweep trước CHoCH đạt chuẩn IFC** (không chỉ sweep thường) | Lực đảo chiều mạnh ngay tại điểm quét là dấu hiệu tổ chức thực sự tham gia, không phải nhiễu ngẫu nhiên | `close_position >= 0.7` (BUY) hoặc `<= 0.3` (SELL) như công thức mục 3.4 |
| 4 | **OB là OB đầu tiên chưa bị test (untested/virgin)** | OB đã bị giá chạm nhiều lần trước đó thường yếu dần theo mỗi lần test — nguyên tắc tương tự FVG fill state | Kiểm tra không có nến nào giữa lúc hình thành OB và hiện tại đã chạm vào vùng OB |
| 5 | **Khoảng cách OB → CHoCH không quá xa (không "already moved")** | Nếu giá đã chạy quá xa khỏi OB trước khi retest, phần lớn "phần thưởng" của chuyển động đã bị bỏ lỡ, R:R còn lại kém hấp dẫn | So sánh khoảng cách hiện tại từ giá tới OB với ATR M15 — nếu > 3×ATR, entry kém hấp dẫn dù vẫn hợp lệ |
| 6 | **Có Inducement (IDM) bị quét trước OB** | Xác nhận 2 lớp thanh khoản nội bộ đã bị dọn (không chỉ 1 lớp BSL/SSL chính) — độ tin cậy cấu trúc cao hơn (Chương I, nguyên tắc Inducement) | Kiểm tra có 1 swing nhỏ hơn nằm giữa OB và CHoCH đã bị giá quét qua trước khi tạo CHoCH chính |
| 7 | **TP tới target tiếp theo cho R:R tối thiểu chấp nhận được** | Một OB hoàn hảo về cấu trúc nhưng TP quá gần (target thanh khoản kế tiếp sát ngay entry) không đáng risk | `(TP - Entry) / (Entry - SL) >= ngưỡng tối thiểu bạn tự đặt (ví dụ 1.5)`, tính trước khi tạo signal |

**Công thức tổng hợp entry_quality_score (ví dụ, không phải chuẩn cố định — nên tự hiệu chỉnh qua backtest):**
```python
def score_smc_entry(ob, pd_zone, sweep_close_position, is_untested, distance_atr_ratio, has_idm, rr_ratio) -> dict:
    score = 0
    max_score = 7
    breakdown = []

    if ob.has_fvg_confluence:
        score += 1; breakdown.append("OB_HAS_FVG")
    if is_untested:
        score += 1; breakdown.append("OB_UNTESTED")
    if distance_atr_ratio <= 3.0:
        score += 1; breakdown.append("DISTANCE_ACCEPTABLE")
    if has_idm:
        score += 1; breakdown.append("IDM_SWEPT")
    if rr_ratio >= 1.5:
        score += 1; breakdown.append("RR_ACCEPTABLE")
    # 2 điểm còn lại (PD zone đúng phía + IFC sweep) nên là điều kiện BẮT BUỘC
    # (chặn cứng, không phải cộng điểm) vì đây là 2 tiêu chí nền tảng nhất — mục 2 và 3 ở trên

    return {"score": score, "max_score": max_score, "breakdown": breakdown,
            "quality_tier": "HIGH" if score >= 5 else "MEDIUM" if score >= 3 else "LOW"}
```

## 3.8 Điểm mạnh / điểm yếu

**Điểm mạnh:**
- TP dựa theo target thanh khoản thật (BSL/SSL) thay vì con số cố định → R:R có thể lớn khi cấu trúc thị trường ủng hộ.
- Loại bỏ được phần lớn nhiễu do sideway vì entry chỉ kích hoạt sau khi có xác nhận CHoCH — không giao dịch liên tục như Phương pháp 1.
- Có nhiều lớp tiêu chí phân tầng chất lượng (mục 3.7) — cho phép thuật toán ưu tiên entry tốt nhất thay vì vào lệnh ngay khi vừa đủ điều kiện tối thiểu.

**Điểm yếu cấu trúc:**
- OB ở khung nhỏ (M5 trở xuống) rất dễ bị phá thủng hoàn toàn (breached) nếu không lọc theo bias HTF.
- Không có bộ lọc thời gian (killzone) — SMC thuần tuý sẵn sàng vào lệnh bất kỳ giờ nào kể cả giờ thanh khoản thấp, nơi cấu trúc dễ bị nhiễu bởi spread rộng và biến động giả.
- Việc phân biệt Inducement (IDM) với Swing Point thật đòi hỏi logic lọc thêm — nếu không lọc IDM, thuật toán dễ nhận nhầm bẫy thanh khoản nội bộ thành swing chính.

---

# CHƯƠNG IV: PHƯƠNG PHÁP 3 — INNER CIRCLE TRADER (ICT)

## 4.1 Triết lý phương pháp

ICT mở rộng SMC bằng cách thêm **yếu tố thời gian** (Time) làm bộ lọc bắt buộc — dựa trên giả thuyết dòng tiền lớn hoạt động theo các "phiên" cụ thể trong ngày (Killzone), và các vùng entry chỉ có ý nghĩa cao khi kết hợp đúng thời điểm với đúng vị trí giá (Price + Time = ICT core). Đây là điểm khác biệt cấu trúc quan trọng nhất so với SMC thuần túy.

## 4.2 Khung thời gian và Killzone (giờ Việt Nam UTC+7)

| Killzone | Giờ VN (UTC+7) | Giờ UTC | Ý nghĩa |
|---|---|---|---|
| Asian Range | 06:00 - 12:00 | 23:00 - 05:00 | Phiên tích luỹ — dùng làm range tham chiếu cho Judas Swing |
| London Killzone | 14:00 - 17:00 | 07:00 - 10:00 | Phiên mở London — thanh khoản cao, dễ có Judas Swing |
| New York Killzone | 19:30 - 22:30 | 12:30 - 15:30 | Phiên overlap NY/London — displacement mạnh nhất trong ngày |

> Lưu ý: giờ UTC có thể lệch 1 giờ giữa DST (Daylight Saving Time) của Mỹ/Âu và giờ VN cố định UTC+7 không đổi DST. Khi code thật, nên lấy giờ server broker (`TimeCurrent()` trong MQL5 hoặc timestamp nến từ MT5) rồi tự quy đổi UTC, không hardcode offset cố định quanh năm.

## 4.3 Quy trình 3 bước chi tiết

### Bước 1 — Judas Swing (Asian Range Sweep)

Trong khoảng đầu London Killzone (thường 14:00-15:30 giờ VN), giá thường tạo một pha di chuyển giả — quét đỉnh hoặc đáy của Asian Range (06:00-12:00) — trước khi đảo chiều đi theo hướng thật trong ngày. Đây gọi là "Judas Swing" (theo nghĩa "cú lừa").

```
asian_high = max(High trong khung 06:00-12:00 giờ VN)
asian_low  = min(Low trong khung 06:00-12:00 giờ VN)

Judas Swing Bullish: giá quét xuống dưới asian_low rồi đảo lên (dự kiến ngày Bullish)
Judas Swing Bearish: giá quét lên trên asian_high rồi đảo xuống (dự kiến ngày Bearish)
```

### Bước 2 — Displacement + FVG

Ngay sau Judas Swing, cần xuất hiện nến (hoặc chuỗi nến) lực đẩy mạnh — thân nến chiếm tỷ trọng lớn so với toàn bộ range nến, đóng cửa dứt khoát theo hướng đảo chiều — và để lại FVG (xem công thức Chương I.2.B). FVG này chính là PD Array dùng cho Bước 3.

### Bước 3 — OTE Entry (Optimal Trade Entry)

**OTE** là vùng Fibonacci retracement 0.618 - 0.790 được kéo từ đáy Swing đến đỉnh Swing (hoặc ngược lại) của đợt displacement vừa hình thành.

```
Fibonacci kéo từ Swing Low → Swing High (cho lệnh BUY):
level_0.618 = Swing_High - (Swing_High - Swing_Low) * 0.618
level_0.790 = Swing_High - (Swing_High - Swing_Low) * 0.790
→ Vùng OTE = [level_0.790, level_0.618]
```

Entry lý tưởng: đặt **BUY LIMIT** tại **CE của FVG** (Chương I.2.B) nếu CE đó nằm trùng bên trong vùng OTE 0.618-0.790. Đây là sự hội tụ giữa 2 công cụ (FVG + Fibonacci) — lý do ICT gọi đây là entry "chuẩn xác" vì hai phương pháp đo độc lập cùng chỉ về một vùng giá.

## 4.4 Quy tắc SL/TP

```
BUY:  SL = Low của nến tạo FVG - buffer nhỏ
      TP = BSL/SSL của phiên Á hoặc Đỉnh/Đáy ngày hôm trước (structural target)

SELL: SL = High của nến tạo FVG + buffer nhỏ
      TP = SSL/BSL tương ứng phía đối diện
```

## 4.5 Điểm mạnh / điểm yếu

**Điểm mạnh:**
- Bộ lọc thời gian loại bỏ phần lớn các pha giá nhiễu ngoài killzone — số lượng setup mỗi ngày giảm mạnh so với SMC/Indicator nhưng chất lượng mỗi setup được xác nhận qua nhiều lớp (thời gian + cấu trúc + Fibonacci).
- Kết hợp FVG + OTE tạo ra một điểm entry hẹp, cụ thể — dễ backtest R:R vì SL luôn sát vùng displacement.

**Điểm yếu cấu trúc:**
- Độ chính xác phụ thuộc hoàn toàn vào việc bóc tách đúng Swing Point để kéo Fibonacci — nếu thuật toán chọn sai Swing Point (ví dụ chọn nhầm Inducement thay vì swing thật), toàn bộ vùng OTE bị lệch và entry sai hoàn toàn dù logic code không có bug.
- Killzone cố định theo giờ nhưng thị trường không phải lúc nào cũng có Judas Swing rõ ràng trong khung giờ đó — những ngày không có displacement đủ mạnh trong killzone, thuật toán cần biết **không giao dịch** (NO_TRADE) thay vì cố ép tìm setup, đây là phần dễ bị lập trình sai (over-fitting để "luôn có tín hiệu" thay vì chấp nhận ngày không có setup).

---

# CHƯƠNG V: PHƯƠNG PHÁP 4 — ULTRA CONFLUENCE MATRIX (HYBRID ĐA LỚP)

## 5.1 Triết lý phương pháp

Đây không phải một phương pháp độc lập mới, mà là **khung ghép tầng (confluence stacking)** của 3 phương pháp trên — mỗi lớp là một điều kiện lọc bắt buộc phải đúng trước khi xét lớp tiếp theo. Nguyên lý: càng nhiều lớp độc lập cùng đồng thuận về một vùng entry, xác suất vùng đó phản ứng đúng theo kỳ vọng càng cao (về mặt logic thống kê — không phải con số cố định).

**Quan trọng:** phần "AI Confidence Score >= 0.90" bằng mô hình ML (XGBoost/TFT) trong tài liệu gốc mà bạn tham khảo trước đó chỉ nên được coi là **lớp lọc thứ 5 tùy chọn**, không phải điều kiện bắt buộc — vì một mô hình ML chỉ đáng tin nếu đã được train, validate (walk-forward), và test out-of-sample trên dữ liệu XAUUSDm thật. Nếu chưa có mô hình đó, 4 lớp đầu (rule-based, không cần ML) đã là một bộ lọc confluence đầy đủ và có thể backtest ngay.

## 5.2 Cấu trúc 5 lớp chi tiết

```
LỚP 1 — HTF NARRATIVE & PREMIUM/DISCOUNT (H4/D1)
  Điều kiện: Giá hiện tại nằm trong Discount Zone (dưới 50% Fibo swing H4/D1)
             → chỉ xét BUY. Ngược lại (Premium) → chỉ xét SELL.
  Input: Swing High/Low H4 hoặc D1 gần nhất (Chương VI.3)
  Output: bias ∈ {DISCOUNT_BUY_ONLY, PREMIUM_SELL_ONLY, NEUTRAL}

LỚP 2 — TIME & KILLZONE WINDOW
  Điều kiện: Thời điểm hiện tại nằm trong London KZ (14:00-17:00 VN)
             hoặc NY KZ (19:30-22:30 VN)
  Input: timestamp nến hiện tại (Chương IX.1)
  Output: bool is_killzone

LỚP 3 — LIQUIDITY SWEEP CONFIRMATION (M15)
  Điều kiện: Nến M15 gần nhất có sweep BSL hoặc SSL hợp lệ
             (wick xuyên qua target, close rút lại trong range)
  Input: BSL/SSL list + nến M15 (Chương VIII.3)
  Output: sweep_direction ∈ {BULLISH_SWEEP, BEARISH_SWEEP, NONE}

LỚP 4 — MSS/CHoCH + DISPLACEMENT + FVG (M5)
  Điều kiện: Nến M5 xác nhận MSS/CHoCH, thân nến chiếm tỷ trọng lớn
             so với ATR, và để lại FVG rõ nét theo đúng hướng LỚP 3
  Input: swing M5 + ATR M5 + FVG list (Chương VIII)
  Output: bool displacement_confirmed, FVG object

LỚP 5 — OTE ENTRY (+ tùy chọn ML confidence)
  Điều kiện: CE của FVG (LỚP 4) trùng vùng OTE Fibonacci 0.618-0.790
             kéo từ swing vừa tạo ở LỚP 4
  Input: FVG.ce + Fibonacci OTE range (Chương IX.2)
  Output: entry_price, sl, tp, confluence_score (đếm số lớp pass)
```

## 5.3 Nguyên tắc ghép tầng cho thuật toán

Điểm mấu chốt kỹ thuật: **các lớp phải được đánh giá tuần tự, không song song** — vì Lớp 1 quyết định hướng (chỉ BUY hoặc chỉ SELL), nên nếu Lớp 3 phát hiện sweep ngược hướng Lớp 1, tín hiệu đó bị loại ngay lập tức thay vì cố "ép" thành setup. Đây là lý do cấu trúc if-chain tuần tự (early-return) phù hợp hơn tính điểm cộng dồn kiểu trọng số — vì một số điều kiện là **bắt buộc** (loại ngay nếu sai hướng), không phải cộng điểm tùy chọn.

```python
def evaluate_ultra_confluence(htf_bias, is_kz, sweep, displacement, ote):
    # Mỗi bước là điều kiện chặn cứng — sai bất kỳ bước nào → NO_TRADE
    if htf_bias == "NEUTRAL":
        return "NO_TRADE", "LAYER1_NO_CLEAR_BIAS"
    if not is_kz:
        return "NO_TRADE", "LAYER2_OUTSIDE_KILLZONE"
    if sweep is None:
        return "NO_TRADE", "LAYER3_NO_SWEEP"
    if (htf_bias == "DISCOUNT_BUY_ONLY" and sweep != "BULLISH_SWEEP") or \
       (htf_bias == "PREMIUM_SELL_ONLY" and sweep != "BEARISH_SWEEP"):
        return "NO_TRADE", "LAYER3_SWEEP_DIRECTION_MISMATCH"
    if not displacement.confirmed:
        return "NO_TRADE", "LAYER4_NO_DISPLACEMENT"
    if not ote.in_zone:
        return "NO_TRADE", "LAYER5_PRICE_NOT_IN_OTE"

    direction = "BUY" if htf_bias == "DISCOUNT_BUY_ONLY" else "SELL"
    return "APPROVED", direction
```

## 5.4 Vì sao Ultra Confluence giảm số lượng tín hiệu mạnh nhất trong 4 phương pháp

Vì mỗi lớp là điều kiện chặn cứng (AND logic, không phải OR), xác suất tất cả 5 điều kiện cùng đúng tại một thời điểm thấp hơn đáng kể so với chỉ xét 1-2 lớp riêng lẻ. Đây là đánh đổi cố ý: số lượng setup/ngày giảm mạnh so với Phương pháp 1-3, đổi lại mỗi setup được xác nhận qua nhiều tầng độc lập (thời gian, cấu trúc HTF, thanh khoản, displacement, Fibonacci). Winrate thật của cách tiếp cận này **chỉ có thể đo bằng backtest** (Chương XII) — không nên giả định trước bất kỳ con số nào, kể cả khi logic mỗi lớp đều đúng, vì hiệu ứng cộng dồn qua backtest thực tế thường khác kỳ vọng lý thuyết (do trượt giá, spread thật, độ trễ khớp lệnh, và các giai đoạn thị trường ngoài mẫu thiết kế).

## 5.5 Bảng so sánh 4 phương pháp (không kèm winrate giả định)

| Tiêu chí | 1. Indicator | 2. SMC | 3. ICT | 4. Ultra Confluence |
|---|---|---|---|---|
| Độ trễ tín hiệu | Cao (lagging) | Trung bình | Thấp (event-based) | Thấp nhất (nhiều lớp lọc) |
| Phụ thuộc thời gian | Không | Không | Bắt buộc (killzone) | Bắt buộc |
| Phụ thuộc cấu trúc HTF | Không | Có (bias H1/H4) | Có (Asian Range) | Có (H4/D1 Premium/Discount) |
| Số điều kiện lọc | 3-4 (độc lập) | 4 bước (tuần tự) | 3 bước (tuần tự + thời gian) | 5 lớp (tuần tự, AND logic) |
| Độ phức tạp code | Thấp | Trung bình | Cao | Cao nhất (kết hợp cả 3) |
| Tần suất setup kỳ vọng | Cao nhất | Trung bình | Thấp | Thấp nhất |
| Cần backtest riêng trước khi live | Có | Có | Có | Bắt buộc, ưu tiên cao nhất |

---

# CHƯƠNG VI: PYTHON PIPELINE — KẾT NỐI MT5, OHLCV, SWING POINTS

## 6.1 Kết nối MT5 và lấy dữ liệu đa khung thời gian

```python
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

SYMBOL = "XAUUSDm"

TIMEFRAME_MAP = {
    "M1":  mt5.TIMEFRAME_M1,
    "M5":  mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "H1":  mt5.TIMEFRAME_H1,
    "H4":  mt5.TIMEFRAME_H4,
}


def connect_mt5(login: int, password: str, server: str) -> bool:
    """Khởi tạo kết nối MT5. Trả về True nếu thành công."""
    if not mt5.initialize(login=login, password=password, server=server):
        print(f"[MT5] initialize() failed, error = {mt5.last_error()}")
        return False
    print(f"[MT5] Connected: {mt5.terminal_info()}")
    return True


def fetch_ohlcv(symbol: str, timeframe_str: str, n_bars: int = 1000) -> pd.DataFrame:
    """
    Lấy n_bars nến gần nhất cho symbol/timeframe chỉ định.
    Trả về DataFrame chuẩn hóa: time, open, high, low, close, tick_volume, spread, real_volume
    """
    tf = TIMEFRAME_MAP[timeframe_str]
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, n_bars)

    if rates is None or len(rates) == 0:
        raise RuntimeError(f"Không lấy được dữ liệu {symbol} {timeframe_str}: {mt5.last_error()}")

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df = df.rename(columns={
        "open": "open", "high": "high", "low": "low", "close": "close"
    })
    df = df[["time", "open", "high", "low", "close", "tick_volume", "spread", "real_volume"]]
    df = df.reset_index(drop=True)
    return df


def fetch_multi_timeframe(symbol: str, n_bars: dict) -> dict:
    """
    Lấy đồng thời nhiều khung thời gian.
    n_bars: dict ví dụ {"H4": 500, "H1": 800, "M15": 1500, "M5": 3000, "M1": 5000}
    Trả về dict {"H4": df, "H1": df, "M15": df, "M5": df, "M1": df}
    """
    result = {}
    for tf_str, count in n_bars.items():
        result[tf_str] = fetch_ohlcv(symbol, tf_str, count)
    return result


# ── Ví dụ sử dụng ──
if __name__ == "__main__":
    if connect_mt5(login=0, password="", server=""):  # điền thông tin thật
        data = fetch_multi_timeframe(SYMBOL, {
            "H4": 500, "H1": 800, "M15": 1500, "M5": 3000, "M1": 5000
        })
        for tf, df in data.items():
            print(f"{tf}: {len(df)} nến, từ {df['time'].iloc[0]} đến {df['time'].iloc[-1]}")
        mt5.shutdown()
```

**Lưu ý khi triển khai thật:**
- `copy_rates_from_pos` lấy theo vị trí (0 = nến hiện tại chưa đóng). Với logic cần nến đã đóng hoàn toàn (đa số detect PD Array yêu cầu điều này), nên loại bỏ dòng cuối (`df.iloc[:-1]`) trước khi đưa vào các hàm detect ở Chương VII-IX, tránh detect nhầm trên nến đang hình thành dở.
- `n_bars` cho H4/H1 nên đủ lớn để bao phủ tối thiểu vài chục swing point gần nhất (500-800 nến là mức hợp lý cho H1); M1 dùng ít hơn vì chủ yếu chỉ cần cho refinement entry cực ngắn hạn, không cần lịch sử dài.

## 6.2 Dựng nến chuẩn hoá (Candle Object) cho xử lý logic

```python
from dataclasses import dataclass


@dataclass
class Candle:
    index: int
    time: pd.Timestamp
    open: float
    high: float
    low: float
    close: float

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open

    @property
    def body_size(self) -> float:
        return abs(self.close - self.open)

    @property
    def range_size(self) -> float:
        return self.high - self.low

    @property
    def body_ratio(self) -> float:
        """Tỷ trọng thân nến / toàn bộ range — dùng đo displacement (Chương IV, VIII)."""
        if self.range_size == 0:
            return 0.0
        return self.body_size / self.range_size

    @property
    def upper_wick(self) -> float:
        return self.high - max(self.open, self.close)

    @property
    def lower_wick(self) -> float:
        return min(self.open, self.close) - self.low


def df_to_candles(df: pd.DataFrame) -> list[Candle]:
    """Chuyển DataFrame OHLCV thành list Candle object để xử lý logic dễ đọc hơn."""
    candles = []
    for i, row in df.iterrows():
        candles.append(Candle(
            index=i, time=row["time"],
            open=row["open"], high=row["high"],
            low=row["low"], close=row["close"]
        ))
    return candles
```

## 6.3 Thuật toán phát hiện Swing High / Swing Low (Fractal)

```python
def find_swing_points(df: pd.DataFrame, window: int = 2) -> pd.DataFrame:
    """
    Đánh dấu Swing High / Swing Low bằng thuật toán Fractal:
    Một điểm là Swing High nếu high[i] cao hơn `window` nến liền trước
    VÀ cao hơn `window` nến liền sau (tương tự cho Swing Low).

    window=2 → Fractal 5 nến chuẩn (2 trái + đỉnh + 2 phải).
    window lớn hơn → lọc bớt swing nhỏ (nhiễu), nhưng phát hiện trễ hơn
    vì phải chờ đủ số nến bên phải để xác nhận.
    """
    df = df.copy()
    df["swing_high"] = False
    df["swing_low"] = False

    highs = df["high"].values
    lows = df["low"].values
    n = len(df)

    for i in range(window, n - window):
        left_h = highs[i - window:i]
        right_h = highs[i + 1:i + window + 1]
        if highs[i] > left_h.max() and highs[i] > right_h.max():
            df.at[i, "swing_high"] = True

        left_l = lows[i - window:i]
        right_l = lows[i + 1:i + window + 1]
        if lows[i] < left_l.min() and lows[i] < right_l.min():
            df.at[i, "swing_low"] = True

    return df


def get_last_swing_points(df: pd.DataFrame, n: int = 5) -> dict:
    """Lấy n Swing High và n Swing Low gần nhất (đã được đánh dấu bởi find_swing_points)."""
    swing_highs = df[df["swing_high"]].tail(n)[["time", "high"]].to_dict("records")
    swing_lows = df[df["swing_low"]].tail(n)[["time", "low"]].to_dict("records")
    return {"swing_highs": swing_highs, "swing_lows": swing_lows}


def classify_trend_structure(df: pd.DataFrame) -> str:
    """
    Phân loại xu hướng dựa trên chuỗi Swing gần nhất:
    HH+HL liên tiếp → uptrend; LH+LL liên tiếp → downtrend; ngược lại → range.
    """
    swings = get_last_swing_points(df, n=3)
    highs = [s["high"] for s in swings["swing_highs"]]
    lows = [s["low"] for s in swings["swing_lows"]]

    if len(highs) < 2 or len(lows) < 2:
        return "INSUFFICIENT_DATA"

    higher_highs = all(highs[i] < highs[i + 1] for i in range(len(highs) - 1))
    higher_lows = all(lows[i] < lows[i + 1] for i in range(len(lows) - 1))
    lower_highs = all(highs[i] > highs[i + 1] for i in range(len(highs) - 1))
    lower_lows = all(lows[i] > lows[i + 1] for i in range(len(lows) - 1))

    if higher_highs and higher_lows:
        return "UPTREND"
    if lower_highs and lower_lows:
        return "DOWNTREND"
    return "RANGE"
```

---

# CHƯƠNG VII: PYTHON PIPELINE — ORDER BLOCK, BREAKER BLOCK, MITIGATION BLOCK

## 7.1 Cấu trúc dữ liệu PD Array thống nhất

```python
from dataclasses import dataclass, field
from enum import Enum


class PDArrayType(Enum):
    ORDER_BLOCK = "OB"
    FVG = "FVG"
    BREAKER_BLOCK = "BREAKER"
    MITIGATION_BLOCK = "MITIGATION"


class PDArrayDirection(Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"


@dataclass
class PDArray:
    type: PDArrayType
    direction: PDArrayDirection
    top: float
    bottom: float
    formed_at_index: int
    formed_at_time: pd.Timestamp
    mitigated: bool = False
    has_fvg_confluence: bool = False
    ce: float | None = None  # chỉ dùng cho FVG

    @property
    def mid(self) -> float:
        return (self.top + self.bottom) / 2

    def contains_price(self, price: float) -> bool:
        return self.bottom <= price <= self.top
```

## 7.2 Phát hiện Order Block hợp lệ

```python
def detect_order_blocks(
    candles: list[Candle],
    swing_df: pd.DataFrame,
    displacement_atr_multiplier: float = 2.0,
    atr_series: pd.Series | None = None,
) -> list[PDArray]:
    """
    Quét toàn bộ chuỗi nến để tìm Order Block hợp lệ theo định nghĩa Chương I.2.A:
    - Nến đối lập cuối cùng trước displacement
    - Displacement phải đóng cửa vượt swing point gần nhất
    - Displacement nên có body_ratio lớn (đo lực đẩy thật, không phải doji)

    atr_series: ATR đã tính sẵn cùng độ dài với candles, dùng để chuẩn hoá
                ngưỡng "displacement mạnh" theo biến động thực tế thay vì
                một số pip cố định (biến động vàng thay đổi theo giai đoạn).
    """
    order_blocks: list[PDArray] = []
    n = len(candles)

    swing_highs_idx = set(swing_df[swing_df["swing_high"]].index)
    swing_lows_idx = set(swing_df[swing_df["swing_low"]].index)

    for i in range(1, n - 1):
        current = candles[i]
        prev = candles[i - 1]

        atr_now = atr_series.iloc[i] if atr_series is not None else None

        # ── Bullish OB: nến giảm (prev) ngay trước nến tăng mạnh (current)
        #    phá vỡ Swing High gần nhất bên trái ──
        if prev.is_bearish and current.is_bullish:
            recent_swing_high = _find_nearest_swing_before(swing_highs_idx, i, candles, "high")
            if recent_swing_high is not None and current.close > recent_swing_high:
                strong_displacement = (
                    current.body_ratio >= 0.6 and
                    (atr_now is None or current.body_size >= displacement_atr_multiplier * atr_now)
                )
                if strong_displacement:
                    order_blocks.append(PDArray(
                        type=PDArrayType.ORDER_BLOCK,
                        direction=PDArrayDirection.BULLISH,
                        top=prev.high,
                        bottom=prev.low,
                        formed_at_index=i - 1,
                        formed_at_time=prev.time,
                    ))

        # ── Bearish OB: nến tăng (prev) ngay trước nến giảm mạnh (current)
        #    phá vỡ Swing Low gần nhất bên trái ──
        if prev.is_bullish and current.is_bearish:
            recent_swing_low = _find_nearest_swing_before(swing_lows_idx, i, candles, "low")
            if recent_swing_low is not None and current.close < recent_swing_low:
                strong_displacement = (
                    current.body_ratio >= 0.6 and
                    (atr_now is None or current.body_size >= displacement_atr_multiplier * atr_now)
                )
                if strong_displacement:
                    order_blocks.append(PDArray(
                        type=PDArrayType.ORDER_BLOCK,
                        direction=PDArrayDirection.BEARISH,
                        top=prev.high,
                        bottom=prev.low,
                        formed_at_index=i - 1,
                        formed_at_time=prev.time,
                    ))

    return order_blocks


def _find_nearest_swing_before(swing_idx_set: set, current_index: int, candles: list[Candle], field_name: str):
    """Tìm giá trị swing point gần nhất TRƯỚC current_index (tránh nhìn tương lai — look-ahead bias)."""
    candidates = [idx for idx in swing_idx_set if idx < current_index]
    if not candidates:
        return None
    nearest_idx = max(candidates)
    return getattr(candles[nearest_idx], field_name)


def mark_ob_mitigated(order_blocks: list[PDArray], candles: list[Candle]) -> None:
    """
    Cập nhật trạng thái mitigated=True nếu giá sau đó đã xuyên qua toàn bộ vùng OB.
    Gọi hàm này sau mỗi lần có nến mới để loại OB đã "chết" khỏi danh sách ứng viên entry.
    """
    for ob in order_blocks:
        if ob.mitigated:
            continue
        for c in candles[ob.formed_at_index + 1:]:
            if ob.direction == PDArrayDirection.BULLISH and c.close < ob.bottom:
                ob.mitigated = True
                break
            if ob.direction == PDArrayDirection.BEARISH and c.close > ob.top:
                ob.mitigated = True
                break
```

## 7.3 Phát hiện Breaker Block và Mitigation Block

```python
def detect_breaker_and_mitigation_blocks(
    order_blocks: list[PDArray], candles: list[Candle]
) -> list[PDArray]:
    """
    Với mỗi OB đã bị mitigated (thất bại), kiểm tra:
    - Nếu thất bại được xác nhận bằng CLOSE vượt qua vùng OB → Breaker Block
    - Nếu chỉ bị xuyên bằng WICK (chưa close qua) → Mitigation Block
    Sau đó vùng OB cũ đổi vai trò (Bullish OB thất bại → Bearish Breaker/Mitigation, và ngược lại)
    theo đúng cơ chế mô tả ở Chương I.2.C và I.2.D.
    """
    results: list[PDArray] = []

    for ob in order_blocks:
        if not ob.mitigated:
            continue

        failure_index = None
        failed_by_close = False

        for idx in range(ob.formed_at_index + 1, len(candles)):
            c = candles[idx]
            if ob.direction == PDArrayDirection.BULLISH:
                wick_breach = c.low < ob.bottom
                close_breach = c.close < ob.bottom
            else:
                wick_breach = c.high > ob.top
                close_breach = c.close > ob.top

            if close_breach:
                failure_index = idx
                failed_by_close = True
                break
            if wick_breach and failure_index is None:
                failure_index = idx
                failed_by_close = False
                # tiếp tục quét — có thể sau đó xuất hiện close breach thật sự

        if failure_index is None:
            continue

        new_direction = (
            PDArrayDirection.BEARISH if ob.direction == PDArrayDirection.BULLISH
            else PDArrayDirection.BULLISH
        )
        new_type = PDArrayType.BREAKER_BLOCK if failed_by_close else PDArrayType.MITIGATION_BLOCK

        results.append(PDArray(
            type=new_type,
            direction=new_direction,
            top=ob.top,
            bottom=ob.bottom,
            formed_at_index=failure_index,
            formed_at_time=candles[failure_index].time,
        ))

    return results
```

---

# CHƯƠNG VIII: PYTHON PIPELINE — FVG, CHoCH/MSS, LIQUIDITY SWEEP

## 8.1 Phát hiện Fair Value Gap (FVG)

```python
def detect_fvg(candles: list[Candle]) -> list[PDArray]:
    """
    Phát hiện FVG theo công thức 3-nến chuẩn (Chương I.2.B).
    i-2, i-1, i là 3 nến liên tiếp; FVG hình thành do nến i-1 (nến giữa)
    di chuyển đủ mạnh khiến nến i-2 và nến i không chồng lấp wick.
    """
    fvg_list: list[PDArray] = []

    for i in range(2, len(candles)):
        c0, c1, c2 = candles[i - 2], candles[i - 1], candles[i]

        # Bullish FVG: low của nến hiện tại (i) > high của nến 2 nến trước (i-2)
        if c2.low > c0.high:
            top, bottom = c2.low, c0.high
            fvg_list.append(PDArray(
                type=PDArrayType.FVG,
                direction=PDArrayDirection.BULLISH,
                top=top, bottom=bottom,
                formed_at_index=i,
                formed_at_time=c2.time,
                ce=(top + bottom) / 2,
            ))

        # Bearish FVG: high của nến hiện tại (i) < low của nến 2 nến trước (i-2)
        if c2.high < c0.low:
            top, bottom = c0.low, c2.high
            fvg_list.append(PDArray(
                type=PDArrayType.FVG,
                direction=PDArrayDirection.BEARISH,
                top=top, bottom=bottom,
                formed_at_index=i,
                formed_at_time=c2.time,
                ce=(top + bottom) / 2,
            ))

    return fvg_list


def link_fvg_to_order_blocks(order_blocks: list[PDArray], fvg_list: list[PDArray], max_gap_bars: int = 3) -> None:
    """
    Gắn cờ has_fvg_confluence=True cho OB nào có FVG hình thành ngay sau đó
    (trong vòng max_gap_bars nến) theo cùng hướng — điều kiện "Valid OB" (Chương I.2.A).
    """
    for ob in order_blocks:
        for fvg in fvg_list:
            same_direction = fvg.direction == ob.direction
            close_in_time = 0 <= (fvg.formed_at_index - ob.formed_at_index) <= max_gap_bars
            if same_direction and close_in_time:
                ob.has_fvg_confluence = True
                break


def get_fvg_fill_state(fvg: PDArray, candles: list[Candle]) -> str:
    """Trả về trạng thái lấp đầy FVG: VIRGIN / PARTIAL / CE_FILLED / FULLY_FILLED (Chương I.2.B)."""
    touched, ce_touched, fully_filled = False, False, False

    for c in candles[fvg.formed_at_index + 1:]:
        if fvg.direction == PDArrayDirection.BULLISH:
            if c.low <= fvg.top:
                touched = True
            if c.low <= fvg.ce:
                ce_touched = True
            if c.low <= fvg.bottom:
                fully_filled = True
        else:
            if c.high >= fvg.bottom:
                touched = True
            if c.high >= fvg.ce:
                ce_touched = True
            if c.high >= fvg.top:
                fully_filled = True

    if fully_filled:
        return "FULLY_FILLED"
    if ce_touched:
        return "CE_FILLED"
    if touched:
        return "PARTIAL"
    return "VIRGIN"
```

## 8.2 Phát hiện CHoCH / MSS

```python
from enum import Enum


class StructureShiftType(Enum):
    CHOCH_BULLISH = "CHOCH_BULLISH"   # đảo chiều từ downtrend sang khả năng uptrend
    CHOCH_BEARISH = "CHOCH_BEARISH"   # đảo chiều từ uptrend sang khả năng downtrend
    MSS_BULLISH = "MSS_BULLISH"       # tiếp diễn nội bộ, cùng hướng bias
    MSS_BEARISH = "MSS_BEARISH"
    NONE = "NONE"


def detect_structure_shift(
    candles: list[Candle],
    swing_df: pd.DataFrame,
    current_index: int,
    htf_bias: str,  # "UPTREND" | "DOWNTREND" | "RANGE", lấy từ classify_trend_structure() ở HTF
) -> StructureShiftType:
    """
    Xác định CHoCH hay MSS tại nến current_index dựa theo:
    - Có đóng cửa vượt swing point gần nhất không (close-based, theo Chương III.3 Bước 3)
    - Hướng phá vỡ có ngược với xu hướng hiện tại (khung đang xét) hay không
      → ngược = CHoCH (khả năng đảo chiều)
      → cùng hướng bias HTF nhưng phá cấu trúc nội bộ = MSS (tiếp diễn)
    """
    current = candles[current_index]

    swing_highs_idx = [idx for idx in swing_df[swing_df["swing_high"]].index if idx < current_index]
    swing_lows_idx = [idx for idx in swing_df[swing_df["swing_low"]].index if idx < current_index]

    if not swing_highs_idx or not swing_lows_idx:
        return StructureShiftType.NONE

    nearest_swing_high = candles[max(swing_highs_idx)].high
    nearest_swing_low = candles[max(swing_lows_idx)].low

    broke_up = current.close > nearest_swing_high
    broke_down = current.close < nearest_swing_low

    if broke_up:
        return StructureShiftType.MSS_BULLISH if htf_bias == "UPTREND" else StructureShiftType.CHOCH_BULLISH
    if broke_down:
        return StructureShiftType.MSS_BEARISH if htf_bias == "DOWNTREND" else StructureShiftType.CHOCH_BEARISH

    return StructureShiftType.NONE
```

## 8.3 Phát hiện Liquidity Sweep (BSL/SSL) và EQH/EQL

```python
def detect_liquidity_sweep(
    candles: list[Candle],
    swing_df: pd.DataFrame,
    current_index: int,
) -> str | None:
    """
    Kiểm tra nến current_index có phải một Liquidity Sweep hợp lệ không
    (định nghĩa Chương I.2.E + III.3 Bước 2): wick xuyên qua target,
    close rút lại vào trong range.
    """
    current = candles[current_index]

    swing_highs_idx = [idx for idx in swing_df[swing_df["swing_high"]].index if idx < current_index]
    swing_lows_idx = [idx for idx in swing_df[swing_df["swing_low"]].index if idx < current_index]

    if swing_highs_idx:
        bsl_target = candles[max(swing_highs_idx)].high
        if current.high > bsl_target and current.close < bsl_target:
            return "BEARISH_SWEEP"  # quét BSL, chuẩn bị đảo xuống

    if swing_lows_idx:
        ssl_target = candles[max(swing_lows_idx)].low
        if current.low < ssl_target and current.close > ssl_target:
            return "BULLISH_SWEEP"  # quét SSL, chuẩn bị đảo lên

    return None


def detect_equal_highs_lows(
    swing_df: pd.DataFrame, candles: list[Candle], tolerance_pct: float = 0.0005
) -> dict:
    """
    Tìm các cặp Equal Highs / Equal Lows (Chương I.2.F): 2 đỉnh (đáy) có sai số
    tương đối nhỏ hơn tolerance_pct (mặc định 0.05%, phù hợp XAUUSD do biến động lớn
    theo giá trị tuyệt đối — nên dùng % thay vì số pip cố định).
    """
    highs = swing_df[swing_df["swing_high"]][["high"]].reset_index()
    lows = swing_df[swing_df["swing_low"]][["low"]].reset_index()

    eqh_pairs, eql_pairs = [], []

    for i in range(len(highs) - 1):
        for j in range(i + 1, len(highs)):
            h1, h2 = highs.iloc[i]["high"], highs.iloc[j]["high"]
            if abs(h1 - h2) / h1 <= tolerance_pct:
                eqh_pairs.append((highs.iloc[i]["index"], highs.iloc[j]["index"], (h1 + h2) / 2))

    for i in range(len(lows) - 1):
        for j in range(i + 1, len(lows)):
            l1, l2 = lows.iloc[i]["low"], lows.iloc[j]["low"]
            if abs(l1 - l2) / l1 <= tolerance_pct:
                eql_pairs.append((lows.iloc[i]["index"], lows.iloc[j]["index"], (l1 + l2) / 2))

    return {"eqh": eqh_pairs, "eql": eql_pairs}
```

---

# CHƯƠNG IX: PYTHON PIPELINE — KILLZONE FILTER, OTE, PREMIUM/DISCOUNT ZONE

## 9.1 Killzone Filter (giờ Việt Nam UTC+7)

```python
from datetime import time as dtime


def get_killzone_status(candle_time: pd.Timestamp, broker_utc_offset_hours: float = 0.0) -> dict:
    """
    Xác định nến hiện tại có nằm trong killzone không (Chương IV.2).
    candle_time: timestamp nến LẤY TỪ MT5 (thường là giờ server broker).
    broker_utc_offset_hours: độ lệch giữa giờ server broker và UTC
                              (thường Exness server = UTC+2 hoặc UTC+3 tuỳ mùa DST —
                              PHẢI xác nhận qua mt5.symbol_info() hoặc terminal_info()
                              thay vì hardcode, vì lệch offset sẽ làm sai toàn bộ killzone).

    Quy đổi: giờ VN (UTC+7) = giờ UTC + 7
    """
    utc_time = candle_time - pd.Timedelta(hours=broker_utc_offset_hours)
    vn_time = utc_time + pd.Timedelta(hours=7)

    t = vn_time.time()

    asian_range = dtime(6, 0) <= t <= dtime(12, 0)
    london_kz = dtime(14, 0) <= t <= dtime(17, 0)
    ny_kz = dtime(19, 30) <= t <= dtime(22, 30)

    return {
        "vn_time": vn_time,
        "is_asian_range": asian_range,
        "is_london_kz": london_kz,
        "is_ny_kz": ny_kz,
        "is_any_killzone": london_kz or ny_kz,
    }


def get_asian_range(df_m15: pd.DataFrame, broker_utc_offset_hours: float = 0.0) -> dict:
    """Lấy High/Low của phiên Á (06:00-12:00 giờ VN) trong ngày hiện tại — dùng cho Judas Swing."""
    df = df_m15.copy()
    df["vn_time"] = df["time"] - pd.Timedelta(hours=broker_utc_offset_hours) + pd.Timedelta(hours=7)
    df["vn_date"] = df["vn_time"].dt.date
    df["vn_hour_float"] = df["vn_time"].dt.hour + df["vn_time"].dt.minute / 60.0

    today = df["vn_date"].iloc[-1]
    mask = (df["vn_date"] == today) & (df["vn_hour_float"] >= 6.0) & (df["vn_hour_float"] <= 12.0)
    session_df = df[mask]

    if session_df.empty:
        return {"asian_high": None, "asian_low": None}

    return {
        "asian_high": session_df["high"].max(),
        "asian_low": session_df["low"].min(),
    }
```

## 9.2 OTE (Optimal Trade Entry) — Fibonacci 0.618-0.790

```python
def calculate_ote_zone(swing_low: float, swing_high: float, direction: str) -> dict:
    """
    Tính vùng OTE (Chương IV.3 Bước 3) từ 1 cặp Swing Low/High vừa hình thành
    sau displacement.
    direction: "BUY" (kéo Fib từ Low→High, tìm entry hồi về) hoặc
               "SELL" (kéo Fib từ High→Low, tìm entry hồi lên)
    """
    range_size = swing_high - swing_low

    if direction == "BUY":
        level_618 = swing_high - range_size * 0.618
        level_790 = swing_high - range_size * 0.790
        return {"zone_top": level_618, "zone_bottom": level_790}
    else:  # SELL
        level_618 = swing_low + range_size * 0.618
        level_790 = swing_low + range_size * 0.790
        return {"zone_top": level_790, "zone_bottom": level_618}


def is_price_in_ote(price: float, ote_zone: dict) -> bool:
    return ote_zone["zone_bottom"] <= price <= ote_zone["zone_top"]


def check_fvg_ote_confluence(fvg: PDArray, ote_zone: dict) -> bool:
    """
    Kiểm tra CE của FVG có trùng vùng OTE không — điều kiện hội tụ ICT quan trọng
    nhất (Chương IV.3 Bước 3): khi 2 công cụ đo độc lập (FVG + Fibonacci) cùng
    chỉ về một vùng giá.
    """
    if fvg.ce is None:
        return False
    return is_price_in_ote(fvg.ce, ote_zone)
```

## 9.3 Premium / Discount Zone (áp dụng lên PD Array — Chương I.4)

```python
def get_premium_discount_zone(swing_low: float, swing_high: float) -> dict:
    """Tính mốc 50% Fibonacci của range HTF — ranh giới Premium/Discount (Chương I.4)."""
    fib_50 = swing_low + (swing_high - swing_low) * 0.5
    return {"swing_low": swing_low, "swing_high": swing_high, "fib_50": fib_50}


def classify_pd_array_zone(pd_array: PDArray, pd_zone: dict) -> str:
    """
    Phân loại một PD Array nằm ở Premium, Discount, hay Mixed (giao cắt mốc 50%)
    so với range HTF — điều kiện LỚP 1 trong Ultra Confluence Matrix (Chương V.2).
    """
    fib_50 = pd_zone["fib_50"]

    if pd_array.top < fib_50:
        return "DISCOUNT"
    if pd_array.bottom > fib_50:
        return "PREMIUM"
    return "MIXED"


def get_htf_bias_from_pd_zone(current_price: float, pd_zone: dict) -> str:
    """
    Xác định bias tổng thể dựa vào vị trí GIÁ HIỆN TẠI so với range HTF —
    dùng làm input cho LỚP 1 Ultra Confluence (Chương V.2).
    """
    fib_50 = pd_zone["fib_50"]
    if current_price < fib_50:
        return "DISCOUNT_BUY_ONLY"
    elif current_price > fib_50:
        return "PREMIUM_SELL_ONLY"
    return "NEUTRAL"
```

---

# CHƯƠNG X: SIGNAL ENGINE — GHÉP TẦNG CONFLUENCE → SINH TÍN HIỆU

## 10.1 Kiến trúc tổng thể Signal Engine

Signal Engine là lớp ghép nối toàn bộ các hàm detect từ Chương VI-IX thành một pipeline duy nhất, chạy tuần tự theo đúng cấu trúc 5 lớp đã mô tả ở Chương V.3. Mỗi lần có nến mới đóng cửa (ví dụ mỗi 1 phút với M1, hoặc theo `OnTimer` polling từ EA), pipeline này được gọi lại để tái đánh giá toàn bộ điều kiện.

```python
from dataclasses import dataclass


@dataclass
class SignalResult:
    status: str          # "APPROVED" | "NO_TRADE"
    direction: str | None  # "BUY" | "SELL" | None
    reason_code: str
    entry_price: float | None = None
    sl: float | None = None
    tp: float | None = None
    layers_passed: list[str] = field(default_factory=list)
    pd_array_used: PDArray | None = None


def run_signal_engine(
    symbol: str,
    mtf_data: dict,           # output của fetch_multi_timeframe()
    broker_utc_offset_hours: float,
    method: str = "ULTRA_CONFLUENCE",  # "INDICATOR" | "SMC" | "ICT" | "ULTRA_CONFLUENCE"
) -> SignalResult:
    """
    Điểm vào chính của Signal Engine. Chọn method để chạy đúng logic
    của 1 trong 4 phương pháp (Chương II-V), mặc định chạy Ultra Confluence
    vì đây là bộ lọc chặt nhất, bao trùm 3 phương pháp còn lại.
    """
    df_h4, df_h1 = mtf_data["H4"].iloc[:-1], mtf_data["H1"].iloc[:-1]  # bỏ nến chưa đóng
    df_m15, df_m5 = mtf_data["M15"].iloc[:-1], mtf_data["M5"].iloc[:-1]
    df_m1 = mtf_data["M1"].iloc[:-1]

    if method == "ULTRA_CONFLUENCE":
        return _run_ultra_confluence(df_h4, df_h1, df_m15, df_m5, df_m1, broker_utc_offset_hours)
    elif method == "ICT":
        return _run_ict_only(df_h1, df_m15, df_m5, broker_utc_offset_hours)
    elif method == "SMC":
        return _run_smc_only(df_h1, df_m15)
    elif method == "INDICATOR":
        return _run_indicator_only(df_m15)
    else:
        raise ValueError(f"Method không hợp lệ: {method}")


def _run_ultra_confluence(df_h4, df_h1, df_m15, df_m5, df_m1, utc_offset) -> SignalResult:
    layers_passed = []

    # ── LỚP 1: HTF Premium/Discount ──
    h4_swing_df = find_swing_points(df_h4, window=2)
    h4_swings = get_last_swing_points(h4_swing_df, n=1)
    if not h4_swings["swing_highs"] or not h4_swings["swing_lows"]:
        return SignalResult("NO_TRADE", None, "LAYER1_INSUFFICIENT_SWING_DATA")

    swing_high_h4 = h4_swings["swing_highs"][-1]["high"]
    swing_low_h4 = h4_swings["swing_lows"][-1]["low"]
    pd_zone = get_premium_discount_zone(swing_low_h4, swing_high_h4)

    current_price = df_m1["close"].iloc[-1]
    htf_bias = get_htf_bias_from_pd_zone(current_price, pd_zone)

    if htf_bias == "NEUTRAL":
        return SignalResult("NO_TRADE", None, "LAYER1_NEUTRAL_ZONE")
    layers_passed.append("LAYER1_PD_ZONE")

    # ── LỚP 2: Killzone ──
    current_time_m1 = df_m1["time"].iloc[-1]
    kz_status = get_killzone_status(current_time_m1, utc_offset)
    if not kz_status["is_any_killzone"]:
        return SignalResult("NO_TRADE", None, "LAYER2_OUTSIDE_KILLZONE")
    layers_passed.append("LAYER2_KILLZONE")

    # ── LỚP 3: Liquidity Sweep tại M15 ──
    m15_swing_df = find_swing_points(df_m15, window=2)
    m15_candles = df_to_candles(df_m15)
    sweep = detect_liquidity_sweep(m15_candles, m15_swing_df, len(m15_candles) - 1)

    expected_sweep = "BULLISH_SWEEP" if htf_bias == "DISCOUNT_BUY_ONLY" else "BEARISH_SWEEP"
    if sweep != expected_sweep:
        return SignalResult("NO_TRADE", None, "LAYER3_NO_MATCHING_SWEEP")
    layers_passed.append("LAYER3_LIQUIDITY_SWEEP")

    # ── LỚP 4: MSS/CHoCH + Displacement + FVG tại M5 ──
    m5_swing_df = find_swing_points(df_m5, window=2)
    m5_candles = df_to_candles(df_m5)
    m5_trend = classify_trend_structure(m5_swing_df)

    shift = detect_structure_shift(m5_candles, m5_swing_df, len(m5_candles) - 1, m5_trend)
    expected_shift = {
        "DISCOUNT_BUY_ONLY": [StructureShiftType.CHOCH_BULLISH, StructureShiftType.MSS_BULLISH],
        "PREMIUM_SELL_ONLY": [StructureShiftType.CHOCH_BEARISH, StructureShiftType.MSS_BEARISH],
    }[htf_bias]

    if shift not in expected_shift:
        return SignalResult("NO_TRADE", None, "LAYER4_NO_STRUCTURE_SHIFT")

    fvg_list = detect_fvg(m5_candles)
    recent_fvg = [f for f in fvg_list if f.formed_at_index >= len(m5_candles) - 5]
    matching_direction = PDArrayDirection.BULLISH if "BULLISH" in shift.value else PDArrayDirection.BEARISH
    valid_fvg = [f for f in recent_fvg if f.direction == matching_direction]

    if not valid_fvg:
        return SignalResult("NO_TRADE", None, "LAYER4_NO_FVG_AFTER_SHIFT")
    layers_passed.append("LAYER4_MSS_DISPLACEMENT_FVG")

    latest_fvg = valid_fvg[-1]

    # ── LỚP 5: OTE Entry ──
    m5_swings = get_last_swing_points(m5_swing_df, n=1)
    if not m5_swings["swing_highs"] or not m5_swings["swing_lows"]:
        return SignalResult("NO_TRADE", None, "LAYER5_INSUFFICIENT_M5_SWING")

    direction = "BUY" if htf_bias == "DISCOUNT_BUY_ONLY" else "SELL"
    ote_zone = calculate_ote_zone(
        m5_swings["swing_lows"][-1]["low"],
        m5_swings["swing_highs"][-1]["high"],
        direction
    )

    if not check_fvg_ote_confluence(latest_fvg, ote_zone):
        return SignalResult("NO_TRADE", None, "LAYER5_FVG_NOT_IN_OTE")
    layers_passed.append("LAYER5_OTE_CONFLUENCE")

    # ── Tất cả 5 lớp pass → APPROVED ──
    entry_price = latest_fvg.ce
    if direction == "BUY":
        sl = m5_candles[latest_fvg.formed_at_index - 2].low - 0.20  # buffer XAUUSD ~0.20
        tp = swing_high_h4  # target cấu trúc HTF gần nhất, không cố định R:R
    else:
        sl = m5_candles[latest_fvg.formed_at_index - 2].high + 0.20
        tp = swing_low_h4

    return SignalResult(
        status="APPROVED",
        direction=direction,
        reason_code="ALL_LAYERS_PASSED",
        entry_price=entry_price,
        sl=sl,
        tp=tp,
        layers_passed=layers_passed,
        pd_array_used=latest_fvg,
    )
```

## 10.2 Ghi chú triển khai quan trọng

- **Look-ahead bias**: mọi hàm detect trong Chương VI-IX đều được viết để chỉ nhìn về **quá khứ** (dùng `< current_index`, không bao giờ `<=` khi tìm swing/OB/FVG tham chiếu). Đây là lỗi phổ biến nhất khi backtest cho kết quả tốt giả tạo nhưng live thất bại — luôn kiểm tra kỹ từng hàm không vô tình dùng dữ liệu tương lai.
- **Nến chưa đóng**: dòng `mtf_data["H4"].iloc[:-1]` trong `run_signal_engine` loại bỏ nến cuối cùng (thường là nến đang hình thành, chưa đóng cửa) — bắt buộc với mọi khung, nếu không loại bỏ, toàn bộ logic dùng `close` (CHoCH, displacement, OB) sẽ dựa trên giá trị chưa ổn định.
- **Hàm `_run_ict_only`, `_run_smc_only`, `_run_indicator_only`** không được viết đầy đủ ở trên để tránh trùng lặp — cấu trúc của chúng tương tự `_run_ultra_confluence` nhưng chỉ chạy các lớp tương ứng theo đúng quy tắc riêng của từng phương pháp (Chương II.4, III.3, IV.3). Khi triển khai thật, nên viết đủ 4 hàm riêng để có thể so sánh backtest giữa các phương pháp trên cùng dữ liệu.

---

# CHƯƠNG XI: RISK GATE & ORDER DISPATCH

## 11.1 Vì sao Risk Gate phải tách riêng khỏi Signal Engine

Signal Engine (Chương X) chỉ trả lời câu hỏi "**có setup hợp lệ về mặt cấu trúc giá không**". Risk Gate trả lời câu hỏi khác: "**có nên gửi lệnh THẬT lúc này không, xét trên tình trạng tài khoản/rủi ro**". Tách 2 lớp này là nguyên tắc kiến trúc quan trọng — một setup có thể đúng 100% về cấu trúc nhưng vẫn bị chặn nếu tài khoản đang chạm daily drawdown, hoặc spread hiện tại quá rộng so với SL dự kiến.

```python
@dataclass
class RiskGateResult:
    approved: bool
    reason_code: str
    volume: float | None = None


def evaluate_risk_gate(
    signal: SignalResult,
    account_balance: float,
    account_equity: float,
    current_spread_points: float,
    open_positions_count: int,
    daily_pnl_pct: float,
    config: dict,
) -> RiskGateResult:
    """
    Risk Gate độc lập — kiểm tra tuần tự, chặn cứng như Ultra Confluence Layers.
    config nên chứa: max_spread_points, max_daily_loss_pct, max_open_positions,
    risk_pct_per_trade, min_free_margin.
    """
    if signal.status != "APPROVED":
        return RiskGateResult(False, "SIGNAL_NOT_APPROVED")

    if account_equity <= 0:
        return RiskGateResult(False, "INVALID_EQUITY")

    if daily_pnl_pct <= -abs(config["max_daily_loss_pct"]):
        return RiskGateResult(False, "DAILY_LOSS_LIMIT_HIT")

    if open_positions_count >= config["max_open_positions"]:
        return RiskGateResult(False, "MAX_POSITIONS_REACHED")

    if current_spread_points > config["max_spread_points"]:
        return RiskGateResult(False, "SPREAD_TOO_WIDE")

    sl_distance_points = abs(signal.entry_price - signal.sl) * 1000  # XAUUSD: 1 point = $1/lot theo Chương 1.2 tài liệu gốc
    if sl_distance_points <= 0:
        return RiskGateResult(False, "INVALID_SL_DISTANCE")

    risk_amount = account_balance * config["risk_pct_per_trade"]
    tick_value = 1.0  # XAUUSDm: 1.0 lot = $1.00/point — XÁC NHẬN LẠI qua mt5.symbol_info() thay vì hardcode
    volume = risk_amount / (sl_distance_points * tick_value)
    volume = round(volume, 2)

    if volume < config.get("min_volume", 0.01):
        return RiskGateResult(False, "VOLUME_BELOW_MINIMUM")
    if volume > config.get("max_volume", 5.0):
        volume = config["max_volume"]  # cap thay vì reject — tuỳ chính sách

    return RiskGateResult(True, "APPROVED", volume=volume)
```

## 11.2 Order Dispatch — mẫu kết nối gửi lệnh (Command Protocol, không gọi order_send trực tiếp)

Dựa theo kiến trúc trong `System Analysis Report` bạn đã cung cấp trước đó — nơi các route gọi `mt5.order_send()` trực tiếp từ Python bị đánh dấu là **VIOLATION nghiêm trọng** — pipeline dưới đây tuân theo đúng nguyên tắc: Python chỉ **tạo command** vào hàng đợi, còn EA (MQL5) là bên duy nhất thực thi lệnh qua `CTrade`.

```python
import sqlite3
import uuid
import json
from datetime import datetime, timedelta


def create_execution_command(
    db_path: str,
    signal: SignalResult,
    risk: RiskGateResult,
    symbol: str,
    magic: int,
    ttl_seconds: int = 10,
) -> str:
    """
    Ghi command vào bảng execution_commands (SQLite) — KHÔNG gọi order_send trực tiếp.
    EA sẽ tự claim command này qua endpoint /api/v1/bridge/commands/claim
    và thực thi bằng CTrade (đúng luồng đã mô tả trong tài liệu kiến trúc gốc).
    """
    command_id = str(uuid.uuid4())
    idempotency_key = f"{symbol}_{signal.direction}_{datetime.utcnow().isoformat()}"
    now = datetime.utcnow()
    expires_at = now + timedelta(seconds=ttl_seconds)

    conn = sqlite3.connect(db_path)
    conn.execute("""
        INSERT INTO execution_commands (
            command_id, idempotency_key, action, symbol, magic,
            volume, stop_loss, take_profit, reason, state,
            created_at, expires_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, ?)
    """, (
        command_id, idempotency_key, signal.direction, symbol, magic,
        risk.volume, signal.sl, signal.tp,
        json.dumps({"layers_passed": signal.layers_passed, "reason": signal.reason_code}),
        now.isoformat(), expires_at.isoformat()
    ))
    conn.commit()
    conn.close()

    return command_id


def signal_to_order_pipeline(
    symbol: str,
    mtf_data: dict,
    account_state: dict,
    config: dict,
    db_path: str,
    utc_offset: float,
    method: str = "ULTRA_CONFLUENCE",
) -> dict:
    """
    Hàm tổng hợp toàn bộ pipeline: detect → signal → risk gate → dispatch.
    Gọi hàm này mỗi khi có nến mới đóng (polling loop bên ngoài, ví dụ mỗi 60s cho M1).
    """
    signal = run_signal_engine(symbol, mtf_data, utc_offset, method=method)

    if signal.status != "APPROVED":
        return {"status": "NO_TRADE", "reason": signal.reason_code}

    risk = evaluate_risk_gate(
        signal=signal,
        account_balance=account_state["balance"],
        account_equity=account_state["equity"],
        current_spread_points=account_state["spread_points"],
        open_positions_count=account_state["open_positions_count"],
        daily_pnl_pct=account_state["daily_pnl_pct"],
        config=config,
    )

    if not risk.approved:
        return {"status": "REJECTED", "reason": risk.reason_code, "signal_layers": signal.layers_passed}

    command_id = create_execution_command(
        db_path=db_path, signal=signal, risk=risk,
        symbol=symbol, magic=config["magic_number"],
    )

    return {
        "status": "COMMAND_CREATED",
        "command_id": command_id,
        "direction": signal.direction,
        "volume": risk.volume,
        "entry": signal.entry_price,
        "sl": signal.sl,
        "tp": signal.tp,
    }
```

## 11.3 Nguyên tắc bắt buộc khi nối vào EA thật

1. **Không bao giờ gọi `mt5.order_send()` trực tiếp từ script Python này** — chỉ ghi vào `execution_commands`. Việc này giữ đúng ranh giới trách nhiệm: Python = phân tích/quyết định, MQL5 EA = validate lần cuối + thực thi qua broker.
2. **EA phải validate lại độc lập** trước khi gọi CTrade — không tin tưởng tuyệt đối command từ Python (kiểm tra spread hiện tại, STOPS_LEVEL, trạng thái tài khoản demo/live) — đúng như mô hình 3 bước đã có trong bối cảnh dự án của bạn (StrictHedgeZone, SamGemDCA).
3. **Idempotency key** bắt buộc để tránh gửi trùng lệnh nếu Python retry hoặc polling loop chạy chồng lấp.
4. **TTL command ngắn (5-15s)** — vì tín hiệu ICT/SMC dựa trên vùng giá cụ thể (OTE, CE của FVG), nếu EA claim quá trễ, giá có thể đã đi qua vùng entry, lúc đó nên để command tự EXPIRE thay vì ép khớp giá kém.

---

# CHƯƠNG XII: KHUNG BACKTEST ĐỂ ĐO WINRATE THẬT

## 12.1 Vì sao chương này bắt buộc phải có trước khi live

Toàn bộ Chương II-V mô tả **logic** của 4 phương pháp — không có con số winrate nào được khẳng định trước, vì lý do đơn giản: không ai (kể cả tài liệu gốc bạn tham khảo) có thể biết winrate thật của một phương pháp mà chưa chạy qua dữ liệu lịch sử thật. Chương này cung cấp khung backtest tối thiểu để bạn tự đo trên dữ liệu XAUUSDm của chính bạn.

## 12.2 Vòng lặp backtest walk-forward (tránh look-ahead bias)

```python
@dataclass
class TradeResult:
    entry_time: pd.Timestamp
    direction: str
    entry_price: float
    sl: float
    tp: float
    exit_price: float | None = None
    exit_time: pd.Timestamp | None = None
    outcome: str | None = None  # "TP_HIT" | "SL_HIT" | "OPEN_AT_END"
    r_multiple: float | None = None


def backtest_signal_engine(
    df_h4_full: pd.DataFrame, df_h1_full: pd.DataFrame,
    df_m15_full: pd.DataFrame, df_m5_full: pd.DataFrame, df_m1_full: pd.DataFrame,
    utc_offset: float,
    method: str = "ULTRA_CONFLUENCE",
    start_index: int = 500,  # đủ dữ liệu lịch sử để tính swing/OB trước khi bắt đầu backtest
) -> list[TradeResult]:
    """
    Backtest walk-forward: tại mỗi mốc thời gian M1, CHỈ dùng dữ liệu
    từ quá khứ đến thời điểm đó (mô phỏng đúng những gì hệ thống live sẽ thấy),
    tuyệt đối không cho Signal Engine nhìn thấy nến tương lai.
    """
    trades: list[TradeResult] = []
    open_trade: TradeResult | None = None

    for i in range(start_index, len(df_m1_full)):
        current_time = df_m1_full["time"].iloc[i]

        # Cắt dữ liệu tại đúng mốc thời gian hiện tại — mô phỏng "chưa biết tương lai"
        m1_slice = df_m1_full.iloc[:i + 1]
        h4_slice = df_h4_full[df_h4_full["time"] <= current_time]
        h1_slice = df_h1_full[df_h1_full["time"] <= current_time]
        m15_slice = df_m15_full[df_m15_full["time"] <= current_time]
        m5_slice = df_m5_full[df_m5_full["time"] <= current_time]

        if len(h4_slice) < 50 or len(m5_slice) < 50:
            continue

        # ── Nếu đang có lệnh mở, kiểm tra SL/TP trước ──
        if open_trade is not None:
            current_candle = df_m1_full.iloc[i]
            hit_sl = (
                (open_trade.direction == "BUY" and current_candle["low"] <= open_trade.sl) or
                (open_trade.direction == "SELL" and current_candle["high"] >= open_trade.sl)
            )
            hit_tp = (
                (open_trade.direction == "BUY" and current_candle["high"] >= open_trade.tp) or
                (open_trade.direction == "SELL" and current_candle["low"] <= open_trade.tp)
            )

            if hit_sl:
                open_trade.exit_price = open_trade.sl
                open_trade.exit_time = current_time
                open_trade.outcome = "SL_HIT"
                open_trade.r_multiple = -1.0
                trades.append(open_trade)
                open_trade = None
                continue
            if hit_tp:
                risk = abs(open_trade.entry_price - open_trade.sl)
                reward = abs(open_trade.tp - open_trade.entry_price)
                open_trade.exit_price = open_trade.tp
                open_trade.exit_time = current_time
                open_trade.outcome = "TP_HIT"
                open_trade.r_multiple = reward / risk if risk > 0 else 0
                trades.append(open_trade)
                open_trade = None
                continue
            continue  # đang có lệnh mở, không tìm tín hiệu mới

        # ── Không có lệnh mở, chạy Signal Engine tìm setup mới ──
        mtf_slice = {"H4": h4_slice, "H1": h1_slice, "M15": m15_slice, "M5": m5_slice, "M1": m1_slice}
        signal = run_signal_engine("XAUUSDm", mtf_slice, utc_offset, method=method)

        if signal.status == "APPROVED":
            open_trade = TradeResult(
                entry_time=current_time, direction=signal.direction,
                entry_price=signal.entry_price, sl=signal.sl, tp=signal.tp,
            )

    return trades


def summarize_backtest(trades: list[TradeResult]) -> dict:
    """Tổng hợp kết quả backtest — con số winrate THẬT, tính từ trades đã chạy, không giả định."""
    closed_trades = [t for t in trades if t.outcome in ("TP_HIT", "SL_HIT")]
    if not closed_trades:
        return {"total_trades": 0, "winrate": None, "message": "Không có lệnh nào khớp trong giai đoạn backtest"}

    wins = [t for t in closed_trades if t.outcome == "TP_HIT"]
    losses = [t for t in closed_trades if t.outcome == "SL_HIT"]

    winrate = len(wins) / len(closed_trades) * 100
    avg_r_win = np.mean([t.r_multiple for t in wins]) if wins else 0
    total_r = sum(t.r_multiple for t in closed_trades)

    return {
        "total_trades": len(closed_trades),
        "wins": len(wins),
        "losses": len(losses),
        "winrate_pct": round(winrate, 2),
        "avg_r_multiple_on_wins": round(avg_r_win, 2),
        "total_r_multiple": round(total_r, 2),
        "expectancy_per_trade_R": round(total_r / len(closed_trades), 3),
    }


# ── Ví dụ chạy backtest so sánh cả 4 phương pháp trên cùng dữ liệu ──
if __name__ == "__main__":
    # Giả định đã có data = fetch_multi_timeframe(...) với đủ lịch sử (khuyến nghị tối thiểu
    # vài nghìn nến H1 tương đương 1-2 năm để bao phủ nhiều giai đoạn thị trường khác nhau)
    for method in ["INDICATOR", "SMC", "ICT", "ULTRA_CONFLUENCE"]:
        trades = backtest_signal_engine(
            data["H4"], data["H1"], data["M15"], data["M5"], data["M1"],
            utc_offset=2.0,  # XÁC NHẬN LẠI offset server thật của bạn, đừng hardcode
            method=method,
        )
        summary = summarize_backtest(trades)
        print(f"\n=== {method} ===")
        print(summary)
```

## 12.3 Các sai lệch (bias) cần kiểm tra trước khi tin kết quả backtest

| Loại bias | Mô tả | Cách kiểm tra |
|---|---|---|
| Look-ahead bias | Code vô tình dùng dữ liệu tương lai (đã kiểm soát bằng walk-forward slice ở trên, nhưng cần double-check từng hàm detect) | Chạy backtest 2 lần: một lần bình thường, một lần cố tình dịch lùi 1 nến toàn bộ input — nếu kết quả thay đổi bất thường, có khả năng đang leak tương lai |
| Overfitting tham số | Tinh chỉnh `displacement_atr_multiplier`, `tolerance_pct`, `window` quá khớp với 1 giai đoạn dữ liệu cụ thể | Chia dữ liệu thành in-sample (70%) / out-of-sample (30%), backtest riêng từng phần, so sánh winrate 2 phần |
| Spread/slippage không tính | Backtest trên ở trên dùng giá lý tưởng (`entry_price` = CE của FVG), thực tế lệnh Limit có thể không khớp đúng giá đó hoặc bị trượt | Thêm buffer spread trung bình vào entry_price khi backtest, hoặc mô phỏng bằng lệnh Limit chỉ khớp nếu giá thật sự chạm |
| Số lượng mẫu quá nhỏ | Ultra Confluence có thể chỉ cho ra vài chục lệnh trên 1-2 năm dữ liệu — không đủ ý nghĩa thống kê | Cần tối thiểu ~100 lệnh đã đóng trước khi coi winrate là có ý nghĩa tham khảo (không phải con số tuyệt đối, chỉ là ngưỡng thống kê tối thiểu thường dùng) |

## 12.4 Quy trình khuyến nghị trước khi kết nối vào lệnh thật

```
1. Backtest cả 4 phương pháp trên tối thiểu 1-2 năm dữ liệu H1/M15 XAUUSDm
2. So sánh winrate, expectancy (R multiple trung bình/lệnh), max drawdown của mỗi phương pháp
3. Chọn phương pháp (hoặc kết hợp) có expectancy dương ổn định qua cả in-sample và out-of-sample
4. Chạy DEMO account tối thiểu vài tuần với Signal Engine + Risk Gate + Order Dispatch
   (Chương X-XI) để kiểm tra độ trễ thật giữa signal và khớp lệnh qua EA
5. Chỉ chuyển sang LIVE sau khi demo cho kết quả nhất quán với backtest
   (nếu lệch nhiều → có bias chưa phát hiện trong bước backtest)
```

## 12.5 Các compoment cuuar các phương pháp trade


- **Price Action:**
Trend, Swing, HH, HL, LH, LL, Support Resistance, Trendline, Channel, Range, Breakout, Pullback, Retest, Fake Breakout, Pin Bar, Engulfing, Inside Bar, Outside Bar, Doji, Morning Star, Evening Star, Hammer, Shooting Star, Tweezer Top, Tweezer Bottom, Marubozu, Three White Soldiers, Three Black Crows

- **Smart Money Concepts (SMC):**
Market Structure, BOS, CHoCH, MSS, Liquidity, Liquidity Sweep, Equal Highs, Equal Lows, Internal Liquidity, External Liquidity, Order Block, Breaker Block, Mitigation Block, Rejection Block, FVG, IFVG, Imbalance, Premium, Discount, Equilibrium, Dealing Range, Inducement, Stop Hunt, Supply/Demand, Volume Imbalance, Liquidity Void

- **ICT (Inner Circle Trader):**
BOS, CHoCH, MSS, OB, FVG, IFVG, BPR, PD Array, OTE, Fibonacci 62–79%, Premium/Discount, Dealing Range, Dealing Curve, Liquidity Pool, Liquidity Void, Turtle Soup, Judas Swing, SMT Divergence, AMD, PO3 (Power of Three), Kill Zone, Silver Bullet, Unicorn Model, Session High/Low, Previous Day High/Low (PDH/PDL), Weekly High/Low, Monthly High/Low

- **Sniper:**
Trend Following, EMA 9/21 Crossover, EMA Ribbon, VWAP, ADX, RSI, MACD, Momentum Confirmation, Volume Confirmation, Breakout, Breakout Confirmation, Pullback, Retest, Support/Resistance Confluence, Dynamic Support/Resistance, Supply/Demand Zone, Market Structure Confirmation, BOS Confirmation, CHoCH Confirmation, Liquidity Sweep, False Breakout, Entry Zone, Precision Entry, Stop Loss Placement, Take Profit Placement, Risk/Reward Ratio, Multi-Timeframe Confirmation, Session Filter, Volatility Filter, Spread Filter, News Filter, Trade Confirmation, Buy Setup, Sell Setup, Entry Signal, Exit Signal, Trailing Stop, Break-Even, Partial Take Profit, Trade Management, Confluence Score
---

## TỔNG KẾT

Tài liệu này cung cấp:
- **Kiến thức đầy đủ về PD Arrays** (Chương I): OB, FVG, Breaker Block, Mitigation Block, Liquidity Pool, EQH/EQL, Inducement — định nghĩa, công thức, cách phân biệt.
- **4 phương pháp trading chi tiết** (Chương II-V): Indicator-Based, SMC, ICT, Ultra Confluence — quy tắc vào/ra lệnh, công thức SL/TP, điểm mạnh/yếu khách quan.
- **Pipeline Python đầy đủ** (Chương VI-XI): kết nối MT5 đa khung thời gian (M1/M5/M15/H1/H4) → dựng nến → swing points → detect toàn bộ PD Arrays → Signal Engine ghép tầng → Risk Gate → Order Dispatch qua Command Protocol (không gọi `order_send` trực tiếp, tuân theo đúng kiến trúc an toàn).
- **Khung backtest** (Chương XII) để tự đo winrate thật trên dữ liệu của bạn, thay vì tin vào con số giả định.

Toàn bộ code trong tài liệu là **khung sườn logic đã đúng theo định nghĩa kỹ thuật**, nhưng cần: (1) test kỹ từng hàm detect trên vài trường hợp đã biết trước kết quả bằng mắt, (2) chạy backtest đủ dữ liệu trước khi tin tưởng, (3) validate kỹ offset giờ server broker thật trước khi dùng killzone filter — vì đây là điểm dễ sai nhất khi hardcode.




## Tuyên bố rủi ro

Giao dịch tài chính có rủi ro cao và có thể mất toàn bộ vốn. Phần mềm này phục vụ mục tiêu kỹ thuật/nghiên cứu; người vận hành chịu trách nhiệm độc lập về cấu hình, tuân thủ quy định, quản trị rủi ro và việc sử dụng bất kỳ broker account nào.

## Bản quyền 

Copyright (c) 2026 QTusdev — All rights reserved.

---

**Sử dụng hợp pháp**

- Chỉ dùng cho mục đích nghiên cứu, backtesting, giao dịch cá nhân.
- Nghiêm cấm sao chép toàn bộ hoặc một phần tài liệu/code để bán, phân phối thương mại, hoặc sử dụng trong sản phẩm thương mại khác mà không có sự đồng ý bằng văn bản từ tác giả.



