<#
.SYNOPSIS
    Configures Windows Firewall and router port forwarding for Cloudlocal public access
.DESCRIPTION
    Sets up inbound/outbound firewall rules for all required ports
    Attempts to configure UPnP port forwarding on router
    Displays current public IP and port status
#>

param(
    [string[]]$Ports = @(80, 443, 3000, 8005, 8006, 8007, 8080, 5432, 6379),
    [switch]$EnableUPnP = $true,
    [switch]$ShowOnly = $false
)

Write-Host "=== Cloudlocal Firewall & Port Forwarding Setup ===" -ForegroundColor Cyan

# Require Administrator for firewall changes
if (-NOT ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Warning "Firewall changes require Administrator. Run PowerShell as Admin for full setup."
    $IsAdmin = $false
} else {
    $IsAdmin = $true
}

# Get public IP
Write-Host "Fetching public IP..." -ForegroundColor Yellow
try {
    $PublicIP = (Invoke-RestMethod -Uri "https://api.ipify.org?format=json" -TimeoutSec 10).ip
    Write-Host "Public IP: $PublicIP" -ForegroundColor Green
} catch {
    Write-Warning "Could not fetch public IP automatically"
    $PublicIP = "UNKNOWN"
}

# Get local IP
$LocalIP = (Get-NetIPAddress -AddressFamily IPv4 -InterfaceAlias "*" | Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } | Select-Object -First 1).IPAddress
Write-Host "Local IP: $LocalIP" -ForegroundColor Green

if ($ShowOnly) {
    Write-Host ""
    Write-Host "=== Current Firewall Rules ===" -ForegroundColor Cyan
    foreach ($Port in $Ports) {
        $RuleIn = Get-NetFirewallRule -DisplayName "Cloudlocal-Port-$Port-In" -ErrorAction SilentlyContinue
        $RuleOut = Get-NetFirewallRule -DisplayName "Cloudlocal-Port-$Port-Out" -ErrorAction SilentlyContinue
        
        $StatusIn = if ($RuleIn) { "ENABLED" } else { "MISSING" }
        $StatusOut = if ($RuleOut) { "ENABLED" } else { "MISSING" }
        
        $ColorIn = if ($RuleIn) { "Green" } else { "Red" }
        $ColorOut = if ($RuleOut) { "Green" } else { "Red" }
        
        Write-Host "Port $Port: Inbound [$StatusIn] Outbound [$StatusOut]" -ForegroundColor $ColorIn
    }
    exit 0
}

if ($IsAdmin) {
    Write-Host "Configuring Windows Firewall..." -ForegroundColor Cyan
    foreach ($Port in $Ports) {
        $RuleNameIn = "Cloudlocal-Port-$Port-In"
        $RuleNameOut = "Cloudlocal-Port-$Port-Out"
        
        # Inbound rule
        if (-not (Get-NetFirewallRule -DisplayName $RuleNameIn -ErrorAction SilentlyContinue)) {
            New-NetFirewallRule -DisplayName $RuleNameIn -Direction Inbound -Protocol TCP -LocalPort $Port -Action Allow -Profile Any -Description "Cloudlocal Trading Engine Port $Port Inbound" -Enabled True
            Write-Host "  [+] Inbound rule for port $Port created" -ForegroundColor Green
        } else {
            Set-NetFirewallRule -DisplayName $RuleNameIn -Enabled True
            Write-Host "  [*] Inbound rule for port $Port already exists (enabled)" -ForegroundColor Yellow
        }
        
        # Outbound rule
        if (-not (Get-NetFirewallRule -DisplayName $RuleNameOut -ErrorAction SilentlyContinue)) {
            New-NetFirewallRule -DisplayName $RuleNameOut -Direction Outbound -Protocol TCP -LocalPort $Port -Action Allow -Profile Any -Description "Cloudlocal Trading Engine Port $Port Outbound" -Enabled True
            Write-Host "  [+] Outbound rule for port $Port created" -ForegroundColor Green
        } else {
            Set-NetFirewallRule -DisplayName $RuleNameOut -Enabled True
            Write-Host "  [*] Outbound rule for port $Port already exists (enabled)" -ForegroundColor Yellow
        }
    }
    
    # Allow Docker networking
    $DockerRules = @(
        @{Name="Docker-Inbound"; Port=2375; Desc="Docker API"},
        @{Name="Docker-Outbound"; Port=2375; Desc="Docker API"},
        @{Name="Docker-DNS"; Port=53; Protocol="UDP"; Desc="Docker DNS"}
    )
    
    foreach ($Rule in $DockerRules) {
        $Proto = if ($Rule.Protocol) { $Rule.Protocol } else { "TCP" }
        $InName = "Cloudlocal-$($Rule.Name)-In"
        $OutName = "Cloudlocal-$($Rule.Name)-Out"
        
        if (-not (Get-NetFirewallRule -DisplayName $InName -ErrorAction SilentlyContinue)) {
            New-NetFirewallRule -DisplayName $InName -Direction Inbound -Protocol $Proto -LocalPort $Rule.Port -Action Allow -Profile Any -Description $Rule.Desc
        }
        if (-not (Get-NetFirewallRule -DisplayName $OutName -ErrorAction SilentlyContinue)) {
            New-NetFirewallRule -DisplayName $OutName -Direction Outbound -Protocol $Proto -LocalPort $Rule.Port -Action Allow -Profile Any -Description $Rule.Desc
        }
    }
    
    Write-Host "Windows Firewall configuration complete." -ForegroundColor Green
} else {
    Write-Warning "Skipping firewall configuration (requires Admin). Run as Administrator to apply."
}

