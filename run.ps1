$ErrorActionPreference = "Stop"

docker compose up postgres adminer -d
docker compose run --rm python
docker compose run --rm dbt
