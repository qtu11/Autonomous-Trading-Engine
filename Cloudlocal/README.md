# Cloudlocal Trading Engine - Local Cloud for MT5-Website Bridge

Transform your Windows PC into a local cloud server that bridges MetaTrader 5 with your Vercel-deployed website. No ngrok, no third-party tunnels - direct public IP access.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        INTERNET / PUBLIC IP                         │
│                              (YOUR_PUBLIC_IP)                       │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      WINDOWS HOST (Your PC)                         │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    DOCKER ENGINE                            │   │
│  │  ┌─────────────────────────────────────────────────────┐    │   │
│  │  │              NGINX REVERSE PROXY (Port 80)          │    │   │
│  │  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │    │   │
│  │  │  │ Next.js │ │ FastAPI │ │AI Engine│ │MT5 Bridge│   │    │   │
│  │  │  │ (3000)  │ │ (8005)  │ │ (8006)  │ │ (8007)  │   │    │   │
│  │  │  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘   │    │   │
│  │  │       │         │         │         │          │    │   │
│  │  │       ▼         ▼         ▼         ▼          │    │   │
│  │  │  ┌─────────────────────────────────────────────┐  │    │   │
│  │  │  │         SHARED VOLUMES                      │  │    │   │
│  │  │  │  Logs | Models | History | Config | DB      │  │    │   │
│  │  │  └─────────────────────────────────────────────┘  │    │   │
│  │  └─────────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│                              ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              METATRADER 5 (Windows Native)                  │   │
│  │  - Terminal64.exe                                           │   │
│  │  - MT5 Python Bridge (via shared volume)                    │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

## Signal Flow

```
Vercel Website (Cloud)                    Your PC (Local Cloud)
─────────────────────                     ───────────────────
     │                                         │
     │  POST /api/v1/signal (BUY/SELL)        │
     ├────────────────────────────────────────►│
     │                                         │  Nginx (Port 80)
     │                                         │       │
     │                                         ▼       ▼
     │                              FastAPI (8005) ──► Python Bridge (8007)
     │                                         │              │
     │                                         │         MT5 DLL
     │                                         │              │
     │                                         ◄──────────────┘
     │  Response: {success, ticket, price}     │
     ◄─────────────────────────────────────────┤
     │                                         │
     │  GET /api/v1/market/tick (Polling/WS)   │
     ├────────────────────────────────────────►│
     │                                         │
     │  Response: {bid, ask, spread, time}     │
     ◄─────────────────────────────────────────┤
```

## Quick Start

### 1. Prerequisites
- Windows 10/11 Pro/Enterprise
- Docker Desktop installed and running
- MetaTrader 5 installed at `C:\Program Files\MetaTrader 5\terminal64.exe`
- Public IP address (static preferred, or use DDNS)

### 2. Configure Environment
```powershell
cd Cloudlocal
copy .env.template .env
notepad .env
```

**Required values in `.env`:**
```env
PUBLIC_IP=YOUR_ACTUAL_PUBLIC_IP      # Critical! Get from https://api.ipify.org
MT5_LOGIN=12345678
MT5_PASSWORD=your_mt5_password
MT5_SERVER=YourBroker-Demo
QUANTAI_BRIDGE_TOKEN=openssl_rand_hex_32
ADMIN_PASSWORD=secure_admin_password
```

### 3. Install as Windows Service (Auto-start on boot)
```powershell
# Run PowerShell as Administrator
.\scripts\install-windows-service.ps1
```

This creates a Task Scheduler job that runs on system startup (SYSTEM account, highest privileges).

### 4. Configure Firewall & Port Forwarding
```powershell
# Run PowerShell as Administrator
.\scripts\setup-firewall-portforward.ps1
```

Or manually forward these ports on your router:
| External Port | Internal IP | Internal Port | Protocol |
|---------------|-------------|---------------|----------|
| 80            | YOUR_LOCAL_IP | 80          | TCP      |
| 443           | YOUR_LOCAL_IP | 443         | TCP      |
| 8005          | YOUR_LOCAL_IP | 8005        | TCP      |
| 8006          | YOUR_LOCAL_IP | 8006        | TCP      |
| 8007          | YOUR_LOCAL_IP | 8007        | TCP      |
| 8080          | YOUR_LOCAL_IP | 8080        | TCP      |

