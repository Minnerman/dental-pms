#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

bash ops/env_check.sh

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

echo
echo "Config check..."
BACKEND_PORT="${BACKEND_PORT:-8100}"
if [ -f .env ]; then
  set -a
  . ./.env
  set +a
  BACKEND_PORT="${BACKEND_PORT:-8100}"
fi
CONFIG_JSON="$(curl -fsS "http://localhost:${BACKEND_PORT}/config")"
CONFIG_OK="$(
  CONFIG_JSON="$CONFIG_JSON" python3 - <<'PY'
import json
import os

raw = os.environ.get("CONFIG_JSON", "")
try:
    data = json.loads(raw)
except json.JSONDecodeError:
    data = {}
flags = data.get("feature_flags", {})
value = flags.get("charting_viewer")
print("ok" if isinstance(value, bool) else "bad")
PY
)"
if [ "$CONFIG_OK" != "ok" ]; then
  echo "Config check failed: missing feature_flags.charting_viewer boolean"
  exit 1
fi
