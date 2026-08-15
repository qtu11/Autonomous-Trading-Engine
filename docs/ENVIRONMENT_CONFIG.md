# 🌐 ENVIRONMENT CONFIG — Kiến trúc triển khai chuẩn (CANONICAL)

> ⚠️ **Tài liệu này phản chiếu `ENVIRONMENT_CONFIG.md` (gốc) — nguồn duy nhất.**
> Mọi thay đổi port/URL/logic triển khai phải sửa file gốc và đồng bộ lại file này
> (và các template `.env.example` / `.env.template`).
## Kiến trúc (1 đường dữ liệu duy nhất)

```
  MT5 (Windows, máy nhà / VNPT)                Browser (mọi nơi)
  ┌───────────────────────────┐                 ┌──────────────┐
  │ EA (ATE_XAUUSD.mq5)       │                 │  Vercel Web  │
  │ • push nến THẬT (copy_rates)│                 │  (Next.js)   │
  │ • push telemetry bid/ask  │                 └──────┬───────┘
  │ • claim + execute lệnh    │                        │ /api/* (serverless proxy)
  └────────────┬──────────────┘                        ▼
               │ https://autonomous-trading-engine.vercel.app/api/v1/*
               ▼                       ┌─────────────────────────────────┐
  ┌─────────────────────┐              │  VERCEL (rewrite /api/v1/*)     │
  │  python-bridge:8007  │◄────────────┤  env ATE_BACKEND_URL =          │
  │  (chạy native trên   │              │  http://<VNPT_PUBLIC_IP>:8848  │
  │   Windows nối MT5)   │              └────────────────┬────────────────┘
  └──────────┬───────────┘                               │
             │ http://localhost:8007 (server.py gọi)     ▼
  ┌──────────▼───────────┐            ┌───────────────────────────────────┐
  │  FastAPI :8005       │◄───────────┤  HOME SERVER (IP VNPT)            │
  │  (server.py)         │            │  nginx :80/:8848                  │
  │  • /api/* dashboard  │            │    /api/*  → fastapi:8005        │
  │  • /api/v1/* EA      │            │    /       → nextjs:3000         │
  └──────────────────────┘            └───────────────────────────────────┘
```

**Nguyên tắc dữ liệu THẬT (đã sửa lỗi):**
1. EA trong MT5 đẩy nến thật qua `POST /api/v1/bridge/candles` → server lưu `_market_cache`
   (trước đây model yêu cầu `executor_id` bắt buộc → 422 → toàn bộ dữ liệu rơi vào stub giả).
2. `fetch_real_candles` đọc theo thứ tự: **EA push → python-bridge `/api/v1/market/candles`
   (copy_rates thật) → stub** (chỉ khi cả hai chết, và `data_status` báo `STUB`).
3. Bid/ask thật: từ **telemetry EA** → python-bridge `/api/v1/market/tick` → stub.
4. `execution_mode=LIVE`: fail-closed — server **không bao giờ giả lập** lệnh/dữ liệu,
   mọi lệnh đi qua EA thật; `DEMO`: server giả lập để chạy thử không cần MT5.

## Cổng & dịch vụ

| Service | Cổng | Môi trường chạy | Ghi chú |
|---------|------|-----------------|---------|
| FastAPI backend (server.py) | 8005 | Windows native hoặc Docker | `ATE_DASHBOARD_PORT` |
| python-bridge (MT5) | 8007 | **Windows native** (cần MetaTrader5 + terminal MT5) | `BRIDGE_URL` của server |
| AI Engine | 8006 | Docker (tùy chọn) | `AI_ENGINE_URL` |
| Freebuff2API (LLM proxy) | 8080 | Docker (Cloudlocal) | `FREEBUFF_LLM_URL` |
| Redis | 6379 | Docker | `REDIS_HOST/PORT` |
| Next.js frontend | 3000 | Docker/Vercel | `ATE_BACKEND_URL` |
| Postgres (Cloudlocal) | 5432 | Docker | `POSTGRES_*` |
| nginx (home server) | 80, **8848** | Docker | 8848 = public (80/443 bị modem VNPT chiếm) |

