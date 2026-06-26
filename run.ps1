$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "=== Edikted Shipments Pipeline ==="
Write-Host ""

# Verify src/ has files
$srcFiles = Get-ChildItem -Path ".\src" -ErrorAction SilentlyContinue
if (-not $srcFiles) {
    Write-Host "ERROR: ./src/ is empty."
    Write-Host "Download raw files from S3 first:"
    Write-Host "  docker compose run --rm python python download.py"
    exit 1
}
Write-Host "Found $($srcFiles.Count) file(s) in ./src/"

# 1. Start postgres + support services
Write-Host "[1/4] Starting postgres, adminer, jupyter..."
docker compose up postgres adminer jupyter -d --build --remove-orphans

Write-Host "Waiting for postgres to be healthy..."
$retries = 20
while ($retries -gt 0) {
    $health = docker inspect --format "{{.State.Health.Status}}" (docker compose ps -q postgres) 2>$null
    if ($health -eq "healthy") { break }
    Start-Sleep -Seconds 3
    $retries--
}
if ($retries -eq 0) { throw "Postgres did not become healthy in time." }

# 2. Load ./src into raw.*
Write-Host "[2/4] Loading ./src into PostgreSQL raw.*..."
docker compose run --rm python

# 3. Run dbt
Write-Host "[3/4] Running dbt (staging + fact + tests)..."
docker compose run --rm dbt

# 4. Build and start API + dashboard
Write-Host "[4/4] Building and starting API and dashboard..."
docker compose up api dashboard -d --build --remove-orphans

Write-Host ""
Write-Host "=== Ready ==="
Write-Host "  Dashboard : http://localhost:8501"
Write-Host "  API docs  : http://localhost:7654/docs"
Write-Host "  Adminer   : http://localhost:8080"
Write-Host "  Jupyter   : http://localhost:8888"
Write-Host ""
