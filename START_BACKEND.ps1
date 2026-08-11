# =============================================
# ATE Trading System - Backend Starter
# =============================================
param(
    [int]$Choice = 0
)

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  ATE Trading System - Backend Selector" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Try to find project root
$SearchPaths = @(
    $PSScriptRoot,
    "$PSScriptRoot\..",
    "$env:USERPROFILE\tradeAI",
    "C:\tradeAI",
    "D:\tradeAI"
)

$ProjectRoot = $null
foreach ($Path in $SearchPaths) {
    if ($Path -and (Test-Path "$Path\dashboard\server.py")) {
        $ProjectRoot = $Path
        break
    }
}

if (-not $ProjectRoot) {
    Write-Host "[ERROR] Cannot find project directory!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Make sure you're running this script from inside the tradeAI folder." -ForegroundColor Yellow
    Write-Host "Expected structure:" -ForegroundColor Yellow
    Write-Host "  tradeAI/" -ForegroundColor Gray
    Write-Host "  ├── dashboard/" -ForegroundColor Gray
    Write-Host "  │   └── server.py" -ForegroundColor Gray
    Write-Host "  └── [working-dir]/" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Or specify path manually:" -ForegroundColor Yellow
    Write-Host "  .\START_BACKEND.ps1 -Path 'C:\path\to\tradeAI'" -ForegroundColor Gray
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "[OK] Project found: $ProjectRoot" -ForegroundColor Green
Write-Host ""

# If path specified, change to it
if ($Path) {
    $ProjectRoot = $Path
    Write-Host "[OK] Using specified path: $ProjectRoot" -ForegroundColor Green
}

# Show choice if not specified
if ($Choice -eq 0) {
    Write-Host "Choose backend to start:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  [1] Dashboard (FastAPI + MT5)" -ForegroundColor White
    Write-Host "      - Full MT5 integration" -ForegroundColor Gray
    Write-Host "      - Real market data" -ForegroundColor Gray
    Write-Host "      - Requires MT5 Terminal running" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  [2] Trading System (FastAPI + SQLite)" -ForegroundColor White
    Write-Host "      - Sample/test data" -ForegroundColor Gray
    Write-Host "      - No MT5 required" -ForegroundColor Gray
    Write-Host ""
    $Choice = Read-Host "Enter choice (1 or 2)"
}

# Start selected backend
switch ($Choice) {
    "1" {
        Write-Host ""
        Write-Host "[INFO] Starting Dashboard (MT5)..." -ForegroundColor Cyan
        Write-Host ""
        Set-Location "$ProjectRoot\dashboard"
        Write-Host "Working directory: $(Get-Location)" -ForegroundColor Gray
        Write-Host "Starting: python server.py" -ForegroundColor Gray
        Write-Host ""
        python server.py
    }
    "2" {
        Write-Host ""
        Write-Host "[INFO] Starting Trading System (SQLite)..." -ForegroundColor Cyan
        Write-Host ""
        
        $TSPath = "$ProjectRoot\[working-dir]\trading_system"
        if (-not (Test-Path $TSPath)) {
            $TSPath = "$ProjectRoot\working-dir\trading_system"
        }
        
        if (-not (Test-Path "$TSPath\app\main.py")) {
            Write-Host "[ERROR] Trading System not found at: $TSPath" -ForegroundColor Red
            Write-Host ""
            Write-Host "Make sure '[working-dir]/trading_system' folder exists" -ForegroundColor Yellow
            Read-Host "Press Enter to exit"
            exit 1
        }
        
        Set-Location $TSPath
        Write-Host "Working directory: $(Get-Location)" -ForegroundColor Gray
        Write-Host "Installing dependencies..." -ForegroundColor Gray
        pip install -r requirements.txt --quiet 2>$null
        Write-Host "Starting: python -m uvicorn app.main:app --reload" -ForegroundColor Gray
        Write-Host ""
        python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    }
    default {
        Write-Host "[ERROR] Invalid choice. Please enter 1 or 2." -ForegroundColor Red
        exit 1
    }
}
