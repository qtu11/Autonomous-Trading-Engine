$logDir = "C:\Users\KIMPC\AppData\Roaming\MetaQuotes\Terminal\C3DCCD4DFDD81FF8F00FFC310CAC0FD8\MQL5\Logs"
$logs = Get-ChildItem $logDir -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 5
foreach ($log in $logs) {
    Write-Host "== $($log.Name) =="
    Get-Content $log.FullName -Tail 100
    Write-Host ""
}
