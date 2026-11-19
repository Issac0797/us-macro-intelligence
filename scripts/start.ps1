param([switch]$Sync)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Install and start Docker Desktop (Linux containers), then run this script again.'
}
if (-not (Test-Path -LiteralPath '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
    Write-Host 'Created .env. Configure FRED_API_KEY and DATA_PROVIDER=fred_api to use the API.'
}
docker compose up --build -d --wait
if ($LASTEXITCODE -ne 0) { throw 'Docker Compose startup failed.' }
if ($Sync) {
    docker compose exec -T backend python -m app.sync --full
    if ($LASTEXITCODE -ne 0) { throw 'FRED synchronization failed. Inspect docker compose logs backend.' }
}
Write-Host 'Terminal: http://localhost:3000 | API docs: http://localhost:8000/docs'
