# 🌐 ENVIRONMENT CONFIG — Kiến trúc triển khai chuẩn (CANONICAL)

> Tài liệu này là **nguồn duy nhất** cho cấu hình môi trường. `docs/ENVIRONMENT_CONFIG.md`
> chứa cùng nội dung. Mọi thay đổi port/URL phải cập nhật cả hai file.

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
| Redis | 6379 | Docker | `REDIS_HOST/PORT` |
| Next.js frontend | 3000 | Docker/Vercel | `ATE_BACKEND_URL` |
| nginx (home server) | 80, **8848** | Docker | 8848 = public (80/443 bị modem VNPT chiếm) |

> **Vì sao bridge phải chạy native trên Windows?** Package `MetaTrader5` chỉ hoạt
> động trên Windows có cài MT5. Container Linux **không** nối được MT5. Trên máy
> Windows cài MT5, bridge là nguồn nến đa khung giờ (M5/M15/H1/D1) cho dashboard;
> EA là nguồn nến chính của chart đang xem.

## Biến môi trường (canonical)

| Biến | Nơi đặt | Giá trị mặc định | Mô tả |
|------|---------|------------------|-------|
| `ATE_BACKEND_URL` | Vercel env / docker-compose / local | `http://localhost:8005` | Backend FastAPI; Docker: `http://backend:8005`; Vercel: `http://<VNPT_IP>:8848` |
| `BRIDGE_URL` | backend env | `http://localhost:8007` | python-bridge (nối MT5) |
| `AI_ENGINE_URL` | backend env | `http://localhost:8006` | AI Engine (tùy chọn) |
| `REDIS_HOST` / `REDIS_PORT` | backend env | `localhost` / `6379` | Redis (bridge dùng) |
| `ATE_EXECUTION_MODE` | backend env | `DEMO` | `DEMO` (giả lập) / `LIVE` (thật, fail-closed) |
| `ADMIN_LOGIN` / `ADMIN_PASSWORD` | backend env | (bắt buộc đặt) | Đăng nhập dashboard |
| `QUANTAI_BRIDGE_TOKEN` | backend + EA | `20022007@Tu` | Bearer token EA↔server (NÊN đổi) |
| `MT5_LOGIN` / `MT5_PASSWORD` / `MT5_SERVER` | python-bridge env | — | Tài khoản MT5 cho bridge |
| `VNPT_PUBLIC_IP` | vercel.json + docs | `113.173.192.226` | **IP công khai VNPT của home server** (đổi khi IP đổi) |

## Triển khai 3 môi trường

### 1. Local dev (máy Windows cài MT5) — ⚠️ BẮT BUỘC đọc kỹ
```bash
cd dashboard && pip install -r requirements.txt && python server.py      # :8005
cd web && npm install && npm run dev                                       # :3000
# Mở http://localhost:3000, đăng nhập, vào Control Center
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
docker compose up -d --build        # backend :8005, frontend :3000, redis
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

## Troubleshooting

| Triệu chứng | Nguyên nhân / Sửa |
|-------------|--------------------|
| Dashboard báo `STUB`, giá không phải thật | EA chưa connect (kiểm tra telemetry trong /api/logs), hoặc EA gửi mà server 422 (đã fix executor_id). Kiểm tra `CANDLES_PUSH_OK` trong MT5 Experts log. |
| `data_status=LIVE` nhưng equity đứng yên | EA chưa gửi telemetry → kiểm tra token + allowlist + `TELEMETRY_OK` trong MT5 log. |
| Lệnh không vào được | Chế độ `LIVE` cần EA connected + claim thành công (xem `CMD_CLAIMED` trong /api/logs). `DEMO` tự giả lập. |
| Vercel 404 `/api/v1/*` | IP VNPT thay đổi → cập nhật `vercel.json` + redeploy; hoặc modem mất port-forward. |
| EA báo HTTP 401 | `QUANTAI_BRIDGE_TOKEN` lệch giữa EA (InpBridgeToken) và backend. |
| EA báo lỗi WebRequest | Domain chưa được allowlist trong MT5 (chỉ được dùng host/IP, không `127.0.0.1`). |
