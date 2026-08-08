# ATE SYSTEM ANALYSIS - LỖI VÀ KẾ HOẠCH FIX

## TÓM TẮT VẤN ĐỀ

### Vấn đề hiện tại:
- Frontend Vercel không thể kết nối đến Backend Docker local
- Nguyên nhân gốc: Vercel (HTTPS) không thể gọi HTTP endpoint của backend
- MT5 EA gọi đến `https://autonomous-trading-engine.vercel.app/api/v1/` - cần backend response đúng

---

## 1. KIẾN TRÚC HIỆN TẠI (BROKEN)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  FRONTEND (Vercel - HTTPS)                                                │
│  https://autonomous-trading-engine.vercel.app                              │
│  └── /api/* -> PROBLEM: Cannot reach HTTP backend                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ✗ 502/Timeout
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│  BACKEND (Docker - HTTP)                                                  │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐                     │
│  │   nginx    │  │   fastapi    │  │  python-     │                     │
│  │  :8848     │──│    :8005     │──│  bridge:8007 │                     │
│  │  (HTTP)    │  │              │  │              │                     │
│  └─────────────┘  └──────────────┘  └──────────────┘                     │
│       ↑                                                                      │
│  Port Forward                                                            │
│  113.173.192.226:8848 ──────────────────────────────────────────────► │
│  (VNPT WAN)                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  MT5 EA (Windows)                                                        │
│  InpApiUrl = "https://autonomous-trading-engine.vercel.app/api/v1/"       │
│  InpBridgeToken = "20022007@Tu"                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ✓ HTTPS
                                    ↓
                         ┌───────────────────┐
                         │  Vercel Frontend  │
                         │  (Currently 502) │
                         └───────────────────┘
                                    ✗
                                    ↓
                         ┌───────────────────┐
                         │  Docker Backend   │
                         │  (Not reachable) │
                         └───────────────────┘
```

---

## 2. VẤN ĐỀ CHI TIẾT

### 2.1 API Path Mismatch

| Component | Expected Path | Actual Path | Status |
|-----------|--------------|------------|--------|
| Frontend Login | `/api/auth/login` | `/api/auth/login` | ❌ Fails |
| Frontend Status | `/api/status` | `/api/status` | ❌ Fails |
| MT5 Claim | `/api/v1/bridge/commands/claim` | `/api/v1/bridge/commands/claim` | ❌ Fails |
| MT5 Receipt | `/api/v1/bridge/commands/{id}/receipt` | `/api/v1/bridge/commands/{id}/receipt` | ❌ Fails |

### 2.2 Backend Login Request Schema

**Frontend sends:**
```json
{
  "login": "qtusdev@quanttrading.ai",
  "password": "qtusdev07"
}
```

**Backend expects (from server.py):**
```python
class LoginRequest(BaseModel):
    login: str
    password: str
```

**Backend admin credentials from .env:**
```
ADMIN_LOGIN=qtusdev@quanttrading.ai
ADMIN_PASSWORD=qtusdev07
```

**Status:** ✅ Schema match

### 2.3 CORS Configuration

**Backend CORS (server.py):**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://autonomous-trading-engine.vercel.app",
        "http://113.173.192.226:8848",  # WAN IP
        "http://113.173.29.210:8848",    # Old WAN IP
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Status:** ✅ CORS configured

### 2.4 Authentication Tokens

**Bridge Token:**
```
QUANTAI_BRIDGE_TOKEN=20022007@Tu
```

**MT5 EA Header:**
```
Authorization: Bearer 20022007@Tu
```

**Status:** ✅ Token match

---

## 3. ROOT CAUSE ANALYSIS

### 3.1 Primary Issue: Vercel Cannot Reach HTTP Backend

**Problem:**
- Vercel runs on HTTPS
- Backend Docker runs on HTTP (port 8848)
- Vercel Edge Functions and rewrites do NOT support forwarding to HTTP backends

**Evidence:**
```
curl -X POST https://autonomous-trading-engine.vercel.app/api/auth/login
-> 502 Bad Gateway

curl http://113.173.192.226:8848/api/auth/login
-> {"status": "SUCCESS", "token": "...", "user": {...}}
```

### 3.2 Secondary Issue: Frontend Code References

**web/app/login/page.tsx:**
```typescript
const BACKEND_URL = process.env.NEXT_PUBLIC_ATE_BACKEND_URL || 'http://113.173.192.226:8848';
const endpoint = `${BACKEND_URL}/api/auth/login`;
```

**Problem:** `NEXT_PUBLIC_ATE_BACKEND_URL` is NOT set in Vercel environment variables

**Fix Required:** Set `NEXT_PUBLIC_ATE_BACKEND_URL=https://autonomous-trading-engine.vercel.app/api` in Vercel and make Next.js API routes proxy requests

---

## 4. SOLUTION DESIGN

### 4.1 Architecture After Fix

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  FRONTEND (Vercel - HTTPS)                                                │
│  https://autonomous-trading-engine.vercel.app                              │
│                                                                            │
│  Next.js API Routes (SSR - can call HTTP):                                │
│  /api/auth/login      -> proxy to Backend /api/auth/login                  │
│  /api/status          -> proxy to Backend /api/status                      │
│  /api/v1/*            -> proxy to Backend /api/v1/*                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ✓ Internal call
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│  BACKEND (Docker - HTTP)                                                  │
│  nginx :8848 -> fastapi :8005                                             │
│                                                                            │
│  Docker network: host.docker.internal:8005                                 │
│  Public: 113.173.192.226:8848                                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ✓ HTTPS
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│  MT5 EA (Windows)                                                        │
│  InpApiUrl = "https://autonomous-trading-engine.vercel.app/api/v1/"       │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Key Changes Required

1. **Create Next.js API Routes** to proxy all requests from HTTPS frontend to HTTP backend
2. **Update frontend code** to call `/api/*` instead of backend URL directly
3. **MT5 EA** keeps calling Vercel URL - works automatically

---

## 5. FILE CHANGES REQUIRED

### 5.1 New Files to Create

| File | Purpose |
|------|---------|
| `web/pages/api/auth/login.ts` | Proxy login requests |
| `web/pages/api/status.ts` | Proxy status requests |
| `web/pages/api/v1/bridge/commands/claim.ts` | Proxy MT5 claim |
| `web/pages/api/v1/bridge/commands/[id]/receipt.ts` | Proxy MT5 receipt |
| `web/pages/api/v1/bridge/markup.ts` | Proxy chart markup |
| `web/pages/api/v1/bridge/candles.ts` | Proxy candle push |
| `web/pages/api/v1/bridge/calendar.ts` | Proxy calendar push |
| `web/pages/api/control-center/status.ts` | Proxy control center |
| `web/pages/api/control-center/kill-switch.ts` | Proxy kill switch |
| `web/pages/api/control-center/demo-arm.ts` | Proxy demo arm |
| `web/pages/api/control-center/mode.ts` | Proxy mode |
| `web/pages/api/control-center/login-mt5.ts` | Proxy MT5 login |
| `web/pages/api/control-center/risk.ts` | Proxy risk config |
| `web/pages/api/control-center/ai-config.ts` | Proxy AI config |
| `web/pages/api/control-center/telegram.ts` | Proxy Telegram |
| `web/pages/api/control-center/trading-method.ts` | Proxy trading method |
| `web/pages/api/control-center/ai-loop.ts` | Proxy AI loop |
| `web/pages/api/order/buy.ts` | Proxy buy order |
| `web/pages/api/order/sell.ts` | Proxy sell order |
| `web/pages/api/order/close.ts` | Proxy close |
| `web/pages/api/order/close_all.ts` | Proxy close all |
| `web/pages/api/order/modify_tpsl.ts` | Proxy modify |
| `web/pages/api/brain.ts` | Proxy brain state |
| `web/pages/api/brain/adjustments/[id].ts` | Proxy brain adjustment |
| `web/pages/api/copilot/chat.ts` | Proxy copilot chat |
| `web/pages/api/market.ts` | Proxy market data |
| `web/pages/api/positions.ts` | Proxy positions |
| `web/pages/api/history.ts` | Proxy history |
| `web/pages/api/pending-orders.ts` | Proxy pending |
| `web/pages/api/logs.ts` | Proxy logs |
| `web/pages/api/economic-calendar.ts` | Proxy calendar |
| `web/pages/api/telemetry.ts` | Proxy telemetry |
| `web/pages/api/reset_all.ts` | Proxy reset |
| `web/pages/api/news/analyze.ts` | Proxy news |
| `web/pages/api/ai/test.ts` | Proxy AI test |
| `web/pages/api/telegram/test_morning_news.ts` | Proxy test |
| `web/pages/api/telegram/test_evening_pnl.ts` | Proxy test |

### 5.2 Files to Modify

| File | Change |
|------|--------|
| `web/app/login/page.tsx` | Change BACKEND_URL to /api/* (use Next.js routes) |
| `web/app/page.tsx` | Change all API calls to use /api/* |
| `web/app/components/ControlCenter.tsx` | Change all API calls to use /api/* |
| `web/lib/api.ts` | Change baseURL to '' (use relative paths) |
| `web/vercel.json` | Remove rewrites (not needed) |

### 5.3 Configuration Changes

| Setting | Value |
|---------|-------|
| `ATE_BACKEND_URL` | `http://113.173.192.226:8848` (in Cloudlocal .env) |
| Vercel Environment | No change needed (uses Next.js API routes) |

---

## 6. IMPLEMENTATION ORDER

### Phase 1: Core API Routes
1. Create `/api/auth/login.ts`
2. Create `/api/status.ts`
3. Test login flow works

### Phase 2: MT5 Bridge Routes
4. Create `/api/v1/bridge/commands/claim.ts`
5. Create `/api/v1/bridge/commands/[id]/receipt.ts`
6. Create `/api/v1/bridge/markup.ts`
7. Create `/api/v1/bridge/candles.ts`
8. Create `/api/v1/bridge/calendar.ts`

### Phase 3: Control Center Routes
9. Create all `/api/control-center/*` routes
10. Create all `/api/order/*` routes
11. Create `/api/brain.ts`
12. Create `/api/copilot/chat.ts`

### Phase 4: Frontend Updates
13. Update `web/lib/api.ts` baseURL
14. Update `web/app/page.tsx` API calls
15. Update `web/app/components/ControlCenter.tsx` API calls

### Phase 5: Testing & Deployment
16. Deploy to Vercel
17. Test login
18. Test MT5 connection
19. Test dashboard

---

## 7. SECURITY CONSIDERATIONS

### 7.1 API Keys Not Exposed
- Bridge token passed from MT5 EA
- Admin token issued by backend
- No sensitive keys in frontend code

### 7.2 CORS Configuration
- Backend already configured with Vercel domain
- MT5 EA calls Vercel (allowed origin)

### 7.3 Rate Limiting
- Nginx already has rate limiting
- Next.js API routes inherit Vercel DDoS protection

---

## 8. ROLLBACK PLAN

If deployment fails:
1. Revert git commit
2. Vercel auto-reverts
3. System returns to broken-but-stable state

---

## 9. DEPENDENCIES

### Backend (Docker)
- Port 8848 must be accessible from internet
- Port forward configured on VNPT router
- nginx running and healthy

### Frontend (Vercel)
- Next.js API routes enabled (default)
- No special Vercel configuration needed

### MT5 EA
- No changes needed
- Already points to Vercel URL

---

## 10. VERIFICATION CHECKLIST

After deployment:
- [ ] Login page shows no error
- [ ] Login succeeds with admin credentials
- [ ] Dashboard loads with real data
- [ ] Control center loads settings
- [ ] MT5 EA can claim commands
- [ ] MT5 EA can send receipts
- [ ] WebSocket connection works
- [ ] Telegram notifications work
