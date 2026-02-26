# seed_geo.ps1
# Automates Tier 1 Geographic Seeding

$downloadUrl = "https://download.geonames.org/export/dump/cities15000.zip"
$zipPath = "cities.zip"
$txtPath = "cities15000.txt"
$sqlPath = "database/ingestion/geo/ingest_geonames.sql"

Write-Host "--- Starting Tier 1 Seeding ---"

if (-not (Test-Path $zipPath)) {
    Write-Host "Downloading GeoNames dataset..."
    Invoke-WebRequest -Uri $downloadUrl -OutFile $zipPath
}

Write-Host "Extracting dataset..."
Expand-Archive -Path $zipPath -DestinationPath "." -Force

Write-Host "Copying data into database container..."
docker cp $txtPath pia_postgres:/tmp/cities15000.txt

Write-Host "Executing SQL ingestion script..."
docker exec pia_postgres psql -U pia -d pia -f /tmp/ingest_geonames.sql

Write-Host "--- Tier 1 Seeding Complete ---"
