<#
.SYNOPSIS
    Real-time monitor for Cloudlocal Trading Engine
.DESCRIPTION
    Displays live container status, resource usage, MT5 connection, and trading metrics
#>

param(
    [int]$RefreshInterval = 5,
    [switch]$NoClear
)

function Clear-HostIfNeeded {
    if (-not $NoClear) { Clear-Host }
}

function Get-ContainerStatus {
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | Where-Object { $_ -like "*cloudlocal*" }
}

function Get-ResourceUsage {
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" | Where-Object { $_ -like "*cloudlocal*" }
}

function Test-Endpoint {
    param([string]$Url, [string]$Name, [int]$Timeout = 3)
    try {
        $Result = Invoke-WebRequest -Uri $Url -Method Get -TimeoutSec $Timeout -UseBasicParsing -ErrorAction Stop
        return [pscustomobject]@{ Name=$Name; Status="OK"; Code=$Result.StatusCode; Time=$Result.ResponseTime }
    } catch {
        return [pscustomobject]@{ Name=$Name; Status="FAIL"; Code=$_.Exception.Response.StatusCode.Value; Time=0 }
    }
}

function Get-MT5Status {
    try {
        $Result = Invoke-WebRequest -Uri "http://localhost:8007/api/v1/account" -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
        $Data = $Result.Content | ConvertFrom-Json
        return [pscustomobject]@{
            Connected = $true
            Login = $Data.login
            Server = $Data.server
            Balance = $Data.balance
            Equity = $Data.equity
            Margin = $Data.margin
            FreeMargin = $Data.free_margin
            MarginLevel = if ($Data.margin_level -gt 0) { "{0:N2}%" -f $Data.margin_level } else { "N/A" }
        }
    } catch {
        return [pscustomobject]@{ Connected = $false }
    }
}

function Get-Positions {
    try {
        $Result = Invoke-WebRequest -Uri "http://localhost:8007/api/v1/positions" -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
        $Data = $Result.Content | ConvertFrom-Json
        return $Data
    } catch {
        return @()
    }
}

function Get-LatestTick {
    try {
        $Result = Invoke-WebRequest -Uri "http://localhost:8007/api/v1/market/tick" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
        $Data = $Result.Content | ConvertFrom-Json
        return $Data
    } catch {
        return $null
    }
}

Write-Host "=== Cloudlocal Trading Engine Monitor ===" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to exit. Refresh: ${RefreshInterval}s" -ForegroundColor Yellow
Write-Host ""

$Iteration = 0
while ($true) {
    $Iteration++
    Clear-HostIfNeeded
    
    $Time = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$Time] Iteration #$Iteration" -ForegroundColor Gray
    Write-Host ""
    
    # Container Status
    Write-Host "▶ CONTAINER STATUS" -ForegroundColor Cyan
    Get-ContainerStatus | Format-Table -AutoSize | Out-Host
    Write-Host ""
    
    # Resource Usage
    Write-Host "▶ RESOURCE USAGE" -ForegroundColor Cyan
    Get-ResourceUsage | Format-Table -AutoSize | Out-Host
    Write-Host ""
    
    # Health Checks
    Write-Host "▶ HEALTH CHECKS" -ForegroundColor Cyan
    $Endpoints = @(
        @{Url="http://localhost/health"; Name="Nginx (80)"},
        @{Url="http://localhost:8005/health"; Name="FastAPI (8005)"},
        @{Url="http://localhost:8006/health"; Name="AI Engine (8006)"},
        @{Url="http://localhost:8007/health"; Name="Python Bridge (8007)"},
        @{Url="http://localhost:3000"; Name="Next.js (3000)"}
    )
    
    $HealthResults = @()
    foreach ($Ep in $Endpoints) {
        $HealthResults += Test-Endpoint $Ep.Url $Ep.Name
    }
    $HealthResults | Format-Table @{Name="Service";Expression={$_.Name}},@{Name="Status";Expression={$_.Status}},@{Name="Code";Expression={$_.Code}},@{Name="Time(ms)";Expression={[math]::Round($_.Time*1000)}} -AutoSize | Out-Host
    Write-Host ""
    
    # MT5 Status
    Write-Host "▶ MT5 CONNECTION" -ForegroundColor Cyan
    $MT5 = Get-MT5Status
    if ($MT5.Connected) {
        Write-Host "  Status: CONNECTED" -ForegroundColor Green
        Write-Host "  Account: $($MT5.Login) @ $($MT5.Server)"
        Write-Host "  Balance: $($MT5.Balance) | Equity: $($MT5.Equity) | Margin: $($MT5.Margin)"
        Write-Host "  Free Margin: $($MT5.FreeMargin) | Margin Level: $($MT5.MarginLevel)"
    } else {
        Write-Host "  Status: DISCONNECTED" -ForegroundColor Red
    }
    Write-Host ""
    
    # Positions
    Write-Host "▶ OPEN POSITIONS" -ForegroundColor Cyan
    $Positions = Get-Positions
    if ($Positions.Count -gt 0) {
        $Positions | Format-Table @{Name="Ticket";Expression={$_.ticket}},@{Name="Symbol";Expression={$_.symbol}},@{Name="Type";Expression={$_.type}},@{Name="Volume";Expression={$_.volume}},@{Name="Entry";Expression={$_.price_open}},@{Name="SL";Expression={$_.sl}},@{Name="TP";Expression={$_.tp}},@{Name="Profit";Expression={$_.profit}},@{Name="Swap";Expression={$_.swap}} -AutoSize | Out-Host
    } else {
        Write-Host "  No open positions" -ForegroundColor Yellow
    }
    Write-Host ""
    
    # Market Data
    Write-Host "▶ MARKET DATA (XAUUSDm)" -ForegroundColor Cyan
    $Tick = Get-LatestTick
    if ($Tick) {
        Write-Host "  Bid: $($Tick.bid) | Ask: $($Tick.ask) | Spread: $($Tick.spread) pips"
        Write-Host "  Time: $($Tick.time) | Volume: $($Tick.volume)"
    } else {
        Write-Host "  No tick data available" -ForegroundColor Yellow
    }
    Write-Host ""
    
    # External Access
    Write-Host "▶ EXTERNAL ACCESS" -ForegroundColor Cyan
    $Env = Get-Content .env -ErrorAction SilentlyContinue | Where-Object { $_ -like "PUBLIC_IP=*" }
    if ($Env) {
        $PubIP = $Env -replace "PUBLIC_IP=", ""
        Write-Host "  Public IP: $PubIP"
        Write-Host "  Website: http://$PubIP:80"
        Write-Host "  API: http://$PubIP:80/api/v1"
        Write-Host "  Bridge: http://$PubIP:80/bridge"
        Write-Host "  WS: ws://$PubIP:80/ws"
    } else {
        Write-Host "  PUBLIC_IP not set in .env" -ForegroundColor Yellow
    }
    Write-Host ""
    
    Start-Sleep -Seconds $RefreshInterval
}