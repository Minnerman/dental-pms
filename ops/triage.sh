#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

section() {
  echo
  echo "=== $1 ==="
}

section "timestamp"
date -u +"%Y-%m-%dT%H:%M:%SZ"

section "docker compose ps"
docker compose ps

section "health check"
set +e
bash ops/health.sh
health_rc=$?
set -e
echo "health_exit_code=$health_rc"

section "backend logs (last 100)"
docker compose logs --tail=100 backend || true

section "frontend logs (last 100)"
docker compose logs --tail=100 frontend || true

section "db logs (last 100)"
docker compose logs --tail=100 db || true

section "disk usage"
df -h
