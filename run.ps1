$ErrorActionPreference = "Stop"

docker compose up postgres adminer jupyter -d
docker compose run --rm python
docker compose run --rm dbt

Write-Host ""
Write-Host "Pipeline done. Jupyter: http://localhost:8888"
