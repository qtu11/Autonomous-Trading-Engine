# 🌐 ENVIRONMENT CONFIG — Kiến trúc triển khai chuẩn (CANONICAL)

> ⚠️ **Tài liệu này phản chiếu `ENVIRONMENT_CONFIG.md` (gốc) — nguồn duy nhất.**
> Mọi thay đổi port/URL/logic triển khai phải sửa file gốc và đồng bộ lại file này.
> (Trước đây hai file lệch nhau: gốc ghi IP LAN `192.168.1.12`, Vercel dùng IP
> công khai `113.173.192.226` → đã thống nhất về khái niệm `VNPT_PUBLIC_IP`.)

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
1. EA đẩy nến thật qua `POST /api/v1/bridge/candles` → server lưu `_market_cache`
   (trước đây model yêu cầu `executor_id` → 422 → dữ liệu luôn là stub giả).
2. `fetch_real_candles` đọc: **EA push → python-bridge `/api/v1/market/candles`
   (copy_rates thật) → stub** (đánh dấu `data_status=STUB`).
3. Bid/ask thật: **telemetry EA → python-bridge `/api/v1/market/tick` → stub**.
4. `execution_mode=LIVE`: fail-closed — server **không bao giờ giả lập** lệnh.

## Cổng & dịch vụ

| Service | Cổng | Môi trường chạy | Ghi chú |
|---------|------|-----------------|---------|
| FastAPI backend (server.py) | 8005 | Windows native hoặc Docker | `ATE_DASHBOARD_PORT` |
| python-bridge (MT5) | 8007 | **Windows native** (cần MetaTrader5) | `BRIDGE_URL` của server |
| AI Engine | 8006 | Docker (tùy chọn) | `AI_ENGINE_URL` |
| Redis | 6379 | Docker | `REDIS_HOST/PORT` |
| Next.js frontend | 3000 | Docker/Vercel | `ATE_BACKEND_URL` |
| nginx (home server) | 80, **8848** | Docker | 8848 = public (80/443 bị modem VNPT chiếm) |

> **Vì sao bridge phải chạy native trên Windows?** Package `MetaTrader5` chỉ hoạt
> trên Windows có cài MT5. Container Linux không nối được MT5. EA trong MT5 là
> nguồn nến chính; bridge native phục vụ đa khung giờ (M5/M15/H1/D1).

## Biến môi trường (canonical)

| Biến | Nơi đặt | Giá trị mặc định | Mô tả |
|------|---------|------------------|-------|
| `ATE_BACKEND_URL` | Vercel env / docker-compose / local | `http://localhost:8005` | Backend; Docker: `http://backend:8005`; Vercel: `http://<VNPT_IP>:8848` |
| `BRIDGE_URL` | backend env | `http://localhost:8007` | python-bridge (nối MT5) |
| `AI_ENGINE_URL` | backend env | `http://localhost:8006` | AI Engine (tùy chọn) |
| `REDIS_HOST` / `REDIS_PORT` | backend env | `localhost` / `6379` | Redis |
| `ATE_EXECUTION_MODE` | backend env | `DEMO` | `DEMO` (giả lập) / `LIVE` (thật, fail-closed) |
| `ADMIN_LOGIN` / `ADMIN_PASSWORD` | backend env | (bắt buộc đặt) | Đăng nhập dashboard |
| `QUANTAI_BRIDGE_TOKEN` | backend + EA | `20022007@Tu` | Bearer token EA↔server (NÊN đổi) |
| `MT5_LOGIN` / `MT5_PASSWORD` / `MT5_SERVER` | python-bridge env | — | Tài khoản MT5 cho bridge |
| `VNPT_PUBLIC_IP` | vercel.json + docs | `113.173.192.226` | **IP công khai VNPT** (đổi khi IP đổi) |

## Triển khai 3 môi trường

### 1. Local dev (máy Windows cài MT5) — ⚠️ BẮT BUỘC đọc kỹ
```bash
cd dashboard && pip install -r requirements.txt && python server.py   # :8005
cd web && npm install && npm run dev                                   # :3000
```
**EA trong MT5 — QUAN TRỌNG (MT5 WebRequest CHẶN localhost/127.0.0.1):**
1. `InpApiUrl = http://192.168.1.12:8005/api/v1/` (IP LAN của máy, xem `ipconfig`
   hoặc Control Center → MT5 Diagnostics). **KHÔNG dùng localhost**.
2. MT5 allowlist: `Công cụ → Tùy chọn → Trình điều tra` → Allow WebRequest →
   thêm `http://192.168.1.12`.
3. Windows Firewall: cho phép cổng **8005 TCP** inbound.
4. Attach EA vào chart XAUUSD, bật **Algo Trading**.
5. Log MT5 có `TELEMETRY_OK`/`CANDLES_PUSH_OK` → web hiện MT5 CONNECTED + số thật.

> Mẹo: nút **Connect** trong Control Center tự launch/login/copy EA/mở chart/attach
> và trả báo cáo từng bước. Nếu muốn qua internet (Vercel): deploy vercel.json
> rewrite về `http://<VNPT_PUBLIC_IP>:8848` + home server chạy nginx + backend.

### 2. Docker (home server / máy nhà)
```bash
docker compose up -d --build    # backend :8005, frontend :3000, redis
# python-bridge chạy NATIVE trên máy Windows cài MT5 (start.bat)
```

### 3. Production: Vercel (frontend) + VNPT home server (backend)
1. Home server chạy `docker compose up -d`.
2. Modem VNPT: **port forward 8848 → IP LAN home server:8848** (TCP).
   Kiểm tra: `http://<VNPT_PUBLIC_IP>:8848/health`.
3. `web/vercel.json`: `ATE_BACKEND_URL` = `http://<VNPT_PUBLIC_IP>:8848`, deploy Vercel.
4. EA trong MT5: `InpApiUrl = https://autonomous-trading-engine.vercel.app/api/v1/`,
   thêm domain vào **MT5 WebRequest allowlist**.
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
> `NEXT_PUBLIC_ATE_API_ORIGIN` không được code đọc — có thể xóa khỏi Dashboard.

## Troubleshooting

| Triệu chứng | Nguyên nhân / Sửa |
|-------------|--------------------|
| Dashboard báo `STUB` | EA chưa connect hoặc telemetry chưa OK. Kiểm tra `CANDLES_PUSH_OK`/`TELEMETRY_OK` trong MT5 Experts log. |
| `data_status=LIVE` nhưng equity đứng yên | EA chưa gửi telemetry → kiểm tra token + allowlist. |
| Lệnh không vào được | Chế độ `LIVE` cần EA connected + `CMD_CLAIMED`. `DEMO` tự giả lập. |
| Vercel 404 `/api/v1/*` | IP VNPT đổi → cập nhật `vercel.json` + redeploy; hoặc mất port-forward. |
| EA báo HTTP 401 | `QUANTAI_BRIDGE_TOKEN` lệch giữa EA và backend. |
| EA báo lỗi WebRequest | Domain chưa allowlist trong MT5 (chỉ host/IP, không `127.0.0.1`). |
