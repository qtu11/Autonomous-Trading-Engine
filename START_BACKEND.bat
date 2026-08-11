@echo off
chcp 65001 >nul
echo ==========================================
echo   ATE Trading System - Backend Starter
echo ==========================================
echo.

:: Find project root
set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%

:: Check dashboard exists
if exist "%PROJECT_ROOT%\dashboard\server.py" (
    goto :found
)

:: Try parent directories
set PROJECT_ROOT=%SCRIPT_DIR%..
if exist "%PROJECT_ROOT%\dashboard\server.py" (
    goto :found
)

echo [ERROR] Cannot find project directory
echo Please run from inside tradeAI folder
pause
exit /b 1

:found
echo [INFO] Project found at: %PROJECT_ROOT%
echo.

:: Ask which backend
echo Choose backend:
echo   [1] Dashboard (FastAPI + MT5) - PRODUCTION
echo   [2] Trading System (FastAPI + SQLite) - NEW
echo.
set /p choice="Enter choice (1 or 2): "

if "%choice%"=="1" (
    echo.
    echo [INFO] Starting Dashboard...
    cd /d "%PROJECT_ROOT%\dashboard"
    python server.py
) else if "%choice%"=="2" (
    if not exist "%PROJECT_ROOT%\working-dir\trading_system" (
        echo [ERROR] Trading System not found
        pause
        exit /b 1
    )
    echo.
    echo [INFO] Starting Trading System...
    cd /d "%PROJECT_ROOT%\working-dir\trading_system"
    pip install -r requirements.txt >nul 2>&1
    python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
) else (
    echo [ERROR] Invalid choice
    pause
)
