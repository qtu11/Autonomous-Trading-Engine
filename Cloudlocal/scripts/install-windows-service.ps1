<# 
.SYNOPSIS
    Installs Cloudlocal as a Windows Task Scheduler service that starts on boot
.DESCRIPTION
    Creates a scheduled task that runs docker-compose up -d on system startup
    Runs with highest privileges, starts whether user is logged on or not
#>

param(
    [string]$ProjectPath = "C:\Users\KIMPC\AppData\Roaming\MetaQuotes\Terminal\C3DCCD4DFDD81FF8F00FFC310CAC0FD8\MQL5\Experts\tradeAI\Cloudlocal",
    [string]$TaskName = "Cloudlocal-Trading-Engine",
    [string]$Description = "GoldQuant AI Local Cloud - Starts Docker containers on boot for MT5-Website bridge"
)

# Require Administrator
if (-NOT ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Error "This script requires Administrator privileges. Please run PowerShell as Administrator."
    exit 1
}

Write-Host "=== Cloudlocal Windows Auto-Start Installation ===" -ForegroundColor Cyan
Write-Host "Project Path: $ProjectPath" -ForegroundColor Yellow
Write-Host "Task Name: $TaskName" -ForegroundColor Yellow

# Verify Docker is installed
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker not found in PATH. Please install Docker Desktop first."
    exit 1
}

if (-not (Get-Command docker-compose -ErrorAction SilentlyContinue)) {
    Write-Error "docker-compose not found. Please install Docker Compose."
    exit 1
}

# Check if project directory exists
if (-not (Test-Path $ProjectPath)) {
    Write-Error "Project directory not found: $ProjectPath"
    exit 1
}

# Check docker-compose.yml exists
$ComposeFile = Join-Path $ProjectPath "docker-compose.yml"
if (-not (Test-Path $ComposeFile)) {
    Write-Error "docker-compose.yml not found in $ProjectPath"
    exit 1
}

# Create the startup script
$StartupScript = @"
@echo off
cd /d "$ProjectPath"
echo [%date% %time%] Starting Cloudlocal containers... >> logs\startup.log
docker-compose up -d --remove-orphans >> logs\startup.log 2>&1
echo [%date% %time%] Cloudlocal started. >> logs\startup.log
"@

$ScriptPath = Join-Path $ProjectPath "scripts\start-cloudlocal.bat"
Set-Content -Path $ScriptPath -Value $StartupScript -Encoding ASCII
Write-Host "Created startup script: $ScriptPath" -ForegroundColor Green

# Create the shutdown script
$ShutdownScript = @"
@echo off
cd /d "$ProjectPath"
echo [%date% %time%] Stopping Cloudlocal containers... >> logs\shutdown.log
docker-compose down >> logs\shutdown.log 2>&1
echo [%date% %time%] Cloudlocal stopped. >> logs\shutdown.log
"@

$ShutdownPath = Join-Path $ProjectPath "scripts\stop-cloudlocal.bat"
Set-Content -Path $ShutdownPath -Value $ShutdownScript -Encoding ASCII
Write-Host "Created shutdown script: $ShutdownPath" -ForegroundColor Green

