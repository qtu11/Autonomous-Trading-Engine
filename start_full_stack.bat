@echo off
title GoldQuant_AI_Launcher
color 0B
cls

echo =======================================================================
echo          GOLDQUANT AI BLOOMBERG TRADING DESK (PORT 3000 / 8005)        
echo =======================================================================
echo.

cd /d "%~dp0"

echo [0/3] Cleaning up old processes on ports 8005 and 3000...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8005 ^| findstr LISTENING') do taskkill /f /pid %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :3000 ^| findstr LISTENING') do taskkill /f /pid %%a >nul 2>&1

echo [1/3] Starting FastAPI Backend Telemetry Server (Port 8005)...
start "Backend" /min cmd /k "cd /d ""%~dp0"" && set QUANTAI_DASHBOARD_PORT=8005 && python dashboard/server.py"

echo [2/3] Checking Node modules...
if not exist "web\node_modules" (
    echo Installing Next.js dependencies...
    cd web && npm install && cd ..
)

echo [3/3] Starting Bloomberg Trading Desk Web Dashboard (Port 3000)...
start "Frontend" /min cmd /k "cd /d ""%~dp0web"" && npm run dev"

timeout /t 3 /nobreak >nul
start http://localhost:3000

echo.
echo =======================================================================
echo [SUCCESS] Full Stack Services active:
echo - Backend FastAPI API: http://127.0.0.1:8005
echo - Web Dashboard UI:    http://localhost:3000
echo =======================================================================
echo.
