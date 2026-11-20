$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot\..
Write-Host 'This removes only the realtime-warehouse Compose containers and named volumes (Kafka, ClickHouse, Spark checkpoint, Grafana).'
docker compose down --volumes --remove-orphans
docker compose up -d --wait
docker compose ps
