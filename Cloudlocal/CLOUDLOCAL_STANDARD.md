# CLOUDLOCAL — QUY TRÌNH CHUẨN
# Biến PC thành Cloud cục bộ kết nối Website (Vercel) và MT5

> Phiên bản: 1.0   |   Hệ thống: GoldQuant Autonomous Trading Engine (ATE)
> Tài liệu này là quy trình chuẩn (Standard Operating Procedure) để thiết lập, vận hành và
> chẩn đoán hạ tầng Cloudlocal: một "đám mây cục bộ" chạy trong Docker trên máy Windows,
> làm cầu nối hai chiều giữa website `https://autonomous-trading-engine.vercel.app`
> và terminal MetaTrader 5 đang chạy native trên máy chủ tịch.

---

## MỤC LỤC
1. [Kiến trúc tổng thể](#1-kiến-trúc-tổng-thể)
2. [Giao thức chuẩn — `https://autonomous-trading-engine.vercel.app/api/v1`](#2-giao-thức-chuẩn)
3. [Luồng tín hiệu 2 chiều Website ↔ MT5](#3-luồng-tín-hiệu-2-chiều)
4. [3 phương án mở cổng Internet cho máy](#4-3-phương-án-mở-cổng-internet)
5. [Triển khai Docker Cloudlocal](#5-triển-khai-docker-cloudlocal)
6. [Cấu hình Vercel (chuẩn / sai)](#6-cấu-hình-vercel)
7. [Cấu hình MT5 + EA](#7-cấu-hình-mt5--ea)
8. [Khắc phục lỗi "Không thể kết nối API Backend (port 8005)"](#8-khắc-phục-lỗi-không-thể-kết-nối-api-backend)
9. [Checklist kiểm tra end-to-end](#9-checklist-kiểm-tra-end-to-end)
10. [Tham chiếu nhanh Port & Endpoint](#10-tham-chiếu-nhanh-port--endpoint)
11. [Bảo mật](#11-bảo-mật)
12. [Rollback & Khôi phục](#12-rollback--khôi-phục)

---

## 1. KIẾN TRÚC TỔNG THỂ

```
                      INTERNET
   ┌──────────────────────────────────────────────────────────────┐
   │                                                              │
   │  Website (Vercel Cloud)          PC CỦA CHỦ TỊCH (CLOUDLOCAL) │
   │  https://autonomous-trading-     ┌────────────────────────────│
   │        engine.vercel.app        │  DOCKER (network host)     │   │
   │  ┌───────────────────────────┐ │  ┌──────────────────────┐  │
   │  │ Next.js Frontend (SSR)     │ │  │ nginx :80 (reverse)  │  │
   │  │ rewrite /api/:path*        │◄┼──│   /api → fastapi      │  │
   │  │   → ATE_BACKEND_URL        │ │  │   /     → nextjs 3000 │  │
   │  └────────────┬──────────────┘ │  │   /ai   → ai-core 8006 │  │
   │        browser (CLIENT)        │  │   /bridge → bridge     │  │
   │  (fetch cùng-namespace /api)   │  │   /ws   → fastapi      │  │
   │ ─────────────────────────────  │  └───────────┬────────────┘  │
   │                                 │  FastAPI 8005  (dashboard)  │
   │  MT5 EA (MQL5 WebRequest)      │   /api/* + /api/v1/*         │
   │  https://...vercel.app/api/v1  │   command_store, telemetry   │
   │   ──► (rewrite) ──► local cloud  │  Python-bridge 8007 (tùy)   │
   │  │                              │  Postgres 5432 | Redis 6379  │
   │  │                              │          │                   │
   │  │                              │          ▼                   │
   │  │                              │  METATRADER 5 (Windows host) │
   │  └──────────────────────────────┴─────────────────────E A ──────┘
   │  CTrade thực thi lệnh là TOÀN QUYỀN của EA (fail-closed)
   └───────────────────────────────────────────────────────────────
```

### Thành phần chính

| Thành phần | Vai trò | Port |
|---|---|---|
| **Vercel Next.js** | Frontend deploy, `rewrites /api/:path* → ATE_BACKEND_URL` | 443 (public) |
| **nginx** (Docker) | Reverse proxy, đơn điểm vào công khai | 80 host |
| **FastAPI backend** | `dashboard/server.py` — status, control-center, command store, telemetry, websocket | 8005 |
| **AI Engine** (Docker) | `ai-engine/app/main.py` — inference đa mô hình | 8006 |
| **Python Bridge** (Docker/tùy chọn) | `python-bridge/app/main.py` — chỉ health/docs trên Linux (thực thi thật do EA) | 8007 |
| **MT5 EA** (native host) | `QuantAI_XAUUSD.mq5` — quyền thực thi lệnh DUY NHẤT | — |
| **PostgreSQL / Redis** | lưu command, cache, pub/sub | 5432 / 6379 |

---

## 2. GIAO THỨC CHUẨN
### `https://autonomous-trading-engine.vercel.app/api/v1`

Đây là "giao thức hợp nhất" (unified API base) cho **mọi** đối tượng gọi API:

- **MT5 EA** đặt `InpApiUrl = https://autonomous-trading-engine.vercel.app/api/v1/`
- **Vercel website** dùng cùng namespace (browser + rewrite)
- **AI Engine, scripts** dùng cùng base

### Quy tắc URL (quan trọng — tránh lỗi double prefix)

1. `ATE_BACKEND_URL` trên Vercel **KHÔNG được chứa `/api/v1`** ở đuôi và **KHÔNG trỏ về chính vercel.app**:
   - ✔ Đúng: `http://YOUR_PUBLIC_IP:80`, `https://cloudlocal-trade.example.com`
   - ✘ Sai: `https://autonomous-trading-engine.vercel.app` → **vòng lặp rewrite vô hạn**
   - `next.config.ts` cộng sẵn `/api/:path*` vào đuôi.
2. `NEXT_PUBLIC_ATE_API_ORIGIN` / `NEXT_PUBLIC_QUANTAI_API_ORIGIN` **cũng không chứa `/api/v1`**:
   - code frontend tự nối `/api/...` phía sau (xem `web/lib/api.ts`).
3. MQL5 `QuantAIApiBase()` được viết để **tự lột bỏ** `/api/v1` và `/api` ở đuôi `InpApiUrl`, sau đó dựng endpoint đầy đủ (đã đúng).

### Bảng endpoints chuẩn (Vercel /api/v1 → Cloudlocal)

| Method | Endpoint (thông qua vercel) | Đích thật | Mô tả |
|---|---|---|---|
| POST | `/api/auth/login` | FastAPI | Xác thực Quản trị (website) |
| GET | `/api/status` | FastAPI | Telemetry tổng hợp (website) |
| GET | `/api/market` | FastAPI | Nến + chỉ báo |
| GET | `/api/positions`, `/api/history`, `/api/pending-orders` | FastAPI | Dữ liệu tài khoản/lệnh |
| WS | `/ws/stream` | FastAPI | Stream realtime |
| POST | `/api/telemetry` | FastAPI (Bearer) | EA gửi telemetry (từ MT5) |
| POST | `/api/v1/bridge/commands/claim` | FastAPI (Bearer) | **EA claim lệnh** |
| POST | `/api/v1/bridge/commands/{id}/receipt` | FastAPI (Bearer) | **EA gửi biên nhận thực thi** |
| POST | `/api/order/buy`, `/api/order/sell`, v.v. | FastAPI + MT5 | Đặt lệnh từ website |

> Lưu ý: `/api/v1/...` khi gọi qua Vercel sẽ được rewrite thành `{ATE_BACKEND_URL}/api/v1/...` → nginx `/api/` → FastAPI (đường đi đúng vì nginx forward nguyên path).

---

## 3. LUỒNG TÍN HIỆU 2 CHIỀU

### 3.1 Chiều **Website → MT5** (website gửi tín hiệu BUY/SELL/CLOSE)

```
Browser               Vercel Next.js          Cloudlocal nginx         FastAPI 8005                →  MT5
  │ POST /api/order/buy  │                       │                       │                         │
  ├──────────────────────► ├─ rewrite ──────────► ├─ /api/ → upstream ──► ├─ write PENDING command   │
  │                       │  (ATE_BACKEND_URL)  │                    │    vào command_store       │
  │                       │                    │                     │  (Postgres/SQLite)       │
  │                       │                    │                     │◄──────────────────────────│ EA (MQL5)
  │                       │                    │                     │   poll POST /claim (1s)   │  claim thành
  │                       │                    │                     │── return {status: CLAIMED}─►  EA parse lệnh
  │                       │                    │                     │  (nếu claim)              │  (action, volume, sl, tp)
  │                       │                    │                     │◄── receipt POST ───────────│  EA thực thi CTrade
  │◄── {success, ticket, price} ─────────────── (receipt forwarded) │ (EXECUTED/REJECTED)    │
  ───────────────────────────────────────────────────────────────────────────────────────────────────────────
```

- Website **không trực tiếp** vào MT5. Website viết **Command** vào Backend; EA **polling `claim`** mỗi 1s, **tự đánh giá guard** >>> **execute** bằng `CTrade`, rồi **POST receipt**.
- Đây là mô hình **command sink / poll executor** — EA là cơ quan thực thi tuyệt đối (fail-closed), đúng theo `docs/MT5_PROTOCOL.md`.

### 3.2 Chiều **MT5 → Website** (website lấy được dữ liệu từ MT5)

```
MT5 EA (WebRequest POST /api/v1/telemetry)         FastAPI 8005            Postgres/Redis     Website
  │  {balance, equity, margin, positions, ask,      │                        │               │
  │      bid, ai trigger...}  (1 lần/s)            ├─ store + notify  ──────► │               │
  ├───────────────────────────────────────────────►│                         |               │
  │                    (qua vercel rewrite → nginx)│◄── GET /api/status ────────────────────────► browser
  │                                              │   broadcaster /ws/stream ──► browser (real-time)
  └───────────────────────────────────────────────►  EA heartbeat liveness
```

- EA gửi `telemetry` (1s) và `calendar protection` — FastAPI lưu vào DB + broadcast qua `/ws/stream`.
- Website gọi `GET /api/status` (poll 1–2s) hoặc nối WebSocket `/ws/stream` để nhận `{type:'telemetry'}` realtime.

> **Kết luận**: Tín hiệu 2 chiều đều đi qua **một cổng duy nhất**: `https://autonomous-trading-engine.vercel.app/api/*` → rewrite → nginx → FastAPI → (claim/execute → MT5 | broadcast/status → Website). Không có kết nối trực tiếp tới 8005 từ trình duyệt (tránh mixed-content/CORS).

---

## 4. MỞ CỔNG INTERNET CHO MÁY (KHÔNG DÙNG TUNNEL BÊN THỨ 3)

Yêu cầu: website (cloud) + EA (MT5) phải **gọi được** vào máy chủ tịch. Hệ thống KHÔNG sử dụng ngrok, Cloudflare Tunnel hay bất kỳ dịch vụ tunnel bên thứ 3 nào — chỉ dùng **IP công khai + port-forward + (tùy chọn) DDNS**.

### 4.1 – Public IP + DDNS + port-forward (cách chuẩn của cloudlocal)

1. Lấy IP công khai: `Invoke-RestMethod https://api.ipify.org`
2. Trên router: forward `80 → máy:80` (chỉ mở 80; **không** mở 5432/6379, hạn chế 8005).
3. (Tùy chọn) DDNS (No-IP/DuckDNS) cho IP động — giúp `ATE_BACKEND_URL` không đổi khi IP đổi.
4. Gán `PUBLIC_IP=<IP/DDNS>` trong `Cloudlocal/.env` và `ATE_BACKEND_URL` trên Vercel.
5. Mở firewall Windows cho cổng 80: `.\scripts\setup-firewall-portforward.ps1`.

> Lưu ý CGNAT: nếu nhà mạng dùng CGNAT, phải liên hệ ISP xin IP tĩnh hoặc mở NAT cho cổng 80 — không dùng tunnel thay thế.

---

## 5. TRIỂN KHAI DOCKER CLOUDLOCAL

### 5.1 Điều kiện tiên quyết
- Docker Desktop chạy (backend **WSL2**). Kiểm tra: `docker info`.
- MT5 cài `C:\Program Files\MetaTrader 5\terminal64.exe`.
- Cổng tự do trên host: `80, 3000, 8005, 8006, 8007, 8080, 5432, 6379`.

### 5.2 Cấu hình `.env`
```powershell
cd Cloudlocal
Copy-Item .env.template .env
notepad .env
```
Bắt buộc sửa:
```env
PUBLIC_IP=<IP hoặc DDNS công khai>
MT5_LOGIN=...  MT5_PASSWORD=...  MT5_SERVER=...
QUANTAI_BRIDGE_TOKEN=<openssl rand -hex 32>
ADMIN_LOGIN=admin  ADMIN_PASSWORD=<mật khẩu mạnh>
ATE_BACKEND_URL=http://${PUBLIC_IP}:80      # KHÔNG có /api/v1, KHÔNG trỏ về vercel
```
Sinh token: `openssl rand -hex 32` (hoặc `docker run --rm alpine openssl rand -hex 32`).

### 5.3 Khởi động
```cmd
docker compose -p cloudlocal up -d --build
```
Kiểm tra:
```cmd
docker compose ps
docker compose logs -f fastapi        # backend chính
docker compose logs -f nginx
```

### 5.4 Health check
```powershell
# Local (host)
Invoke-RestMethod http://localhost:80/health          ; # nginx → "healthy"
Invoke-RestMethod http://localhost:8005/health        ; # FastAPI → {"status":"UP"...}
Invoke-RestMethod http://localhost:8005/api/status    ; # → data_status LIVE_VERIFIED
Invoke-RestMethod http://localhost:8080/api/status    ; # qua port-exposer
```

> **Đã sửa (so với trước)** — nhằm stack chạy được ngay:
> 1. `nginx.conf`: bỏ `server { listen 8005 }` (xung đột cổng host với FastAPI trên `network_mode: host` → trước đó nginx crash-loop).
> 2. `docker-compose.yml`: `NEXT_PUBLIC_ATE_API_ORIGIN/QUANTAI` bỏ hậu tố `/api/v1` (double-prefix `/api/v1/api/...` → 404 như đã test).
> 3. `python-bridge` & `ai-engine`: mount module đúng (`./python-bridge/app:/app/bridge`, `./ai-engine/app:/app/ai_engine`) + CMD `python -m bridge.main` / `ai_engine.main` (trước đó `python -m python_bridge.main` → module không tồn tại → crash-loop).
> 4. `web/next.config.ts`: `output: 'standalone'` (Dockerfile nextjs cần `.next/standalone` — trước đây build không có).
> 5. Tạo `dashboard/requirements.txt` (3 Dockerfile dùng build context `../dashboard` nhưng file này thiếu → build FAIL).
> 6. `.env.example` + `Cloudlocal/.env.template`: sửa URL sai (bỏ `/api/v1`, cấm self-loop).

---

## 6. CẤU HÌNH VERCEL

### 6.1 Environment Variables (Project Settings → Environment Variables)

```
ATE_BACKEND_URL = http://<PUBLIC_IP>:80               # DDNS domain hoặc IP công khai
                                                       # KHÔNG /api/v1, KHÔNG vercel.app
NEXT_PUBLIC_ATE_API_ORIGIN = (để TRỐNG / xóa)        # → browser dùng same-origin /api/*
NEXT_PUBLIC_QUANTAI_API_ORIGIN = (để TRỐNG / xóa)    # → rewrite server-side
```
Chọn đúng environment: **Production** phải có giá trị; Preview/Development tuỳ chọn.
**Sau khi đổi env phải Redeploy**: Deployments → ⋯ → Redeploy.

### 6.2 Vì sao phải để `NEXT_PUBLIC_*` trống?

- Khi để trống → browser gọi **cùng origin** `https://...vercel.app/api/status` → Next.js `rewrites()` gửi server-side tới `ATE_BACKEND_URL`. Không có vấn đề **CORS / mixed-content**.
- Nếu đặt `NEXT_PUBLIC_ATE_API_ORIGIN=http://<PUBLIC_IP>:80`, browser gọi **trực tiếp** IP công khai từ trang HTTPS: phải có **HTTPS** và CORS trên FastAPI mới được (rủi ro hơn).
- Nếu đặt `NEXT_PUBLIC_ATE_API_ORIGIN=https://...vercel.app/api/v1` → **Sai double-prefix**: trở thành `/api/v1/api/status` → 404 (đã test 404).

### 6.3 Frontend "backend" via `/backend` (nếu boss muốn)

Muốn dịch vụ backend hiện dưới path `/backend` thay vì `/api`, thêm `vercel.json` và/dùng rewrite thứ 2:
```json
{
  "rewrites": [
    { "source": "/backend/:path*", "destination": "/api/:path*" }
  ]
}
```
(không bắt buộc; mặc định chuẩn là namespace `/api`).

---

## 7. CẤU HÌNH MT5 + EA

1. Mở EA `QuantAI_XAUUSD.mq5` (hoặc `ATE_XAUUSD.mq5`) trong MetaEditor → biên dịch.
2. Kéo EA lên chart `XAUUSDm`. Inputs:
   - `InpApiUrl = https://autonomous-trading-engine.vercel.app/api/v1/`  (giữ nguyên)
   - `InpBridgeToken = <QUANTAI_BRIDGE_TOKEN trong .env>`
   - `InpExecutionEnabled = true` (sau khi arm demo/live đúng guard)
3. **Tools → Options → Expert Advisors → Allow WebRequest for listed URL**, thêm ĐẦY ĐỦ các URL sau:
   ```
   https://autonomous-trading-engine.vercel.app
   http://<IP/DDNS công khai>   (backend cloudlocal)
   http://192.168.x.x        (IP LAN nếu dùng trực tiếp)
   ```
   (MT5 chặn loopback `127.0.0.1`, phải ghi hostname/IP.)
4. Đảm bảo đã **AutoTrading** (Algo Trading) ON, EA không báo `trade_allowed=0`.

---

## 8. KHẮC PHỤC LỖI "Không thể kết nối API Backend. Vui lòng kiểm tra dịch vụ backend (port 8005)!"

### I. Summary
Lỗi hiện khi **browser không nhận được phản hồi từ điểm API** — thường vì `ATE_BACKEND_URL` trên Vercel sai (trỏ self-loop về chính vercel.app) hoặc đường dẫn bị **double prefix `/api/v1/api` → 404**. Backend local (8005) và MT5 vẫn đang chạy tốt.

### II. Root Cause (tối đa 3)
1. `ATE_BACKEND_URL` trên Vercel sai: `https://autonomous-trading-engine.vercel.app/api/v1/` → rewrite `/api/:path*` nối lồng → **vòng lặp vô hạn khiến Next.js trả 404/502**.
2. Cloudlocal (Docker nginx) không chạy hoặc cổng 80 chưa mở ra Internet → Vercel rewrite tới IP công khai → lỗi mạng.
3. Đường dẫn double prefix: `NEXT_PUBLIC_ATE_API_ORIGIN` chứa `/api/v1/` + code thêm `/api/...` ⇒ `/api/v1/api/auth/login` → **404 Not Found** (đã kiểm chứng bằng test thật).

### III. Diagnostics (đã thực thi trên máy)
| Test | Kết quả |
|---|---|
| `GET http://localhost:8005/health` | ✅ `200 status UP` (backend OK) |
| `GET http://localhost:8005/api/status` | ✅ `200 LIVE_VERIFIED` (MT5 Exness-MT5Trial7) |
| `POST http://localhost:8005/api/v1/api/auth/login` | ❌ **404** (chứng minh double-prefix) |
| `GET https://autonomous-...vercel.app/api/status` | ❌ **404/401** (rewrite loop/sai URL) |

### IV. Quick Fix (khôi phục ngay)
1. **Đảm bảo cloudlocal (Docker nginx) đang chạy** và IP/DDNS công khai có port 80 mở:
   ```cmd
   cd Cloudlocal; docker compose -p cloudlocal up -d --build
   Start-Process "http://localhost:80/health"
   ```
2. **Đổi env Vercel** rồi **Redeploy**:
   ```
   ATE_BACKEND_URL = http://<PUBLIC_IP>:80          (KHÔNG /api/v1, KHÔNG vercel.app)
   NEXT_PUBLIC_ATE_API_ORIGIN = (trống)
   NEXT_PUBLIC_QUANTAI_API_ORIGIN = (trống)
   ```
3. Test lại từ PowerShell (timeout 15s):
   ```powershell
   Invoke-RestMethod http://localhost:80/api/status
   Invoke-RestMethod https://<endpoint>/api/status
   ```

### V. Permanent Fix
- Mở Internet bằng **Public IP tĩnh hoặc DDNS + port-forward cổng 80** (xem mục 4) — KHÔNG dùng ngrok/Cloudflare Tunnel.
- Loại bỏ double-prefix: giữ chuẩn base URL (xem mục 2) trên cả `.env`, `docker-compose`, Vercel.
- Triển khai chuẩn Docker Cloudlocal (mục 5) để nginx/FastAPI/ai-engine chạy ổn định, healthcheck giám sát.

### VI. Commands — toàn bộ chuỗi lệnh
```powershell
# 1. Kiểm tra backend & MT5 cục bộ
Invoke-RestMethod http://localhost:8005/health
Invoke-RestMethod http://localhost:8005/api/status | Select generated_at, mt5_connected, balance

# 2. Kiểm tra endpoint công khai (đổi <endpoint>)
Invoke-WebRequest https://<endpoint>/api/status -UseBasicParsing

# 3. Kiểm tra Vercel rewrite
Invoke-WebRequest https://autonomous-trading-engine.vercel.app/api/status -UseBasicParsing

# 4. Xem log backend docker
docker compose -f Cloudlocal/docker-compose.yml logs -f fastapi nginx

# 5. Xem log EA telemetry (trong MT5 → Experts tab / file Experts log)
Get-Content "$env:APPDATA\MetaQuotes\Terminal\C3DCCD4DFDD81FF8F00FFC310CAC0FD8\Logs" | Select-String -Pattern 'QuantAI'
```

---

## 9. CHECKLIST KIỂM TRA END-TO-END

- [ ] `docker compose ps` — toàn bộ `running`, healthcheck ok (nginx, fastapi, ai-engine, postgres, redis).
- [ ] `Invoke-RestMethod http://localhost:8080/api/status` → `data_status=LIVE_VERIFIED`.
- [ ] `https://<public-endpoint>/api/status` từ ngoài → 200.
- [ ] `https://autonomous-...vercel.app/api/status` → 200 (đã rewrite).
- [ ] Login website thành công (không nhảy lỗi 8005).
- [ ] EA `INIT_OK` + `TELEMETRY_OK` trong Journal MT5.
- [ ] EA `claim` được: đặt 1 `POST /api/v1/demo/scan` → command `CLAIMED` → `EXECUTED` + receipt.
- [ ] Website hiển thị status realtime (balance, spread, positions) và AI signal.

---

## 10. BẢNG THAM CHIẾU PORT & ENDPOINT

| Port | Dịch vụ | Ghi chú |
|---|---|---|
| 80 | nginx (public gateway) | mở ra internet |
| 8080 | socat + nginx (alias) | port exposer |
| 3000 | Next.js | host port (nếu cần) |
| 8005 | FastAPI | **backend chính** — không nên mở thẳng internet |
| 8006 | AI Engine | internal |
| 8007 | Python Bridge | internal / optional |
| 5432 / 6379 | Postgres / Redis | **tuyệt đối không expose** |

---

## 11. BẢO MẬT

- Chỉ mở `80/443` ra internet; **không mở** 8005 hay 5432/6379 trực tiếp.
- `QUANTAI_BRIDGE_TOKEN` mạnh ≥ 32 hex `openssl rand -hex 32`; đổi thường xuyên.
- `ADMIN_PASSWORD` mạnh; auth server-side.
- Nếu có thể: whitelist IP nguồn ở router (hoặc mức firewall nginx).
- Không log token/password (server đã bọc `secrets.compare_digest`).

---

## 12. ROLLBACK & KHÔI PHỤC

```cmd
# Dừng stack
cd Cloudlocal; docker compose down

# Xoá volumes (CẢNH BÁO: mất toàn bộ dữ liệu DB) — chỉ khi cần reset dữ liệu:
docker compose down -v

# Khôi phục cấu hình cũ (git)
git checkout -- .env.example Cloudlocal/.env.template web/next.config.ts

# Chạy lại backend native (phương án dự phòng không Docker)
start.ps1
```

---

© 2026 QTusdev — GoldQuant AI. Dùng nội bộ.