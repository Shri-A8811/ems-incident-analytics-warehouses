param(
    [string]$StartDate = '2024-01-01T00:00:00',
    [string]$EndDateExclusive = '2026-07-01T00:00:00',
    [int]$PageSize = 500000
)

$ErrorActionPreference = 'Stop'
$datasetId = '76xm-jjuj'
$apiRoot = "https://data.cityofnewyork.us/resource/$datasetId.csv"
$rawDir = Join-Path $PSScriptRoot 'data/raw'
New-Item -ItemType Directory -Force -Path $rawDir | Out-Null
$existing = Get-ChildItem -LiteralPath $rawDir -Filter 'ems_incident_dispatch_2024-01_to_2026-06_part*.csv' -File -ErrorAction SilentlyContinue
if ($existing) {
    throw "Raw extract files already exist in $rawDir. Move them to a dated archive before starting a fresh download; this script will not overwrite them."
}

$where = "incident_datetime >= '$StartDate' AND incident_datetime < '$EndDateExclusive'"
$selectQuery = "`$select=count(*)&`$where=$([uri]::EscapeDataString($where))"
$countResponse = Invoke-RestMethod -Uri "https://data.cityofnewyork.us/resource/$datasetId.json`?$selectQuery" -TimeoutSec 120
$expected = [long]$countResponse[0].count
Write-Host "Expected records: $expected"

$downloaded = 0L
$part = 0
while ($downloaded -lt $expected) {
    $query = "`$where=$([uri]::EscapeDataString($where))&`$limit=$PageSize&`$offset=$downloaded"
    $response = Invoke-WebRequest -Uri "$apiRoot`?$query" -TimeoutSec 180 -Headers @{ 'Accept' = 'text/csv' }
    $content = $response.Content
    if ([string]::IsNullOrWhiteSpace($content)) { throw "Empty response at offset $downloaded" }
    $file = Join-Path $rawDir ('ems_incident_dispatch_2024-01_to_2026-06_part{0:D3}.csv' -f $part)
    [System.IO.File]::WriteAllText($file, $content, [System.Text.UTF8Encoding]::new($false))
    $rowCount = ([regex]::Matches($content, "`n")).Count
    if (-not $content.EndsWith("`n")) { $rowCount++ }
    $rowsInPart = [Math]::Max(0, $rowCount - 1)
    if ($rowsInPart -le 0) { throw "No data rows at offset $downloaded" }
    $downloaded += $rowsInPart
    Write-Host "Saved part $part ($rowsInPart rows; $downloaded / $expected)"
    $part++
    if ($rowsInPart -lt $PageSize -and $downloaded -lt $expected) {
        throw "Short page at offset $($downloaded - $rowsInPart); expected $expected rows, received $downloaded"
    }
}

if ($downloaded -ne $expected) { throw "Row-count mismatch: expected $expected, downloaded $downloaded" }
Write-Host "Download complete: $downloaded rows in $part files."
