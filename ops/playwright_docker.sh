#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR"

COMPOSE_FILES=(-f docker-compose.yml -f docker-compose.playwright.yml)

# Optional clean run; note this removes volumes.
if [ "${PLAYWRIGHT_CLEAN:-}" = "1" ]; then
  docker compose "${COMPOSE_FILES[@]}" down -v
fi

docker compose "${COMPOSE_FILES[@]}" up -d backend frontend
docker compose "${COMPOSE_FILES[@]}" run --rm playwright "$@"
