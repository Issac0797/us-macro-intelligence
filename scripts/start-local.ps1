# Convenience launcher for the already prepared native workspace, not an installer.
param([switch]$Restart,[string]$BuildDirectory="")
$ErrorActionPreference = 'Stop'
if ($Restart) { & "$PSScriptRoot/stop-local.ps1" }
$taskRoot = Split-Path $PSScriptRoot -Parent
Set-Location $taskRoot
if (-not $BuildDirectory) {
    $activeBuild=Join-Path $taskRoot '.local/active-build.json'
    $BuildDirectory=if (Test-Path -LiteralPath $activeBuild) { (Get-Content -LiteralPath $activeBuild -Raw | ConvertFrom-Json).directory } else { '.next' }
}
if ($BuildDirectory -notin @('.next','.next-phase-a','.next-phase-b','.next-phase-b-final','.next-bugfix-final')) { throw 'Unsupported build directory.' }
$buildRelative="frontend/$BuildDirectory"
New-Item -ItemType Directory -Force '.local','logs' | Out-Null
if (-not (Test-Path '.env')) { throw 'Configure .env first. See README.md.' }
if (-not (Test-Path '.venv/Scripts/python.exe')) { throw 'Install native backend dependencies first. See README.md.' }
if (-not (Test-Path "$buildRelative/standalone/server.js")) { throw 'Run npm.cmd ci and npm.cmd run build in frontend first.' }

function Test-TaskPort([int]$Port) {
    $taskClient = New-Object System.Net.Sockets.TcpClient
    try { $taskClient.Connect('127.0.0.1', $Port); return $true } catch { return $false } finally { $taskClient.Dispose() }
}
function Start-TaskService($Name, $File, $Arguments, $Directory) {
    $taskProcess = Start-Process -FilePath $File -ArgumentList $Arguments -WorkingDirectory $Directory -WindowStyle Hidden -RedirectStandardOutput "$taskRoot/logs/$Name.stdout.log" -RedirectStandardError "$taskRoot/logs/$Name.stderr.log" -PassThru
    @{pid=$taskProcess.Id; started=$taskProcess.StartTime.ToUniversalTime().ToString('O')} | ConvertTo-Json | Set-Content ".local/$Name.process.json"
    Write-Host "Started $Name (PID $($taskProcess.Id))"
}

$taskPg = "$taskRoot/.local/postgres-runtime/node_modules/@embedded-postgres/windows-x64/native/bin/postgres.exe"
if ((Test-Path $taskPg) -and (Test-Path '.local/pgdata') -and -not (Test-TaskPort 55432)) {
    Start-TaskService 'postgres' $taskPg @('-D',('"' + "$taskRoot/.local/pgdata" + '"'),'-h','127.0.0.1','-p','55432') $taskRoot
    for ($taskAttempt=0; $taskAttempt -lt 20; $taskAttempt++) {
        if (Test-TaskPort 55432) { break }
        Start-Sleep -Milliseconds 250
    }
}
Push-Location "$taskRoot/backend"
try {
    & "$taskRoot/.venv/Scripts/python.exe" "$taskRoot/scripts/wait-database.py"
    if ($LASTEXITCODE -ne 0) { throw 'Database readiness check failed.' }
    & "$taskRoot/.venv/Scripts/python.exe" -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw 'Database migration failed.' }
} finally { Pop-Location }
if (-not (Test-TaskPort 8000)) {
    $env:MONITOR_ENABLED = 'true'
    Start-TaskService 'backend' "$taskRoot/.venv/Scripts/python.exe" @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000') "$taskRoot/backend"
}
New-Item -ItemType Directory -Force "$buildRelative/standalone/$BuildDirectory" | Out-Null
Copy-Item -LiteralPath "$buildRelative/static" -Destination "$buildRelative/standalone/$BuildDirectory" -Recurse -Force
$env:HOSTNAME = '127.0.0.1'
$env:PORT = '3000'
$env:BACKEND_URL = 'http://127.0.0.1:8000'
$env:NEXT_TELEMETRY_DISABLED = '1'
if (-not (Test-TaskPort 3000)) {
    Start-TaskService 'frontend' (Get-Command node.exe).Source @('server.js') "$taskRoot/$buildRelative/standalone"
}
Write-Host 'Terminal: http://127.0.0.1:3000 | API docs: http://127.0.0.1:8000/docs'
