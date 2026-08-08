# QuantAI - Hướng Dẫn Vận Hành (Operation Guide)

## 1. Yêu Cầu Hệ Thống

| Thành phần | Yêu cầu |
|------------|---------|
| OS | Windows 10/11 hoặc Windows Server (VPS) |
| Python | 3.11+ |
| Node.js | 18+ (cho web dashboard) |
| MetaTrader 5 | Bản mới nhất, có hỗ trợ WebRequest tới localhost |
| Broker | Tài khoản DEMO trước (khuyến nghị Exness hoặc broker hỗ trợ XAUUSDm) |
| Internet | Ổn định cho AI API + broker |

## 2. Cài Đặt

### 2.1. Backend (FastAPI)

```bash
cd dashboard
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2.2. Cấu hình môi trường

```bash
copy .env.example .env
# Sửa .env: điền ADMIN_LOGIN/PASSWORD, token bridge, MT5 login (demo), Telegram (tùy chọn)
```

Các biến quan trọng:
- `ADMIN_LOGIN` / `ADMIN_PASSWORD`: đăng nhập UI.
- `QUANTAI_BRIDGE_TOKEN`: token xác thực EA - **tự tạo ngẫu nhiên, không commit lên Git**.
- `MT5_LOGIN/PASSWORD/SERVER/PATH`: thông tin tài khoản MT5.
- `QUANTAI_EXECUTION_MODE=DEMO` mặc định; **KHÔNG đổi LIVE khi chưa sẵn sàng**.
- `ATE_BACKEND_URL`: nếu chạy local để `http://127.0.0.1:8005`.
- AI: giữ mặc định `OPENCODE_BASE_URL` + `QUANTAI_AI_MODEL=deepseek-v4-flash-free` để chạy free; thêm key Gemini/OpenAI nếu muốn tăng cường.

### 2.3. Frontend (Next.js)

```bash
cd web
npm install
npm run dev       # phát triển - http://localhost:3000
npm run build && npm run start   # production
```

### 2.4. EA (MetaTrader 5)

1. Copy `MQL5/Experts/tradeAI/QuantAI_XAUUSD.mq5` vào `MQL5/Experts/` của MT5 (hoặc thư mục dữ liệu MT5).
2. Compile trong MetaEditor.
3. Trong MT5: Tools -> Options -> Expert Advisors -> **Allow WebRequest** và thêm `http://127.0.0.1:8005` (hoặc URL backend) vào danh sách trắng.
4. Kéo EA vào chart XAUUSDm, nhập input: `InpSymbol=XAUUSDm`, `InpMagicNumber=888999`, `InpExecutorId` (bất kỳ), `InpBridgeURL` = backend, `InpBridgeToken` = QUANTAI_BRIDGE_TOKEN.
5. Bật `InpExecutionEnabled=true` (chỉ sau khi xác nhận môi trường demo).

## 3. Trình Tự Khởi Động An Toàn (Checklist)

1. [ ] Khởi động backend `python server.py` - chờ log "Ready".
2. [ ] Mở dashboard `http://localhost:3000`, đăng nhập admin.
3. [ ] Kiểm tra `Control Center` -> status cho thấy MT5 connected (nếu MT5 đang chạy EA).
4. [ ] Gắn EA vào chart XAUUSDm; theo dõi telemetry xuất hiện.
5. [ ] Bật `AI Auto Loop` để hệ thống bắt đầu vòng lặp phân tích.
6. [ ] Đặt mode `DEMO` + `demo_armed=true` (chưa bật LIVE).
7. [ ] Theo dõi ít nhất 1 phiên giao dịch đầy đủ trước khi cân nhắc LIVE.

## 4. Vận Hành Hằng Ngày

- **Theo dõi**: Dashboard -> Telemetry (balance, equity, margin), Positions, Logs.
- **Kiểm tra**: EA heartbeat không `STALE` (>10s là cảnh báo).
- **Xem AI**: tab AI Intelligence Matrix để biết confluence score.
- **Tin tức**: tab Economic Calendar - hệ thống tự khóa lệnh trước tin đỏ.
- **KPI**: `dashboard/performance.py` tính Win Rate, PF, Max DD, Recovery Factor (xem qua UI).

## 5. Xử Lý Sự Cố (Troubleshooting)

### 5.1. "Không thể kết nối API Backend (port 8005)"
- Kiểm tra backend đang chạy `python server.py`.
- Kiểm tra `ATE_BACKEND_URL` không chứa `/api/v1` và không trỏ tới domain vercel.app.
- Kiểm tra firewall cho phép cổng 8005.

### 5.2. EA không nhận lệnh
- Kiểm tra `InpBridgeURL/InpBridgeToken` khớp.
- Kiểm tra EA có trong danh sách WebRequest whitelist.
- Kiểm tra `InpExecutionEnabled=true`.
- Xem log EA (Experts tab) - sẽ ghi rõ lý do guard fail.

### 5.3. AI lỗi liên tục
- Xem log JSON: nếu 429/400/401 cho từng provider -> hệ thống tự failover; nếu tất cả lỗi, kiểm tra mạng/key.
- Nếu dùng Zen Free: đảm bảo User-Agent trình duyệt (không dùng Python-urllib).

### 5.4. Lệnh bị REJECTED
- Xem `reason` trong command: RiskGate từ chối vì spread/equity/drawdown/vị thế tối đa.
- Xem log EA: guard fail cụ thể.

### 5.5. Dashboard không cập nhật telemetry
- Kiểm tra WS connection (`/ws/stream`), reconnect backoff tự động.
- Kiểm tra EA heartbeat còn sống.

## 6. Triển Khai Production (Tùy Chọn)

- Cloudlocal nginx + Vercel: xem `Cloudlocal/CLOUDLOCAL_STANDARD.md`.
- VPS Windows: cài đặt tương tự local; đảm bảo latency < 15ms (backend + MT5 cùng máy).
- Bảo mật: đổi token mặc định, giới hạn CORS, dùng HTTPS qua cloudlocal nginx.

## 7. Sao Lưu & Bảo Mật

- Backup `dashboard/quantai_commands.sqlite3` định kỳ (sổ cái giao dịch).
- Backup `dashboard/user_control_config.json` (cấu hình vận hành).
- Backup `.env` tại nơi an toàn (KHÔNG commit lên Git).
- Xoay vòng token bridge định kỳ.

---

*Tài liệu thuộc dự án QuantAI - Nguyễn Quang Tú (QTusdev) | MIT License.*