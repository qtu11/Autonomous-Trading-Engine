@echo off
REM Cloudlocal Trading Engine - Health Check & Monitor

cd /d "%~dp0.."

echo =============================================
echo  Cloudlocal Health Check
echo =============================================
echo.

echo [1/5] Container Status:
docker-compose ps
echo.

echo [2/5] Service Health Endpoints:
echo.

echo Checking Nginx (port 80)...
curl -s -o nul -w "  HTTP %{http_code} - %{time_total}s\n" http://localhost/health --max-time 5 2>nul || echo "  FAILED - Nginx not responding"

echo Checking FastAPI (port 8005)...
curl -s -o nul -w "  HTTP %{http_code} - %{time_total}s\n" http://localhost:8005/health --max-time 5 2>nul || echo "  FAILED - FastAPI not responding"

echo Checking AI Engine (port 8006)...
curl -s -o nul -w "  HTTP %{http_code} - %{time_total}s\n" http://localhost:8006/health --max-time 5 2>nul || echo "  FAILED - AI Engine not responding"

echo Checking Python Bridge (port 8007)...
curl -s -o nul -w "  HTTP %{http_code} - %{time_total}s\n" http://localhost:8007/health --max-time 5 2>nul || echo "  FAILED - Python Bridge not responding"

echo Checking Next.js (port 3000)...
curl -s -o nul -w "  HTTP %{http_code} - %{time_total}s\n" http://localhost:3000 --max-time 5 2>nul || echo "  FAILED - Next.js not responding"

echo.
echo [3/5] MT5 Connection:
curl -s http://localhost:8007/api/v1/account --max-time 5 2>nul | findstr /r "login balance equity" >nul && echo "  MT5 Connected" || echo "  MT5 NOT CONNECTED"

echo.
echo [4/5] Redis:
docker exec cloudlocal-redis redis-cli ping 2>nul || echo "  Redis not responding"

echo.
echo [5/5] PostgreSQL:
docker exec cloudlocal-postgres pg_isready -U quantai 2>nul || echo "  PostgreSQL not responding"

echo.
echo =============================================
echo  Resource Usage:
echo =============================================
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"
echo.

pause