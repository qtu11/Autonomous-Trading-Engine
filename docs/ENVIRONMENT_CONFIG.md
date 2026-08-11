# 🌐 Environment Configuration Guide

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DEPLOYMENT ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   ┌─────────────┐         ┌──────────────────────────────────────┐ │
│   │   BROWSER  │────────►│          VERCEL (Frontend)           │ │
│   │  (Client)  │         │  https://autonomous-trading-engine.   │ │
│   └─────────────┘         │         vercel.app/                   │ │
│                           └──────────────────────────────────────┘ │
│                                          │                           │
│                                          │ /backend/*               │
│                                          ▼                           │
│                           ┌──────────────────────────────────────┐ │
│                           │          VERCEL (Backend)             │ │
│                           │  https://autonomous-trading-engine.   │ │
│                           │     vercel.app/backend/*              │ │
│                           │          (FastAPI Docker)             │ │
│                           └──────────────────────────────────────┘ │
│                                          │                           │
│                                          │ Internal call            │
│                                          ▼                           │
│                           ┌──────────────────────────────────────┐ │
│                           │       HOME SERVER (Docker)            │ │
│                           │        192.168.1.12:8848             │ │
│                           │      MT5 Terminal + FastAPI           │ │
│                           └──────────────────────────────────────┘ │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Standard URLs

| Environment | URL |
|-------------|-----|
| **Website** | `https://autonomous-trading-engine.vercel.app/` |
| **Backend** | `https://autonomous-trading-engine.vercel.app/backend` |
| **API/v1** | `https://autonomous-trading-engine.vercel.app/api/v1` |

## Environment Files

### 1. Vercel Dashboard (Backend)
File: **vercel.json** in `web/`

```json
{
  "env": {
    "ATE_BACKEND_URL": "https://autonomous-trading-engine.vercel.app/backend",
    "ATE_FRONTEND_URL": "https://autonomous-trading-engine.vercel.app",
    "NEXT_PUBLIC_ATE_API_ORIGIN": "https://autonomous-trading-engine.vercel.app"
  }
}
```

### 2. Frontend Production
File: **web/.env.production**

```env
NEXT_PUBLIC_ATE_API_ORIGIN=https://autonomous-trading-engine.vercel.app
ATE_BACKEND_URL=https://autonomous-trading-engine.vercel.app/backend
```

### 3. Frontend Local Dev
File: **web/.env.local**

```env
NEXT_PUBLIC_ATE_API_ORIGIN=http://localhost:8005
ATE_BACKEND_URL=http://localhost:8005
```

### 4. Home Server Backend
File: **Docker/Cloudlocal/.env**

```env
ATE_BACKEND_URL=http://192.168.1.12:8848
ATE_FRONTEND_URL=https://autonomous-trading-engine.vercel.app
```

## API URL Flow

### Browser → Frontend (Vercel)
```
https://autonomous-trading-engine.vercel.app/
```

### Frontend → Backend (via API Routes)
```typescript
// web/pages/api/market.ts
const res = await fetch(`${process.env.ATE_BACKEND_URL}/api/market`, ...);
```

### MT5 EA → Backend (via /api/v1/*)
```
MT5 EA → /api/v1/telemetry → Vercel Rewrite → 192.168.1.12:8848/api/v1/telemetry
```

## Variable Reference

| Variable | Purpose | Production Value |
|----------|---------|-----------------|
| `ATE_BACKEND_URL` | Backend API base URL | `https://autonomous-trading-engine.vercel.app/backend` |
| `ATE_FRONTEND_URL` | Frontend URL | `https://autonomous-trading-engine.vercel.app` |
| `NEXT_PUBLIC_ATE_API_ORIGIN` | Public API origin for frontend | `https://autonomous-trading-engine.vercel.app` |
| `ATE_MT5_API` | MT5 API endpoint | `https://autonomous-trading-engine.vercel.app/api/v1` |

## CORS Configuration

Backend (server.py) CORS:
```python
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://autonomous-trading-engine.vercel.app"
]
```

## Next.js Rewrites

```typescript
// next.config.ts
{
  source: '/api/v1/:path*',
  destination: `${ATE_BACKEND_URL}/api/v1/:path*`
}
```

## Deployment Checklist

- [ ] Set `ATE_BACKEND_URL` in Vercel dashboard to backend URL
- [ ] Set `NEXT_PUBLIC_ATE_API_ORIGIN` in Vercel dashboard
- [ ] Update `ATE_ALLOWED_ORIGINS` with production domain
- [ ] Deploy frontend to Vercel
- [ ] Deploy backend Docker to home server
- [ ] Test MT5 EA connection
- [ ] Test browser connection

## Troubleshooting

### CORS Error
→ Check `ATE_ALLOWED_ORIGINS` includes your domain

### 404 on API calls
→ Check `ATE_BACKEND_URL` is correct and backend is running

### MT5 can't connect
→ Check `/api/v1/*` rewrites are configured in Vercel
