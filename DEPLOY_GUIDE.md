# =======================================================================
# GOLDQUANT AI BLOOMBERG TRADING DESK - DEPLOYMENT GUIDE
# Author: Nguyễn Quang Tú (QTusdev) | https://github.com/qtu11
# =======================================================================

## URL STRUCTURE (PRODUCTION)

```
Website : https://autonomous-trading-engine.vercel.app/
Backend : https://autonomous-trading-engine.vercel.app/backend
API/v1  : https://autonomous-trading-engine.vercel.app/api/v1
```

---

## DEPLOY STEPS

### Step 1: Deploy Backend to Railway

```bash
# Navigate to dashboard folder
cd C:\Users\KIMPC\AppData\Roaming\MetaQuotes\Terminal\C3DCCD4DFDD81FF8F00FFC310CAC0FD8\MQL5\Experts\tradeAI\dashboard

# Login Railway
railway login

# Init project
railway init

# Add PostgreSQL plugin
railway add postgresql

# Add Redis plugin
railway add redis

# Add Environment Variables (copy from .env.railway)
# IMPORTANT: Set DEMO mode for safety
QUANTAI_EXECUTION_MODE=DEMO
QUANTAI_DEMO_ARMED=true
QUANTAI_LIVE_ARMED=false
QUANTAI_KILL_SWITCH=true

# Deploy
railway up

# Get Railway URL (e.g., https://quantai-api.up.railway.app)
```

### Step 2: Update vercel.json with Railway URL

```bash
cd C:\Users\KIMPC\AppData\Roaming\MetaQuotes\Terminal\C3DCCD4DFDD81FF8F00FFC310CAC0FD8\MQL5\Experts\tradeAI\web
```

Update `vercel.json` with your Railway URL:

```json
{
  "rewrites": [
    {
      "source": "/api/v1/:path*",
      "destination": "https://YOUR-RAILWAY-URL.up.railway.app/api/v1/:path*"
    },
    {
      "source": "/backend/:path*",
      "destination": "https://YOUR-RAILWAY-URL.up.railway.app/backend/:path*"
    }
  ]
}
```

### Step 3: Deploy Frontend to Vercel

```bash
cd C:\Users\KIMPC\AppData\Roaming\MetaQuotes\Terminal\C3DCCD4DFDD81FF8F00FFC310CAC0FD8\MQL5\Experts\tradeAI\web

# Deploy to Vercel
vercel --prod
```

### Step 4: Verify Deployment

Test the endpoints:
- `https://autonomous-trading-engine.vercel.app/health`
- `https://autonomous-trading-engine.vercel.app/api/v1/status`
- `https://autonomous-trading-engine.vercel.app/backend/docs`

---

## LOCAL DEVELOPMENT (DOCKERLOCAL)

```bash
cd C:\Users\KIMPC\AppData\Roaming\MetaQuotes\Terminal\C3DCCD4DFDD81FF8F00FFC310CAC0FD8\MQL5\Experts\tradeAI\Cloudlocal

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f fastapi

# Stop all services
docker-compose down
```

### Local URLs:
- Frontend: http://localhost:3001
- API: http://localhost:8005
- Nginx: http://localhost:8080, http://localhost:8848

---

## PRODUCTION SAFETY CHECKLIST

- [ ] DEMO mode enabled (`QUANTAI_EXECUTION_MODE=DEMO`)
- [ ] Kill switch ON (`QUANTAI_KILL_SWITCH=true`)
- [ ] LIVE arms OFF (`QUANTAI_LIVE_ARMED=false`)
- [ ] MT5 credentials verified
- [ ] Telegram notifications working
- [ ] Health check passing

---

## ENVIRONMENT VARIABLES REFERENCE

### Trading Configuration
| Variable | Default | Description |
|----------|---------|-------------|
| QUANTAI_EXECUTION_MODE | DEMO | DEMO or LIVE |
| QUANTAI_DEMO_ARMED | true | Enable demo trading |
| QUANTAI_LIVE_ARMED | false | Enable live trading |
| QUANTAI_KILL_SWITCH | true | Emergency stop |
| QUANTAI_EXECUTION_SYMBOL | XAUUSDm | Trading symbol |
| QUANTAI_MAGIC_NUMBER | 888999 | EA magic number |

### MT5 Configuration
| Variable | Description |
|----------|-------------|
| MT5_LOGIN | Account number |
| MT5_PASSWORD | Account password |
| MT5_SERVER | Server name |

### Database
| Variable | Default | Description |
|----------|---------|-------------|
| POSTGRES_HOST | (from plugin) | Railway PostgreSQL host |
| POSTGRES_DB | quantai | Database name |
| REDIS_HOST | (from plugin) | Railway Redis host |

### CORS (Vercel Frontend)
```
ATE_ALLOWED_ORIGINS=https://autonomous-trading-engine.vercel.app
QUANTAI_ALLOWED_ORIGINS=https://autonomous-trading-engine.vercel.app
```

---

## TROUBLESHOOTING

### Health Check Failing
```bash
# Check Railway logs
railway logs

# Check if PORT is set correctly
railway variables
```

### CORS Errors
- Verify `ATE_ALLOWED_ORIGINS` includes Vercel URL
- Check browser console for specific origin being blocked

### MT5 Connection Issues
- DEMO account: `433928815 @ Exness-MT5Trial7`
- LIVE account: `257471778 @ Exness-MT5Real36`
- Ensure MT5 terminal is running and logged in

---

## FILE STRUCTURE

```
tradeAI/
├── dashboard/                 # FastAPI Backend (Railway)
│   ├── Dockerfile.railway    # Railway Dockerfile
│   ├── docker-compose.railway.yml
│   ├── railway.json         # Railway config
│   ├── .env.railway         # Railway env vars
│   └── requirements.txt      # Python dependencies
│
├── web/                      # Next.js Frontend (Vercel)
│   ├── vercel.json          # Vercel config + rewrites
│   └── package.json
│
└── Cloudlocal/              # Local Docker Stack
    ├── docker-compose.yml   # Full stack
    ├── nginx/nginx.conf     # Reverse proxy
    └── .env                 # Local env (113.173.29.210:8848)
```

---

**Author**: Nguyễn Quang Tú (QTusdev)
**GitHub**: https://github.com/qtu11
**Last Updated**: 2026-01-17
