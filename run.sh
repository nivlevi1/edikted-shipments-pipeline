#!/usr/bin/env bash
set -euo pipefail

echo ""
echo "=== Edikted Shipments Pipeline ==="
echo ""

# Verify src/ has files
src_count=$(ls ./src 2>/dev/null | wc -l)
if [ "$src_count" -eq 0 ]; then
    echo "ERROR: ./src/ is empty."
    echo "Download raw files from S3 first:"
    echo "  docker compose run --rm python python download.py"
    exit 1
fi
echo "Found $src_count file(s) in ./src/"

# 1. Start postgres + support services
echo "[1/4] Starting postgres, adminer, jupyter..."
docker compose up postgres adminer jupyter -d --build --remove-orphans

echo "Waiting for postgres to be healthy..."
retries=20
until docker inspect --format "{{.State.Health.Status}}" \
    "$(docker compose ps -q postgres)" 2>/dev/null | grep -q "healthy"; do
    retries=$((retries - 1))
    [ $retries -le 0 ] && echo "ERROR: postgres did not become healthy." && exit 1
    sleep 3
done

# 2. Load ./src into raw.*
echo "[2/4] Loading ./src into PostgreSQL raw.*..."
docker compose run --rm python

# 3. Run dbt
echo "[3/4] Running dbt (staging + fact + tests)..."
docker compose run --rm dbt

# 4. Build and start API + dashboard
echo "[4/4] Building and starting API and dashboard..."
docker compose up api dashboard -d --build --remove-orphans

echo ""
echo "=== Ready ==="
echo "  Dashboard : http://localhost:8501"
echo "  API docs  : http://localhost:7654/docs"
echo "  Adminer   : http://localhost:8080"
echo "  Jupyter   : http://localhost:8888"
echo ""
