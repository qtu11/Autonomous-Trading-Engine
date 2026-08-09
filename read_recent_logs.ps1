$logDir = "C:\Users\KIMPC\AppData\Roaming\MetaQuotes\Terminal\C3DCCD4DFDD81FF8F00FFC310CAC0FD8\MQL5\Logs"
$recent = Get-Date | AddHours(-3)
$logs = Get-ChildItem $logDir -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -gt $recent } | Sort-Object LastWriteTime -Descending
if ($logs.Count -eq 0) {
    Write-Host "No logs in last 3 hours. Showing latest 3 files:"
    $logs = Get-ChildItem $logDir -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 3
}
foreach ($log in $logs) {
    Write-Host "== $($log.Name) (Modified: $($log.LastWriteTime)) =="
    Get-Content $log.FullName -Tail 50
    Write-Host ""
}
