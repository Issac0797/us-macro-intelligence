$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path $PSScriptRoot -Parent
foreach ($taskName in @('frontend','backend','postgres')) {
    $taskRecordPath = Join-Path $taskRoot ".local/$taskName.process.json"
    if (-not (Test-Path -LiteralPath $taskRecordPath)) { continue }
    $taskRecord = Get-Content -LiteralPath $taskRecordPath -Raw | ConvertFrom-Json
    $taskProcess = Get-Process -Id $taskRecord.pid -ErrorAction SilentlyContinue
    # Do not stop a recycled PID that no longer belongs to this launcher.
    if ($taskProcess -and $taskProcess.StartTime.ToUniversalTime() -eq ([datetime]$taskRecord.started).ToUniversalTime()) {
        if ($taskName -eq 'postgres') {
            & "$taskRoot/.local/postgres-runtime/node_modules/@embedded-postgres/windows-x64/native/bin/pg_ctl.exe" -D "$taskRoot/.local/pgdata" stop -m fast
        } elseif ($taskName -eq 'backend') {
            # The Windows venv launcher may have a Python child process.
            taskkill /PID $taskProcess.Id /T /F | Out-Null
        } else { Stop-Process -Id $taskProcess.Id }
        Write-Host "Stopped $taskName"
    }
    Remove-Item -LiteralPath $taskRecordPath
}
