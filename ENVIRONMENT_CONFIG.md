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

## Verify

MT5 logs sẽ show:
```
CLAIM_TRY: ... url=https://autonomous-trading-engine.vercel.app/api/v1/bridge/commands/claim
CLAIM_RESULT: HTTP=200 result_size=XX err=0  ← OK!
```

Nếu `err=4014` → Backend không phản hồi, kiểm tra:
1. Home server có đang chạy không?
2. Port 8848 có mở không?
3. Firewall có cho phép không?
