#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ "${SKIP_DOCKER_BUILD:-0}" != "1" ]; then
  echo "Building containers..."
  docker compose build
fi

echo "Starting containers..."
docker compose up -d

echo
echo "Frontend production build..."
docker compose run --rm --no-deps frontend sh -lc 'set -eux; NODE_ENV=production npm run build'

echo
echo "Typecheck..."
./ops/typecheck.sh

echo
echo "Health check..."
./ops/health.sh