> **Vì sao bridge phải chạy native trên Windows?** Package `MetaTrader5` chỉ hoạt
> động trên Windows có cài MT5. Container Linux **không** nối được MT5. Trên máy
> Windows cài MT5, bridge là nguồn nến đa khung giờ (M5/M15/H1/D1) cho dashboard;
> EA là nguồn nến chính của chart đang xem.

## Bản đồ file `.env` (file nào cho thành phần nào)

| File | Thành phần đọc | Git? | Ghi chú |
|------|----------------|------|---------|
| `.env` (root) | Tham chiếu chính / docker-compose | ⛔ ignored | Giá trị thật, không commit |
| `.env.example` (root) | Template | ✅ tracked | Bản chuẩn, placeholder |
| `dashboard/.env` | `server.py` (chạy trong thư mục dashboard) | ⛔ ignored | Đầy đủ biến backend |
| `dashboard/.env.example` | Template backend | ✅ tracked | |
| `web/.env` | Next.js build/dev | ⛔ ignored | URL backend + Firebase + JWT |
| `web/.env.local` | Next.js **dev** (ưu tiên cao hơn .env) | ⛔ ignored | ⚠️ Không để giá trị rỗng (ghi đè .env) |
| `web/.env.production` | Next.js production build | ⛔ ignored | |
| `Cloudlocal/.env` | docker compose (fastapi/nginx/bridge) | ⛔ ignored | |
| `Cloudlocal/.env.template` | Template Cloudlocal | ✅ tracked | |

**Thứ tự ưu tiên của Next.js**: `.env.local` > `.env.production` > `.env`.
⚠️ **Bug thực tế đã gặp**: `web/.env.local` chứa toàn giá trị rỗng → ghi đè `web/.env`
→ Firebase/auth vỡ khi chạy dev. Giá trị rỗng trong file ưu tiên cao hơn vẫn tính là
"có đặt". Hãy điền đủ hoặc xóa dòng.

## Tham chiếu đầy đủ biến môi trường (canonical)

