#!/usr/bin/env bash
set -euo pipefail

ROOT="$HOME/dental-pms"
cd "$ROOT"

echo "Dental PMS health"

docker compose ps

echo
echo "Backend:"
curl -fsS http://localhost:8100/health

echo
echo "Frontend proxy:"
curl -fsS http://localhost:3100/api/health

echo
echo "Auth + data (using ADMIN_EMAIL/ADMIN_PASSWORD from .env):"
ADMIN_EMAIL=$(grep -E '^ADMIN_EMAIL=' .env | cut -d= -f2-)
ADMIN_PASSWORD=$(grep -E '^ADMIN_PASSWORD=' .env | cut -d= -f2-)
LOGIN_JSON=$(curl -s -X POST http://localhost:3100/api/auth/login \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"${ADMIN_EMAIL}\",\"password\":\"${ADMIN_PASSWORD}\"}")
TOKEN=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])' <<<"$LOGIN_JSON")

curl -fsS http://localhost:3100/api/patients -H "Authorization: Bearer $TOKEN" >/dev/null
curl -fsS http://localhost:3100/api/audit -H "Authorization: Bearer $TOKEN" >/dev/null
echo "Auth checks: OK"
