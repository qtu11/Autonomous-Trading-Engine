@echo off
chcp 65001 >nul
title ATE_Launcher
color 0B
cls

echo =======================================================================
echo     AUTONOMOUS TRADING ENGINE (ATE) - BLOOMBERG TRADING DESK
echo                          PORT 3005 / 8005
echo =======================================================================
echo.

cd /d "%~dp0"

echo BAN MUON KHOI CHAY HE THONG BANG CHE DO NAO?
echo   [L] Local Service (Chay truc tiep Node.js ^& Python FastAPI tren host Windows)
echo   [D] Docker Compose (Chay toan bo dich vu trong Cloudlocal Docker Containers)
echo =======================================================================
set /p MODE="Nhap lua chon cua ban [L/D] (Mac dinh: L): "

if /i "%MODE%"=="d" goto docker_flow
if /i "%MODE%"=="D" goto docker_flow
goto local_flow

:docker_flow
echo.
echo === KHOI CHAY CHE DO DOCKER COMPOSE ===
echo [1/3] Kiem tra Docker Daemon...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker Desktop chua khoi dong hoac chua cai dat. Vui long bat Docker Desktop va thu lai!
    pause
    exit /b 1
)

echo [2/3] Kiem tra file .env...
if not exist "Cloudlocal\.env" (
    if exist "Cloudlocal\.env.template" (
        copy "Cloudlocal\.env.template" "Cloudlocal\.env" >nul
        echo Da tao file .env tu .env.template
    ) else (
        echo [WARN] Khong tim thay file .env va .env.template trong thu muc Cloudlocal!
    )
)

echo [3/3] Dang khoi chay Docker Compose (Cloudlocal)...
docker compose -f Cloudlocal\docker-compose.yml -p cloudlocal up -d --build
if %errorlevel% neq 0 (
    echo [ERROR] Khong the khoi chay Docker Compose.
    pause
    exit /b 1
)

echo.
echo =======================================================================
echo [SUCCESS] Docker Stack Services active:
echo - Nginx Proxy:           http://localhost:8080
echo - Next.js Frontend:      http://localhost:3001
echo - Backend FastAPI API:   http://localhost:8005
echo =======================================================================
echo.
timeout /t 3 /nobreak >nul
start http://localhost:8080
exit /b 0

:local_flow
echo.
echo === KHOI CHAY CHE DO LOCAL SERVICES ===
echo [0/3] Cleaning up old processes on ports 8005 and 3005...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8005 ^| findstr LISTENING') do taskkill /f /pid %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :3005 ^| findstr LISTENING') do taskkill /f /pid %%a >nul 2>&1

echo [1/3] Starting FastAPI Backend Telemetry Server (Port 8005)...
start "Backend" /min cmd /k "cd /d ""%~dp0"" && set ATE_DASHBOARD_PORT=8005 && set ATE_DASHBOARD_HOST=0.0.0.0 && python dashboard/server.py"

echo [2/3] Checking Node modules...
if not exist "web\node_modules" (
    echo Installing Next.js dependencies...
    cd web && npm install && cd ..
)

echo [3/3] Starting Bloomberg Trading Desk Web Dashboard (Port 3005)...
start "Frontend" /min cmd /k "cd /d ""%~dp0web"" && npm run dev"

timeout /t 3 /nobreak >nul
start http://localhost:3005

echo.
echo =======================================================================
echo [SUCCESS] Full Stack Services active:
echo - Backend FastAPI API: http://127.0.0.1:8005
echo - Web Dashboard UI:    http://localhost:3005
echo =======================================================================
echo.
