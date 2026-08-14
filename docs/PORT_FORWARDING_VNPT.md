# 🌐 Port Forwarding VNPT — Expose Backend ra Internet

**Mục tiêu:** Để Vercel + MT5 EA truy cập được backend FastAPI trên máy bạn qua IP public VNPT.

> ⚠️ **Cảnh báo bảo mật:** Port forwarding expose máy bạn ra internet. Hãy đảm bảo:
> - Firewall Windows ON
> - `QUANTAI_BRIDGE_TOKEN` đã đổi (không dùng default `20022007@Tu`)
> - `ADMIN_PASSWORD` đã đổi (không dùng default)

---

## 📋 Kiến trúc sau khi setup

```
MT5 EA ────────► Internet ────► VNPT Router ────► 192.168.x.x:8848 ────► Docker Backend
                                                            ↑
Browser ──► vercel.app ──► rewrites ──► ATE_BACKEND_URL=http://<PUBLIC_IP>:8848
```

---

## 🔧 Bước 1: Tìm IP public WAN của router VNPT

Truy cập một trong các trang:
- https://ifconfig.me
- https://api.ipify.org
- https://whatismyip.com

Ghi lại IP public (ví dụ: `113.173.192.226` hoặc IP khác nếu dynamic).

**Quan trọng:** Nếu IP là **dynamic** (VNPT phổ biến), mỗi lần router restart IP sẽ đổi. Bạn cần **DDNS** (Dynamic DNS) để IP luôn trỏ về 1 hostname cố định. Skip DDNS nếu muốn giữ đơn giản trước.

---

## 🔧 Bước 2: Đặt IP tĩnh cho máy của bạn trong LAN

Để port forwarding ổn định, máy backend phải có IP LAN cố định:

```
1. Mở CMD gõ: ipconfig
2. Tìm "IPv4 Address" trong card mạng chính (vd 192.168.1.100)
3. Mở Network & Sharing Center → adapter → Properties → IPv4 → chọn "Use the following"
4. Đặt:
   - IP: 192.168.1.100 (lấy từ bước 1)
   - Subnet: 255.255.255.0
   - Gateway: 192.168.1.1 (router VNPT)
   - DNS: 8.8.8.8 + 8.8.4.4
```

---

## 🔧 Bước 3: Truy cập router VNPT

Mở browser:
```
http://192.168.1.1  (gateway mặc định VNPT)
```

Đăng nhập bằng:
- Username: `admin` (hoặc `adminn` tùy model)
- Password: mặc định thường ở dưới router, hoặc `admin`, `vnpt123`

> Nếu không vào được → gọi VNPT 1800 1234 (miễn phí) nhờ hướng dẫn model router + IP gateway + password admin.

---

## 🔧 Bước 4: Mở port 8848 (NAT/Port Forwarding)

Tùy model router, menu có thể là:
- **NAT** → **Virtual Server**
- **Port Forwarding** → **Add Rule**
- **Firewall** → **Port Mapping**

Ví dụ với VNPT GPON home gateway:

```
Service Name:    ATE-Backend
Protocol:        TCP    (chỉ TCP, không cần UDP)
External Port:   8848
Internal Port:   8848
Internal IP:     192.168.1.100   (IP máy backend)
Status:          Enabled
```

Save → Apply.

---

## 🔧 Bước 5: Mở firewall Windows cho port 8848

```powershell
# Run as Administrator
New-NetFirewallRule -DisplayName "ATE Backend 8848" -Direction Inbound -LocalPort 8848 -Protocol TCP -Action Allow
```

Hoặc qua GUI:
1. Windows Security → Firewall & network protection → Advanced settings
2. Inbound Rules → New Rule
3. Port → TCP → 8848 → Allow → All profiles → Name "ATE Backend"

---

## 🔧 Bước 6: Restart Docker + verify

```bash
# Trên máy backend
cd /opt/ate-backend  # hoặc C:\ate-backend trên Windows
docker compose down
docker compose up -d

# Test trong LAN (từ máy khác trong cùng mạng)
curl http://192.168.1.100:8848/health

# Test qua IP public (từ điện thoại 4G, hoặc browser internet khác)
curl http://<PUBLIC_IP>:8848/health
```

Nếu trả `{"status":"ok",...}` → OK!

---

## 🔧 Bước 7: Update env Vercel

Vào **Vercel Project → Settings → Environment Variables**, sửa:

**XÓA các biến sai:**
- ❌ `ATE_BACKEND_URL=https://autonomous-trading-engine.vercel.app/backend`
- ❌ `ATE_MT5_API=https://autonomous-trading-engine.vercel.app/api/v1`
- ❌ `ATE_DASHBOARD_HOST=0.0.0.0`
- ❌ `ATE_DASHBOARD_PORT=8005`
- ❌ `MT5_*` (3 biến)

**SỬA / THÊM:**
- ✅ `ATE_BACKEND_URL=http://<PUBLIC_IP>:8848`
- ✅ `ATE_MT5_API=http://<PUBLIC_IP>:8848/api/v1`
- ✅ `ATE_EXECUTION_SYMBOL=XAUUSD`