# Create the scheduled task
$Action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$ScriptPath`"" -WorkingDirectory $ProjectPath

$Trigger = New-ScheduledTaskTrigger -AtStartup -RandomDelay 00:02:00

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 5)

$Principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

$Task = New-ScheduledTask -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Description $Description

try {
    # Remove existing task if exists
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "Removed existing task: $TaskName" -ForegroundColor Yellow
    }
    
    Register-ScheduledTask -TaskName $TaskName -InputObject $Task -Force
    Write-Host "Successfully registered task: $TaskName" -ForegroundColor Green
    
    # Also create a logon trigger for when user logs in (backup)
    $LogonTrigger = New-ScheduledTaskTrigger -AtLogOn -User "SYSTEM" -RandomDelay 00:01:00
    Add-ScheduledTaskTrigger -TaskName $TaskName -Trigger $LogonTrigger
    
} catch {
    Write-Error "Failed to register scheduled task: $_"
    exit 1
}

# Enable Docker Desktop auto-start
Write-Host "Configuring Docker Desktop to start on boot..." -ForegroundColor Cyan
$DockerPath = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
if (Test-Path $DockerPath) {
    $DockerTaskName = "Docker Desktop Auto-Start"
    if (-not (Get-ScheduledTask -TaskName $DockerTaskName -ErrorAction SilentlyContinue)) {
        $DockerAction = New-ScheduledTaskAction -Execute $DockerPath
        $DockerTrigger = New-ScheduledTaskTrigger -AtStartup -RandomDelay 00:00:30
        $DockerSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfOnBatteries -StartWhenAvailable
        $DockerPrincipal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
        $DockerTask = New-ScheduledTask -Action $DockerAction -Trigger $DockerTrigger -Settings $DockerSettings -Principal $DockerPrincipal
        Register-ScheduledTask -TaskName $DockerTaskName -InputObject $DockerTask -Force
        Write-Host "Docker Desktop auto-start configured" -ForegroundColor Green
    }
}

# Configure Windows Firewall for required ports
Write-Host "Configuring Windows Firewall..." -ForegroundColor Cyan
$Ports = @(80, 443, 3000, 8005, 8006, 8007, 8080, 5432, 6379)
foreach ($Port in $Ports) {
    $RuleNameIn = "Cloudlocal-Port-$Port-In"
    $RuleNameOut = "Cloudlocal-Port-$Port-Out"
    
    if (-not (Get-NetFirewallRule -DisplayName $RuleNameIn -ErrorAction SilentlyContinue)) {
        New-NetFirewallRule -DisplayName $RuleNameIn -Direction Inbound -Protocol TCP -LocalPort $Port -Action Allow -Profile Any -Description "Cloudlocal Trading Engine Port $Port"
        Write-Host "  Added inbound rule for port $Port" -ForegroundColor Green
    }
    
    if (-not (Get-NetFirewallRule -DisplayName $RuleNameOut -ErrorAction SilentlyContinue)) {
        New-NetFirewallRule -DisplayName $RuleNameOut -Direction Outbound -Protocol TCP -LocalPort $Port -Action Allow -Profile Any -Description "Cloudlocal Trading Engine Port $Port"
        Write-Host "  Added outbound rule for port $Port" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "=== Installation Complete ===" -ForegroundColor Cyan
Write-Host "Task Name: $TaskName" -ForegroundColor Yellow
Write-Host "Startup Script: $ScriptPath" -ForegroundColor Yellow
Write-Host "Shutdown Script: $ShutdownPath" -ForegroundColor Yellow
Write-Host ""
Write-Host "The service will start automatically on:" -ForegroundColor White
Write-Host "  1. System boot (via Task Scheduler)" -ForegroundColor White
Write-Host "  2. User logon (backup trigger)" -ForegroundColor White
Write-Host ""
Write-Host "To manually start now:" -ForegroundColor Cyan
Write-Host "  & `"$ScriptPath`"" -ForegroundColor Yellow
Write-Host ""
Write-Host "To check status:" -ForegroundColor Cyan
Write-Host "  Get-ScheduledTask -TaskName `"$TaskName`"" -ForegroundColor Yellow
Write-Host "  docker-compose -f $ComposeFile ps" -ForegroundColor Yellow
Write-Host ""
Write-Host "Public URLs (replace with your actual public IP):" -ForegroundColor Cyan
Write-Host "  Website: http://YOUR_PUBLIC_IP:80" -ForegroundColor White
Write-Host "  API:     http://YOUR_PUBLIC_IP:80/api" -ForegroundColor White
Write-Host "  Bridge:  http://YOUR_PUBLIC_IP:80/bridge" -ForegroundColor White
Write-Host "  WS:      ws://YOUR_PUBLIC_IP:80/ws" -ForegroundColor White