# UPnP Port Forwarding
if ($EnableUPnP) {
    Write-Host ""
    Write-Host "Attempting UPnP Port Forwarding..." -ForegroundColor Cyan
    
    # Check if UPnP is available
    $UPnPService = Get-Service -Name "upnphost" -ErrorAction SilentlyContinue
    if ($UPnPService) {
        if ($UPnPService.Status -ne "Running") {
            Start-Service -Name "upnphost" -ErrorAction SilentlyContinue
            Write-Host "  Started UPnP service" -ForegroundColor Green
        }
    } else {
        Write-Warning "UPnP service not found. Enable 'UPnP Device Host' in Windows Features."
    }
    
    # Try using Windows NAT/UPnP COM object
    try {
        $NATUPnP = New-Object -ComObject HNetCfg.NATUPnP
        $StaticMappings = $NATUPnP.StaticPortMappingCollection
        
        foreach ($Port in $Ports) {
            try {
                # Check if mapping exists
                $Existing = $StaticMappings | Where-Object { $_.ExternalPort -eq $Port -and $_.Protocol -eq 6 } # TCP=6
                if ($Existing) {
                    Write-Host "  [*] UPnP mapping for port $Port already exists -> $($Existing.InternalClient):$($Existing.InternalPort)" -ForegroundColor Yellow
                } else {
                    $StaticMappings.Add($Port, 6, $Port, $LocalIP, $true, "Cloudlocal-Port-$Port")
                    Write-Host "  [+] UPnP mapping created: External $Port -> $LocalIP:$Port (TCP)" -ForegroundColor Green
                }
            } catch {
                Write-Warning "  UPnP mapping failed for port $Port: $_"
            }
        }
    } catch {
        Write-Warning "UPnP COM object not available. Manual router configuration required."
        Write-Host "  Please manually forward these ports on your router:" -ForegroundColor Yellow
        foreach ($Port in $Ports) {
            Write-Host "    Port $Port (TCP) -> $LocalIP:$Port" -ForegroundColor White
        }
    }
}

# Test port accessibility
Write-Host ""
Write-Host "Testing local port bindings..." -ForegroundColor Cyan
foreach ($Port in $Ports) {
    $Listener = $null
    try {
        $Listener = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Any, $Port)
        $Listener.Start()
        $Listener.Stop()
        Write-Host "  Port $Port: AVAILABLE" -ForegroundColor Green
    } catch {
        Write-Host "  Port $Port: IN USE or BLOCKED" -ForegroundColor Red
    } finally {
        if ($Listener) { $Listener.Stop() }
    }
}

# Summary
Write-Host ""
Write-Host "=== Configuration Summary ===" -ForegroundColor Cyan
Write-Host "Public IP: $PublicIP" -ForegroundColor White
Write-Host "Local IP:  $LocalIP" -ForegroundColor White
Write-Host ""
Write-Host "External URLs (configure ATE_BACKEND_URL in Vercel):" -ForegroundColor Cyan
Write-Host "  Website:     http://$PublicIP:80" -ForegroundColor White
Write-Host "  API (Main):  http://$PublicIP:80/api/v1" -ForegroundColor White
Write-Host "  API (Direct): http://$PublicIP:8005" -ForegroundColor White
Write-Host "  Bridge:      http://$PublicIP:80/bridge" -ForegroundColor White
Write-Host "  WebSocket:   ws://$PublicIP:80/ws" -ForegroundColor White
Write-Host "  AI Engine:   http://$PublicIP:80/ai" -ForegroundColor White
Write-Host ""
Write-Host "Vercel Environment Variable:" -ForegroundColor Yellow
Write-Host "  ATE_BACKEND_URL=http://$PublicIP:80" -ForegroundColor White
Write-Host ""
Write-Host "Router Manual Forwarding (if UPnP failed):" -ForegroundColor Yellow
foreach ($Port in @(80, 443, 8005, 8006, 8007, 8080)) {
    Write-Host "  $Port (TCP) -> $LocalIP:$Port" -ForegroundColor White
}
Write-Host ""
Write-Host "Test external access:" -ForegroundColor Cyan
Write-Host "  curl http://$PublicIP:80/health" -ForegroundColor White
Write-Host "  curl http://$PublicIP:80/api/v1/health" -ForegroundColor White