**GIỮ NGUYÊN:**
- `ATE_FRONTEND_URL=https://autonomous-trading-engine.vercel.app`
- `NEXT_PUBLIC_ATE_API_ORIGIN=https://autonomous-trading-engine.vercel.app`
- `NEXT_PUBLIC_FIREBASE_*`
- `ADMIN_LOGIN/PASSWORD`
- `ATE_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,https://autonomous-trading-engine.vercel.app`
- `OPENAI_API_KEY`
- `GEMINI_API_KEY`
- `ATE_AI_MODEL=deepseek-v4-flash-free`
- `ATE_BRIDGE_TOKEN=20022007@Tu`  *(nên đổi thành random 32 chars)*
- `ATE_DEMO_ARMED=true`
- `ATE_DEMO_COMMAND_TTL_SECONDS=10`
- `ATE_ENABLE_TRADING=true`
- `ATE_EXECUTION_MAGIC=888999`
- `ATE_EXECUTION_MODE=LIVE` *(hoặc XÓA — auto-detect)*
- `ATE_KILL_SWITCH=false`
- `ATE_LIVE_ARMED=true`
- `TELEGRAM_*`

---

## 🔧 Bước 8: Update `vercel.json` (repo, không phải Vercel UI)

Commit & push:

```bash
git add web/vercel.json
git commit -m "fix: ATE_BACKEND_URL trỏ về IP public VNPT (port forwarding)"
git push
```

Trong `web/vercel.json`:

```json
{
  "buildCommand": "npm run build",
  "outputDirectory": ".next",
  "framework": "nextjs",
  "rewrites": [
    { "source": "/api/:path*", "destination": "/api/:path*" }
  ],
  "env": {
    "ATE_FRONTEND_URL": "https://autonomous-trading-engine.vercel.app",
    "NEXT_PUBLIC_ATE_API_ORIGIN": "https://autonomous-trading-engine.vercel.app",
    "ATE_BACKEND_URL": "http://113.173.192.226:8848",
    "ATE_BRIDGE_TOKEN": "20022007@Tu",
    "ATE_EXECUTION_MODE": "DEMO",
    "ATE_LIVE_ARMED": "true",
    "ATE_DEMO_ARMED": "true",
    "VERCEL": "1",
    "VERCEL_ENV": "production"
  }
}
```

---

## 🔧 Bước 9: MT5 EA cấu hình

Trong MetaEditor → recompile nếu cần → MT5 → attach EA → input panel:

| Input | Giá trị |
|---|---|
| `InpApiUrl` | `http://<PUBLIC_IP>:8848/api/v1/` |
| `InpBridgeToken` | `20022007@Tu` (khớp `ATE_BRIDGE_TOKEN`) |
| `InpMagicNumber` | `888999` |
| `InpSymbol` | `XAUUSD` |

Bật **Algo Trading** + check MT5 → Tools → Options → Expert Advisors → Allow WebRequest:
- ✅ `http://<PUBLIC_IP>:8848`

---

## ✅ Verification cuối cùng

```bash
# Test 1: Backend LAN
curl http://192.168.1.100:8848/health

# Test 2: Backend public
curl http://<PUBLIC_IP>:8848/health

# Test 3: Vercel proxy
curl https://autonomous-trading-engine.vercel.app/api/health

# Test 4: Vercel → Backend
curl https://autonomous-trading-engine.vercel.app/api/status
# Kỳ vọng: 401 (cần auth) hoặc 200 với data

# Test 5: EA telemetry (từ MT5 đang chạy)
curl -X POST http://<PUBLIC_IP>:8848/api/v1/telemetry \
  -H "Authorization: Bearer 20022007@Tu" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"XAUUSD","account_id":12345,"balance":10000}'
```

**Mở browser** `https://autonomous-trading-engine.vercel.app/` → đăng nhập → thấy chart, account, AI.

---

## ⚠️ Vấn đề với IP động (Dynamic IP)

VNPT hay thay đổi IP public. Nếu mai router restart → IP đổi → mọi URL phía trên sai.

**Giải pháp:**
1. **DDNS miễn phí:** DuckDNS.org → cài client trên máy bạn → hostname cố định `ate-backend.duckdns.org`
2. **Vercel env đổi sang hostname:** `ATE_BACKEND_URL=http://ate-backend.duckdns.org:8848`

Tôi skip DDNS trong guide này để giữ đơn giản. Nếu bạn cần, nói tôi thêm bước.

---

## 🔄 Restart cycle

```bash
# Sau khi đổi .env hoặc code:
cd C:\ate-backend
docker compose restart
curl http://<PUBLIC_IP>:8848/health
```

---

## 🆘 Troubleshooting

| Vấn đề | Kiểm tra |
|---|---|
| Timeout từ bên ngoài | Router chưa forward, hoặc firewall Windows chặn. Test trong LAN trước. |
| 401 Unauthorized | Token EA ≠ backend env. Verify khớp. |
| Vercel 502 | Backend down, hoặc IP public sai. Test `curl http://IP:8848/health` từ server khác. |
| EA "TELEMETRY_HTTP_0" | EA không truy cập được IP. Check allowlist URL trong MT5. |
| Backend down sau restart Docker | Check logs: `docker logs ate-backend`. Có thể port conflict. |

---

## 🔐 Khuyến nghị bảo mật

| Hiện tại | Nên làm |
|---|---|
| `ATE_BRIDGE_TOKEN=20022007@Tu` | Đổi thành random 32+ chars, vd `xK7F3mN9pQ2vR8wT5yB1cL4hG6jD0sA9eZ` |
| `ADMIN_PASSWORD=qtusdev07` | Đổi thành password mạnh hơn (16+ chars) |
| Port 8848 mở cho toàn internet | Có thể restrict bằng firewall Windows cho phép IP Vercel + broker MT5 |
| Backend không HTTPS | OK cho demo; production nên dùng reverse proxy (nginx + Let's Encrypt) |

Tôi KHÔNG tự động đổi các secret mặc định vì sẽ break integration hiện tại. Bạn tự đổi khi sẵn sàng.