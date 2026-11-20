$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot\..
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose up -d --wait
docker compose ps
Write-Host "Grafana: http://localhost:$((Get-Content .env | Where-Object { $_ -match '^GRAFANA_PORT=' } | Select-Object -First 1).Split('=')[1])"
