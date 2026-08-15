# 🚀 Hướng dẫn Deploy ATE Backend lên VPS VNPT

**Mục tiêu:** Chạy FastAPI backend ở VPS VNPT (`113.173.192.226:8848`), để Vercel frontend có thể proxy qua.

---

## 📋 Kiến trúc sau khi deploy

```
┌────────────────────────────────────────────────────────────────────┐
│ Browser (https://autonomous-trading-engine.vercel.app)            │
│     ↓ fetch('/api/market')                                         │
│ Next.js (Vercel)                                                   │
│     ↓ catch-all proxy: web/app/api/[...path]/route.ts              │
│     ↓ fetch('http://113.173.192.226:8848/api/market')              │
│ FastAPI (VPS VNPT)                                                 │
│     ↓                                                               │
│ SQLite + AI + RiskGate + Command queue                              │
└────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────┐
│ MT5 EA (trên VPS hoặc máy trader)                                  │
│     ↓ WebRequest POST                                               │
│     ↓ Bearer token: 20022007@Tu                                    │
│ 2 lựa chọn:                                                        │
│   A) http://113.173.192.226:8848/api/v1/bridge/candles  (trực tiếp)│
│   B) https://autonomous-trading-engine.vercel.app/api/v1/bridge/... │
│      (qua Vercel proxy)                                            │
└────────────────────────────────────────────────────────────────────┘
```

**Khuyến nghị dùng option A** cho EA (latency thấp hơn, không qua Vercel timeout 10s).

---

## 🔧 Bước 1: SSH vào VPS VNPT

```bash
ssh root@113.173.192.226
# hoặc user bạn đã tạo
ssh ateuser@113.173.192.226
```

---

## 🔧 Bước 2: Cài Docker + Docker Compose

```bash
# Update & cài dependencies
sudo apt update && sudo apt install -y ca-certificates curl gnupg

# Thêm Docker GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Thêm repo
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Cài Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Cho phép user chạy Docker không cần sudo
sudo usermod -aG docker $USER
newgrp docker

# Verify
docker --version
docker compose version
```

---

## 🔧 Bước 3: Upload code lên VPS

### Option A: Git clone (khuyến nghị)
```bash
# Trên VPS
cd /opt
sudo git clone https://github.com/qtu11/ate-backend.git
sudo chown -R $USER:$USER ate-backend
cd ate-backend
```

### Option B: SCP từ máy local
```bash
# Trên máy local (Windows Git Bash)
scp -r ./dashboard root@113.173.192.226:/opt/ate-backend
```

---

## 🔧 Bước 4: Cấu hình .env

```bash
cd /opt/ate-backend
cp .env.example .env
nano .env
```

> **🎯 Drop-in workflow:** Backend tự động nhận diện DEMO/LIVE từ EA telemetry.
> Copy file `.ex5` vào MT5 (chạy bất kỳ tài khoản Demo hay Real) → EA tự gửi
> `account_mode` lên backend → backend tự động set execution_mode tương ứng.
> Bạn KHÔNG cần đổi `ATE_EXECUTION_MODE=LIVE` mỗi lần đổi account.
>
> `ATE_EXECUTION_MODE` chỉ là fallback khi EA chưa kết nối.

**Các giá trị QUAN TRỌNG cần đổi:**

```ini
# MT5 Bridge — phải khớp với InpBridgeToken trong EA
QUANTAI_BRIDGE_TOKEN=<token-random-32-chars>
QUANTAI_OPERATOR_TOKEN=${QUANTAI_BRIDGE_TOKEN}

# Đổi admin password
ADMIN_PASSWORD=mat-khau-cua-ban

# Nếu có OpenAI/Gemini key thì fill vào
OPENAI_API_KEY=sk-...
# Gemini
GEMINI_API_KEY=AIza...
```

Lưu file: `Ctrl+O`, Enter, `Ctrl+X`

---

## 🔧 Bước 5: Build & chạy Docker

```bash
cd /opt/ate-backend
docker compose build
docker compose up -d

# Xem logs
docker compose logs -f api
```

**Output mong đợi:**
```
api  | [INFO] Starting gunicorn
api  | [INFO] Listening at: http://0.0.0.0:8848
api  | [INFO] Booting worker with pid: 7
```

---

## 🔧 Bước 6: Mở firewall port 8848

```bash
# Nếu dùng UFW
sudo ufw allow 8848/tcp
sudo ufw reload

# Nếu dùng iptables
sudo iptables -A INPUT -p tcp --dport 8848 -j ACCEPT

# Nếu dùng firewall khác (CSF, firewalld), mở port 8848 tương ứng
```

---

## 🔧 Bước 7: Test backend từ VPS

```bash
curl http://localhost:8848/health
# Mong đợi: {"status":"ok",...}

curl http://localhost:8848/api/status
# Mong đợi: 401 (cần token) — đúng

curl -X POST http://localhost:8848/api/v1/telemetry \
  -H "Authorization: Bearer 20022007@Tu" \
  -H "Content-Type: application/json" \
  -d '{"ea_version":"1.0","terminal_state":"RUNNING"}'
# Mong đợi: {"ok":true}
```

