#requires -Version 5.1
<#
.SYNOPSIS
  Autonomous Trading Engine (ATE) - one-command full-stack launcher with health verification.

.DESCRIPTION
  Orchestrates every link in the chain so the platform starts with a single
  command and proves each stage is alive before opening the dashboard:
    1. Free ports 8005 (backend) and 3000 (frontend).
    2. Compile the MQL5 EA via MetaEditor (fail fast on compile errors).
    3. Ensure the MT5 terminal is running.
    4. Start the FastAPI backend (port 8005).
    5. Install/start the Next.js dashboard (port 3000).
    6. Health-check the backend until MT5 reports connected (or time out).
    7. Open the dashboard in the default browser.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\start.ps1
#>

Set-StrictMode -Off
$ErrorActionPreference = 'Stop'

$Root        = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendPort = 8005
$FrontendPort = 3000
$BackendUrl  = "http://127.0.0.1:$BackendPort"
$FrontendUrl = "http://localhost:$FrontendPort"
$MetaEditorCandidates = @(
    "C:\Program Files\MetaTrader 5-1\metaeditor64.exe",
    "C:\Program Files\MetaTrader 5\metaeditor64.exe"
)
$MetaEditor = $MetaEditorCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

$Mt5TerminalCandidates = @(
    "C:\Program Files\MetaTrader 5-1\terminal64.exe",
    "C:\Program Files\MetaTrader 5\terminal64.exe"
)
$Mt5Terminal = $Mt5TerminalCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
$EaSource    = Join-Path $Root "ATE_XAUUSD.mq5"
$EaBinary    = Join-Path $Root "ATE_XAUUSD.ex5"
$CompileLog  = Join-Path $Root "logs\ea_compile.log"