### 5. Start Manually (First Time)
```cmd
.\scripts\start-cloudlocal.bat
```

### 6. Verify Health
```cmd
.\scripts\health-check.bat
```

### 7. Monitor Real-time
```powershell
.\scripts\monitor-cloudlocal.ps1
```

## Vercel Configuration

In your Vercel project settings, add this environment variable:

```
ATE_BACKEND_URL=http://YOUR_PUBLIC_IP:80
```

**NOT** `https://autonomous-trading-engine.vercel.app` - that would create an infinite loop!

## API Endpoints

### Website → MT5 (via Vercel → Your Public IP)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/order` | Execute trade (BUY/SELL/CLOSE) |
| GET | `/api/v1/market/tick` | Get current bid/ask |
| GET | `/api/v1/account` | Get account info |
| GET | `/api/v1/positions` | Get open positions |
| WS | `/ws` | Real-time market data |

### Bridge Authentication
All mutating endpoints require header:
```
Authorization: Bearer YOUR_QUANTAI_BRIDGE_TOKEN
```

## Container Ports

| Service | Internal Port | External (Nginx) | Direct Access |
|---------|---------------|------------------|---------------|
| Nginx | 80 | 80 | http://PUBLIC_IP:80 |
| Next.js | 3000 | 80/ | http://PUBLIC_IP:3000 |
| FastAPI | 8005 | 80/api/ | http://PUBLIC_IP:8005 |
| AI Engine | 8006 | 80/ai/ | http://PUBLIC_IP:8006 |
| MT5 Bridge | 8007 | 80/bridge/ | http://PUBLIC_IP:8007 |
| PostgreSQL | 5432 | - | localhost only |
| Redis | 6379 | - | localhost only |

## Management Commands

```cmd
# Start all services
.\scripts\start-cloudlocal.bat

# Stop all services
.\scripts\stop-cloudlocal.bat

# Health check
.\scripts\health-check.bat

# Real-time monitor
powershell -ExecutionPolicy Bypass -File .\scripts\monitor-cloudlocal.ps1

# View logs
docker-compose logs -f fastapi
docker-compose logs -f python-bridge

# Restart single service
docker-compose restart fastapi

# Update and rebuild
docker-compose pull
docker-compose build --no-cache
docker-compose up -d
```

## Troubleshooting

### MT5 Not Connecting
1. Verify MT5 is running and logged in
2. Check `MT5_PATH` in `.env` points to `terminal64.exe`
3. Check bridge logs: `docker-compose logs python-bridge`
4. Ensure MT5 allows DLL imports: Tools → Options → Expert Advisors → "Allow WebRequest for listed URL"

### Website Can't Reach API
1. Verify `PUBLIC_IP` in `.env` matches your actual public IP
2. Check port forwarding on router (port 80 → local IP:80)
3. Test locally: `curl http://localhost/health`
4. Test externally: `curl http://YOUR_PUBLIC_IP/health`

### Docker Containers Keep Restarting
```cmd
docker-compose logs fastapi
# Check for Python import errors, missing dependencies
```

### Windows Firewall Blocking
```powershell
# Run as Admin
.\scripts\setup-firewall-portforward.ps1 -ShowOnly
# Verify rules exist for ports 80, 8005, 8006, 8007, 8080
```

## Security Notes

- **Never expose PostgreSQL/Redis ports (5432, 6379) to internet**
- Use strong `QUANTAI_BRIDGE_TOKEN` (32+ hex chars)
- Use strong `ADMIN_PASSWORD`
- Consider IP whitelisting on router for port 80
- Enable Windows Firewall logging for audit

## Auto-Start Verification

After reboot, verify:
```powershell
Get-ScheduledTask -TaskName "Cloudlocal-Trading-Engine"
docker-compose ps
```

## Logs Location

```
Cloudlocal/
├── volumes/
│   ├── logs/
│   │   ├── nginx/
│   │   ├── fastapi/
│   │   ├── python-bridge/
│   │   ├── ai-engine/
│   │   └── nextjs/
│   ├── models/
│   ├── history/
│   └── config/
```

## License

Internal use only - GoldQuant AI Trading System