---

## 🔧 Bước 8: Test từ bên ngoài (máy local)

```bash
# Test health (public)
curl http://113.173.192.226:8848/health

# Test telemetry (với token)
curl -X POST http://113.173.192.226:8848/api/v1/telemetry \
  -H "Authorization: Bearer 20022007@Tu" \
  -H "Content-Type: application/json" \
  -d '{"ea_version":"1.0","terminal_state":"RUNNING"}'
```

Nếu OK → backend đã public.

---

## 🔧 Bước 9: Test Vercel proxy

Mở browser: `https://autonomous-trading-engine.vercel.app/api/health`

Nếu Vercel đã deploy code mới (có `web/app/api/[...path]/route.ts`), request này sẽ proxy về VPS và trả kết quả tương tự `http://113.173.192.226:8848/api/health`.

**Nếu thấy response JSON hợp lệ → proxy hoạt động ✅**

---

## 🔧 Bước 10: Cấu hình MT5 EA

Trong MetaEditor → mở `ATE_XAUUSD.mq5` → compile → mở MT5 → kéo EA vào chart XAUUSD → trong input panel:

| Input | Giá trị |
|---|---|
| `InpApiUrl` | `http://113.173.192.226:8848/api/v1/` ← trực tiếp VPS, latency thấp |
| `InpBridgeToken` | `<token-random>` ← phải khớp QUANTAI_BRIDGE_TOKEN (không có mặc định) |
| `InpMagicNumber` | `888999` ← phải khớp QUANTAI_EXECUTION_MAGIC |
| `InpSymbol` | `XAUUSDm` ← phải khớp QUANTAI_EXECUTION_SYMBOL |

Bấm OK, bật Algo Trading.

---

## 🔧 Bước 11: Verify end-to-end

1. Mở `https://autonomous-trading-engine.vercel.app/` → đăng nhập
2. Vào Control Center → kiểm tra:
   - **EA Connected:** ✅ (xanh)
   - **Account info:** hiển thị balance/equity
3. Vào Chart → phải thấy candles đang chạy
4. Vào AI → phải thấy tín hiệu AI đang phân tích

**Nếu EA Connected = ❌** → check:
- Token khớp chưa
- Port 8848 có mở không
- VPS IP đúng chưa
- EA logs trong MT5 (tab Experts)

---

## 🛑 Troubleshooting

### VPS không start Docker
```bash
sudo systemctl status docker
sudo systemctl start docker
sudo systemctl enable docker
```

### Backend crash liên tục
```bash
docker compose logs api --tail=100
# Thường là do .env sai, port bị chiếm, hoặc thiếu dependency
```

### Port 8848 bị firewall block
- Liên hệ VNPT mở port
- Hoặc dùng port khác (3000, 8080...) và update cả 2 phía

### Vercel proxy timeout
- Vercel free plan timeout = 10s. Nếu AI loop chậm, có thể timeout.
- Fix: tăng plan Vercel hoặc proxy từng endpoint riêng (không dùng catch-all)

### Bridge token mismatch
- VPS .env: `QUANTAI_BRIDGE_TOKEN=ABC`
- EA input: `InpBridgeToken=ABC`
- Nếu khác → 401 từ backend, EA báo "auth failed"

---

## 🔄 Update code

```bash
cd /opt/ate-backend
git pull  # nếu dùng git
docker compose build
docker compose up -d
docker image prune -f  # dọn image cũ
```

---

## 📊 Monitoring

```bash
# Live logs
docker compose logs -f api

# Resource usage
docker stats ate-backend

# Restart service
docker compose restart api

# Stop
docker compose down
```

---

## 🔐 Security checklist

- [ ] Đổi `ADMIN_PASSWORD` trong `.env`
- [ ] Đổi `QUANTAI_BRIDGE_TOKEN` (dùng password mạnh, vd 32 chars random)
- [ ] Đổi `QUANTAI_OPERATOR_TOKEN`
- [ ] Update `InpBridgeToken` trong MT5 EA khớp token mới
- [ ] Đặt `ATE_EXECUTION_MODE=DEMO` cho đến khi verify xong
- [ ] Không commit `.env` lên git (đã có `.gitignore`)
- [ ] Mở port 8848 CHỈ từ IP Vercel + IP cá nhân (nếu firewall cho phép)

---

## ✅ Checklist xong

- [x] Backend FastAPI chạy trên VPS port 8848
- [x] Bridge token khớp giữa EA và backend
- [x] Vercel proxy qua `/api/[...path]` route
- [x] Browser mở `https://autonomous-trading-engine.vercel.app/` thấy chart, account, AI
- [x] EA đẩy data → backend → frontend realtime
- [x] AI loop tạo signals → risk_gate → commands → EA execute