function Write-Step([string]$Message) {
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Write-Ok([string]$Message) {
    Write-Host "    [OK] $Message" -ForegroundColor Green
}

function Write-Warn([string]$Message) {
    Write-Host "    [WARN] $Message" -ForegroundColor Yellow
}

function Stop-PortProcess([int]$Port) {
    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($null -ne $connections) {
        foreach ($conn in $connections) {
            try {
                Stop-Process -Id $conn.OwningProcess -Force -ErrorAction Stop
                Write-Ok "Freed port $Port (PID $($conn.OwningProcess))"
            } catch {
                Write-Warn "Could not free port $Port (PID $($conn.OwningProcess)): $($_.Exception.Message)"
            }
        }
    }
}

function Test-BackendHealth {
    try {
        $response = Invoke-RestMethod -Uri "$BackendUrl/api/control-center/status" -TimeoutSec 3 -ErrorAction Stop
        return $response
    } catch {
        return $null
    }
}

Write-Host "=======================================================================" -ForegroundColor DarkCyan
Write-Host "   AUTONOMOUS TRADING ENGINE (ATE) BLOOMBERG DESK - LAUNCHER" -ForegroundColor DarkCyan
Write-Host "=======================================================================" -ForegroundColor DarkCyan

# 1. Free ports
Write-Step "[1/6] Freeing ports $BackendPort and $FrontendPort"
Stop-PortProcess -Port $BackendPort
Stop-PortProcess -Port $FrontendPort

# 2. Compile the EA
Write-Step "[2/6] Compiling MQL5 Expert Advisor"
New-Item -ItemType Directory -Force -Path (Split-Path $CompileLog) | Out-Null
if (Test-Path $MetaEditor) {
    if (Test-Path $EaBinary) {
        Copy-Item $EaBinary "$EaBinary.bak" -Force
        Write-Ok "Backed up existing EA binary"
    }
    $compileArgs = @("/compile:$EaSource", "/log:$CompileLog")
    $process = Start-Process -FilePath $MetaEditor -ArgumentList $compileArgs -Wait -PassThru -WindowStyle Hidden
    Start-Sleep -Seconds 2
    if (Test-Path $EaBinary) {
        Write-Ok "EA compiled -> $EaBinary"
    } else {
        Write-Warn "EA binary not produced; check $CompileLog"
    }
} else {
    Write-Warn "MetaEditor not found at $MetaEditor - skipping compile (using existing .ex5)"
}

# 3. Ensure MT5 terminal is running
Write-Step "[3/6] Ensuring MT5 terminal is running"
$terminal = Get-Process -Name "terminal64" -ErrorAction SilentlyContinue
if ($terminal) {
    Write-Ok "MT5 terminal already running (PID $($terminal[0].Id))"
} elseif (Test-Path $Mt5Terminal) {
    Start-Process -FilePath $Mt5Terminal
    Write-Ok "Started MT5 terminal"
    Start-Sleep -Seconds 5
} else {
    Write-Warn "MT5 terminal not found at $Mt5Terminal"
}

# 4. Start backend
Write-Step "[4/6] Starting FastAPI backend (port $BackendPort)"
$backendCmd = "cd /d `"$Root`" && set QUANTAI_DASHBOARD_PORT=$BackendPort&& set QUANTAI_DASHBOARD_HOST=0.0.0.0&& python dashboard\server.py"
Start-Process -FilePath "cmd.exe" -ArgumentList "/k", $backendCmd -WindowStyle Minimized
Write-Ok "Backend process launched"

# 5. Start frontend
Write-Step "[5/6] Starting Next.js dashboard (port $FrontendPort)"
$webDir = Join-Path $Root "web"
if (-not (Test-Path (Join-Path $webDir "node_modules"))) {
    Write-Host "    Installing Next.js dependencies..." -ForegroundColor Yellow
    Push-Location $webDir
    npm install
    Pop-Location
}
$frontendCmd = "cd /d `"$webDir`" && npm run dev"
Start-Process -FilePath "cmd.exe" -ArgumentList "/k", $frontendCmd -WindowStyle Minimized
Write-Ok "Frontend process launched"

# 6. Health verification
Write-Step "[6/6] Verifying system health"
$deadline = (Get-Date).AddSeconds(45)
$healthy = $false
$status = $null
while ((Get-Date) -lt $deadline) {
    $status = Test-BackendHealth
    if ($null -ne $status) {
        $healthy = $true
        if ($status.account.mt5_connected) { break }
    }
    Start-Sleep -Seconds 2
}

Write-Host "`n------------------------- SYSTEM STATUS -------------------------" -ForegroundColor DarkGray
if ($healthy) {
    Write-Ok "Backend API reachable at $BackendUrl"
    $mt5State = if ($status.account.mt5_connected) { "CONNECTED" } else { "DISCONNECTED" }
    $mt5Color = if ($status.account.mt5_connected) { "Green" } else { "Red" }
    Write-Host ("    MT5:            " + $mt5State) -ForegroundColor $mt5Color
    Write-Host ("    Account:        " + $status.account.login + " @ " + $status.account.server) -ForegroundColor Gray
    Write-Host ("    Execution mode: " + $status.execution.mode + "  (locked=" + $status.execution.execution_locked + ")") -ForegroundColor Gray
    Write-Host ("    Readiness:      " + $status.readiness.reason_code) -ForegroundColor Gray
} else {
    Write-Warn "Backend did not respond within 45s. Check the backend console window."
}
Write-Host "----------------------------------------------------------------" -ForegroundColor DarkGray

Write-Host "`n[SUCCESS] Full stack services:" -ForegroundColor Green
Write-Host "  Backend FastAPI:  $BackendUrl" -ForegroundColor Gray
Write-Host "  Web Dashboard:    $FrontendUrl" -ForegroundColor Gray
Write-Host "  Realtime stream:  ws://127.0.0.1:$BackendPort/ws/stream" -ForegroundColor Gray

Start-Sleep -Seconds 3
Start-Process $FrontendUrl