### Nhóm A — Auth & bảo mật
| Biến | Mặc định | Nơi đọc | Mô tả |
|------|----------|---------|-------|
| `ADMIN_LOGIN` / `ADMIN_PASSWORD` | (bắt buộc đặt) | backend `/api/auth/login`, web `pages/api/auth/login.ts` | Đăng nhập dashboard |
| `QUANTAI_BRIDGE_TOKEN` | *(bắt buộc, không có mặc định)* | web proxy, python-bridge | **Tên chuẩn** token Bearer EA↔server — FAIL-CLOSED: thiếu env = mọi endpoint /api/* bị khóa |
| `ATE_BRIDGE_TOKEN` | *(bắt buộc, cùng giá trị)* | alias tương thích | Luôn để CÙNG GIÁ TRỊ với `QUANTAI_BRIDGE_TOKEN` |
| `ATE_OPERATOR_TOKEN` | — | (dự phòng) | Token vận hành nâng cao |
| `JWT_SECRET` / `JWT_REFRESH_SECRET` | — | web `lib/middleware/auth.ts` | Tạo bằng `openssl rand -hex 32` — đã sinh sẵn trong root `.env`, `dashboard/.env`, `web/.env*`, `Cloudlocal/.env` |

### Nhóm B — Execution & Risk Gate (backend)
| Biến | Mặc định | Mô tả |
|------|----------|-------|
| `ATE_EXECUTION_MODE` | `DEMO` | `DEMO` (giả lập) / `LIVE` (thật, fail-closed) / `DISABLED` |
| `ATE_ENABLE_TRADING` | `false` | Bật cho phép tạo lệnh |
| `ATE_DEMO_ARMED` / `ATE_LIVE_ARMED` | `true` / `false` | Armed chế độ tương ứng |
| `ATE_KILL_SWITCH` | `false` | `true` = chặn mọi lệnh ngay lập tức |
| `ATE_EXECUTION_SYMBOL` | `XAUUSDm` | Symbol thực thi (khớp chart EA) |
| `ATE_EXECUTION_MAGIC` / `ATE_MAGIC_NUMBER` | `888999` | Magic Number (khớp `InpMagicNumber` EA) |
| `ATE_RISK_PERCENT` | `1` | % equity rủi ro mỗi lệnh (1 = 1%) |
| `ATE_MAX_POSITIONS` | `5` | Số vị thế mở tối đa |
| `ATE_MAX_SPREAD` | `4.5` | Spread tối đa cho phép |
| `ATE_DEMO_COMMAND_TTL_SECONDS` | `10` | TTL lệnh demo |

### Nhóm C — Network & URL
| Biến | Mặc định | Mô tả |
|------|----------|-------|
| `VNPT_PUBLIC_IP` | `113.173.192.226` | **IP công khai home server** (đổi khi IP đổi) |
| `ATE_BACKEND_URL` | `http://localhost:8005` | Backend; Docker `http://backend:8005`; Cloudlocal `http://nginx:80`; Vercel `http://<IP>:8848` |
| `ATE_FRONTEND_URL` | `https://autonomous-trading-engine.vercel.app` | Origin website |
| `ATE_MT5_API` | `https://autonomous-trading-engine.vercel.app/api/v1` | URL web dùng để rewrite `/api/v1/*` (next.config) — cầu nối cho EA tới home server |
| `NEXT_PUBLIC_ATE_API_ORIGIN` | — | Không được code đọc — có thể bỏ |
| `ATE_ALLOWED_ORIGINS` | localhost:3000/3005 + vercel.app | CORS cho backend |
| `ATE_DASHBOARD_HOST` / `ATE_DASHBOARD_PORT` | `0.0.0.0` / `8005` | Bind backend (KHÔNG dùng 8848 — nginx chiếm) |
| `BRIDGE_URL` / `BRIDGE_PORT` | `http://localhost:8007` / `8007` | python-bridge |
| `AI_ENGINE_URL` / `AI_ENGINE_PORT` | `http://localhost:8006` / `8006` | AI Engine |
| `REDIS_HOST` / `REDIS_PORT` | `localhost` / `6379` | Redis |
| `ATE_LOG_DIR` | `logs` | Thư mục log (logging_config.py) |
| `DEBUG` | `false` | Log chi tiết |

### Nhóm D — AI / LLM Gateway
| Biến | Mặc định | Mô tả |
|------|----------|-------|
| `ATE_AI_MODEL` | `deepseek-v4-flash-free` (qua .env; code fallback khi không set: `big-pickle`) | Model mặc định (OpenCode Zen free) |
| `OPENCODE_BASE_URL` | `https://opencode.ai/zen/v1/chat/completions` | Gateway free mặc định |
| `FREEBUFF_LLM_URL` | `http://127.0.0.1:8080/v1/chat/completions` | Freebuff2API (Docker: `http://freebuff2api:8080/...`) |
| `FREEBUFF_AUTH_TOKEN` | — | AuthToken Freebuff từ `~/.config/manicode/credentials.json` |
| `OPENAI_API_KEY` / `OPENAI_BASE_URL` | — / `https://api.openai.com/v1` | OpenAI (tùy chọn) |
| `GEMINI_API_KEY` / `GEMINI_BASE_URL` | — / `...googleapis.com/v1beta/openai/` | Gemini (tùy chọn) |
| `ZPLAY_API_KEY` / `ZPLAY_BASE_URL` | — / `https://router.flatkey.ai/v1` | Zplay (tùy chọn) |
| `GATEWAY_URL` / `GATEWAY_KEY` | — | Router cá nhân (OpenRouter...) — ưu tiên cao nhất |

**Thứ tự ưu tiên AI**: `GATEWAY_URL+KEY` → key/model khách hàng → OpenCode Zen Free (mặc định)
→ xoay vòng Freebuff2API khi bị rate limit.

### Nhóm E — MT5 (python-bridge)
| Biến | Mặc định | Mô tả |
|------|----------|-------|
| `MT5_PATH` | `C:\Program Files\MetaTrader 5-1\` | Đường dẫn terminal MT5 |
| `MT5_AUTOSTART` | `true` | Tự khởi động MT5 |
| `MT5_TERMINAL_TIMEOUT_SECONDS` | `30` | Timeout kết nối terminal |

### Nhóm F — Telegram
| Biến | Mặc định | Mô tả |
|------|----------|-------|
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` / `TELEGRAM_ENABLED` | — / — / `true` | Bot thông báo |

### Nhóm G — Firebase
| Biến | Mô tả |
|------|-------|
| `NEXT_PUBLIC_FIREBASE_*` (7 biến) | Config web app công khai (frontend) |
| `FIREBASE_ENABLE_SYNC` | Bật mirror config lên Firestore |
| `FIREBASE_PROJECT_ID` / `FIREBASE_API_KEY` | Đồng bộ backend |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | (khuyến nghị) base64 serviceAccountKey.json |

### Nhóm H — Postgres / Docker (Cloudlocal)
| Biến | Mặc định |
|------|----------|
| `POSTGRES_HOST` / `POSTGRES_PORT` / `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | `postgres` / `5432` / `ate` / `ate` / — |

## Triển khai 3 môi trường

### 1. Local dev (máy Windows cài MT5) — ⚠️ BẮT BUỘC đọc kỹ
```bash
cd dashboard && pip install -r requirements.txt && python server.py      # :8005
cd web && npm install && npm run dev                                       # :3005
# Mở http://localhost:3005, đăng nhập, vào Control Center
```
**EA trong MT5 — QUAN TRỌNG (MT5 WebRequest CHẶN localhost/127.0.0.1):**
1. Trong MetaEditor: đổi `InpApiUrl = http://192.168.1.12:8005/api/v1/`
   (thay `192.168.1.12` bằng IP LAN của máy — xem `ipconfig`; cũng có trong
   Control Center → MT5 Diagnostics). **KHÔNG dùng `http://localhost:8005`**.
2. MT5 allowlist: `Công cụ → Tùy chọn → Trình điều tra` → bật `Allow WebRequest`
   → thêm `http://192.168.1.12` (IP LAN) vào danh sách.
3. Windows Firewall: cho phép cổng **8005 TCP** inbound (nếu cần).
4. Attach EA vào chart XAUUSD, bật **Algo Trading** (nút ON).
5. Kiểm tra MT5 Experts log có `TELEMETRY_OK` / `CANDLES_PUSH_OK` — khi đó web
   hiện MT5 CONNECTED + balance/equity thật.

> Mẹo: dùng nút **Connect** trong Control Center (đăng nhập MT5) — server tự
> launch terminal, login, copy EA, mở chart XAUUSD M15, attach EA và bật Algo
> Trading, trả báo cáo từng bước. Nếu EA ở máy khác, dùng `http://<IP-LAN>:8005/api/v1/`
> + mở firewall 8005.
> Nếu muốn qua internet (Vercel): phải deploy `web/vercel.json` với rewrite về
> `http://<VNPT_PUBLIC_IP>:8848` VÀ home server chạy nginx + backend (mục 3).

### 2. Docker (home server / máy nhà)
```bash
cp Cloudlocal/.env.template Cloudlocal/.env   # rồi sửa giá trị
docker compose -f Cloudlocal/docker-compose.yml up -d --build
# python-bridge chạy NATIVE trên máy Windows cài MT5 (start.bat) — không trong container
```

### 3. Production: Vercel (frontend) + VNPT home server (backend)
1. Home server chạy `docker compose up -d` (backend + frontend + redis).
2. Modem VNPT: **port forward 8848 → IP LAN của home server:8848** (TCP).
   - Kiểm tra: `http://<VNPT_PUBLIC_IP>:8848/health` từ ngoài mạng.
3. `web/vercel.json`: set `ATE_BACKEND_URL` = `http://<VNPT_PUBLIC_IP>:8848`
   (rewrite `/api/v1/*` → home server). Deploy lên Vercel.
4. EA trong MT5: giữ `InpApiUrl = https://autonomous-trading-engine.vercel.app/api/v1/`,
   thêm domain vào **MT5 WebRequest allowlist** (`Công cụ → Tùy chọn → Trình điều tra`).
5. Bật `ATE_EXECUTION_MODE=LIVE` + `live_armed=true` khi sẵn sàng trade thật.

> ⚠️ **QUAN TRỌNG — env trên Vercel Dashboard (Project → Settings → Environment
> Variables) GHI ĐÈ lên env trong `web/vercel.json`.** 4 biến phải đúng:
>
> | Biến | Giá trị ĐÚNG | Giá trị SAI (gây hỏng) |
> |------|-------------|------------------------|
> | `ATE_BACKEND_URL` | `http://113.173.192.226:8848` | `https://...vercel.app/backend` (tự tham chiếu → loop) |
> | `ATE_MT5_API` | `http://113.173.192.226:8848/api/v1` | `https://...vercel.app/api/v1` (rewrite loop) |
> | `ATE_DASHBOARD_PORT` | `8005` | `8848` (server.py bind đè nginx) |
> | `ATE_DASHBOARD_HOST` | `0.0.0.0` | `http://127.0.0.1/` (sai format) |
>
> `NEXT_PUBLIC_ATE_API_ORIGIN` không được code đọc — có thể xóa khỏi Dashboard
> để tránh nhầm lẫn.

## Lỗi cú pháp .env thường gặp (đã sửa trong repo)

| Lỗi | Ví dụ | Hệ quả | Cách tránh |
|-----|-------|--------|------------|
| Dấu ngoặc kép thừa cuối giá trị | `ATE_FRONTEND_URL=https://...vercel.app"` | URL sai, frontend hỏng | Không bọc giá trị bằng `"` trong .env |
| Khoảng trắng đầu giá trị | `ATE_BACKEND_URL= http://...` | URL có space → connect fail | Không có space quanh `=` |
| Key trùng lặp | `ATE_BRIDGE_TOKEN` x2 | Dòng sau thắng, khó debug | Giữ mỗi key 1 lần |
| `.env.local` giá trị rỗng | `NEXT_PUBLIC_FIREBASE_API_KEY=` | Ghi đè `.env` (ưu tiên cao hơn) | Điền đủ hoặc xóa dòng |
| Tên token lệch nhau | `QUANTAI_*` vs `ATE_*` | EA 401 / proxy 401 | Dùng `QUANTAI_BRIDGE_TOKEN` chuẩn, alias cùng giá trị |
| Port lệch | backend 8005 vs 8848 | Nginx chết / bind đè | Backend LUÔN 8005; 8848 chỉ là cổng public nginx |

## Security Checklist (trước khi chạy LIVE)

- [ ] Đổi `QUANTAI_BRIDGE_TOKEN` / `ATE_BRIDGE_TOKEN` sang token ngẫu nhiên
      (`openssl rand -hex 32`) và đồng bộ vào **EA (InpBridgeToken) + backend + web proxy**.
- [ ] Đổi `ADMIN_PASSWORD`, `JWT_SECRET`, `JWT_REFRESH_SECRET`.
- [ ] Xoay vòng token định kỳ; backup `.env` ở nơi an toàn, KHÔNG commit.
- [ ] Không commit bất kỳ `.env` nào (gitignore đã chặn — kiểm tra `git status`).
- [ ] `ATE_ALLOWED_ORIGINS` chỉ chứa origin thực sự dùng.
- [ ] Chỉ bật `ATE_EXECUTION_MODE=LIVE` + `ATE_LIVE_ARMED=true` khi đã kiểm chứng DEMO.
- [ ] Kiểm tra `FIREBASE_SERVICE_ACCOUNT_JSON` nếu bật `FIREBASE_ENABLE_SYNC`.

## Troubleshooting

| Triệu chứng | Nguyên nhân / Sửa |
|-------------|--------------------|
| Dashboard báo `STUB`, giá không phải thật | EA chưa connect (kiểm tra telemetry trong /api/logs), hoặc EA gửi mà server 422 (đã fix executor_id). Kiểm tra `CANDLES_PUSH_OK` trong MT5 Experts log. |
| `data_status=LIVE` nhưng equity đứng yên | EA chưa gửi telemetry → kiểm tra token + allowlist + `TELEMETRY_OK` trong MT5 log. |
| Lệnh không vào được | Chế độ `LIVE` cần EA connected + claim thành công (xem `CMD_CLAIMED` trong /api/logs). `DEMO` tự giả lập. |
| Vercel 404 `/api/v1/*` | IP VNPT thay đổi → cập nhật `vercel.json` + redeploy; hoặc modem mất port-forward. |
| EA báo HTTP 401 | `QUANTAI_BRIDGE_TOKEN` lệch giữa EA (InpBridgeToken) và backend. |
| EA báo lỗi WebRequest | Domain chưa được allowlist trong MT5 (chỉ được dùng host/IP, không `127.0.0.1`). |
| Frontend không gọi được backend | `web/.env.local` đang ghi đè `ATE_BACKEND_URL` bằng giá trị rỗng/sai. |
