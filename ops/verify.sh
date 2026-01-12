#!/usr/bin/env bash
set -euo pipefail

ROOT="$HOME/dental-pms"
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
echo "Health check..."
./ops/health.sh
