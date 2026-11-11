# Execution policy is scoped to this launcher process; no system settings are changed.
$ErrorActionPreference = 'Continue'
Set-Location -LiteralPath $PSScriptRoot -ErrorAction Stop
function Stop-Installation([string] $Message) { Write-Host "`n$Message" -ForegroundColor Red; exit 1 }
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Stop-Installation 'Install Docker Desktop from https://www.docker.com/products/docker-desktop/, then start this launcher again.'
}
docker info *> $null
if ($LASTEXITCODE -ne 0) { Stop-Installation 'Open Docker Desktop, wait until its engine is running, then start this launcher again.' }
docker compose version *> $null
if ($LASTEXITCODE -ne 0) { Stop-Installation 'Update Docker Desktop: its Docker Compose plugin is required.' }
Write-Host "`nStarting ProbeLoop. The first download can take several minutes."
docker compose up -d
if ($LASTEXITCODE -ne 0) { Stop-Installation 'ProbeLoop could not start. If port 8000 is occupied, set PROBELOOP_PORT=8001 in the .env file beside this launcher and try again. Your saved data has been kept.' }
$backendId = docker compose ps -q backend
$healthy = $false
for ($attempt = 0; $attempt -lt 300; $attempt++) {
    $health = docker inspect --format '{{.State.Health.Status}}' $backendId
    if ($health -eq 'healthy') { $healthy = $true; break }
    if ($attempt -gt 0 -and $attempt % 15 -eq 0) { Write-Host 'Preparing the application. The first start can take longer on a cold Docker cache.' }
    Start-Sleep -Seconds 2
}
if (-not $healthy) { Stop-Installation 'ProbeLoop is taking longer than expected. Open Docker Desktop and inspect the backend logs, then run this launcher again. Saved data is preserved.' }
$address = docker compose port backend 8000
$url = "http://$address"
Write-Host "`nProbeLoop is ready: $url`nKeep Docker Desktop running while you use the app."
Start-Process $url
