@echo off
REM Cloudlocal Trading Engine - Quick Start Script
REM Run this to start all containers

cd /d "%~dp0.."

echo =============================================
echo  Cloudlocal Trading Engine - Starting...
echo =============================================
echo.

REM Check Docker
docker --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker not found. Install Docker Desktop first.
    pause
    exit /b 1
)

docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: docker-compose not found.
    pause
    exit /b 1
)

REM Check .env exists
if not exist .env (
    echo WARNING: .env not found. Copying from template...
    copy .env.template .env
    echo Please edit .env with your credentials and run again.
    pause
    exit /b 1
)

REM Create log directories
if not exist volumes\logs\nginx mkdir volumes\logs\nginx
if not exist volumes\logs\nextjs mkdir volumes\logs\nextjs
if not exist volumes\logs\fastapi mkdir volumes\logs\fastapi
if not exist volumes\logs\ai-engine mkdir volumes\logs\ai-engine
if not exist volumes\logs\python-bridge mkdir volumes\logs\python-bridge
if not exist volumes\logs\nginx mkdir volumes\logs\nginx

echo Starting containers...
docker-compose up -d --remove-orphans

echo.
echo Waiting for services to be healthy...
timeout /t 10 /nobreak >nul

echo.
echo =============================================
echo  Cloudlocal Status
echo =============================================
docker-compose ps

echo.
echo Public Access URLs (replace YOUR_PUBLIC_IP in .env):
echo   Website:     http://YOUR_PUBLIC_IP:80
echo   API:         http://YOUR_PUBLIC_IP:80/api/v1
echo   Bridge:      http://YOUR_PUBLIC_IP:80/bridge
echo   WebSocket:   ws://YOUR_PUBLIC_IP:80/ws
echo   AI Engine:   http://YOUR_PUBLIC_IP:80/ai
echo.
echo Vercel ATE_BACKEND_URL: http://YOUR_PUBLIC_IP:80
echo.
echo Logs: tail -f volumes/logs/*/*.log
echo.
pause