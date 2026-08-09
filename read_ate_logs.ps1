$logDir = "C:\Users\KIMPC\AppData\Roaming\MetaQuotes\Terminal\C3DCCD4DFDD81FF8F00FFC310CAC0FD8\MQL5\Logs"
$logs = Get-ChildItem $logDir -ErrorAction SilentlyContinue | Where-Object { $_.Name -like "*ATE_XAUUSD*" } | Sort-Object LastWriteTime -Descending | Select-Object -First 3
foreach ($log in $logs) {
    Write-Host "== $($log.Name) (Modified: $($log.LastWriteTime)) =="
    Get-Content $log.FullName -Tail 80
    Write-Host ""
}
