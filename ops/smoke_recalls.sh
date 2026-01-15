#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi

APP_ENV="${APP_ENV:-}"
ALLOW_DEV_SEED="${ALLOW_DEV_SEED:-0}"
if [ "$APP_ENV" != "development" ] && [ "$ALLOW_DEV_SEED" != "1" ]; then
  echo "Refusing to run smoke: set APP_ENV=development or ALLOW_DEV_SEED=1"
  exit 1
fi

ADMIN_EMAIL="${ADMIN_EMAIL:-}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-}"
if [ -z "$ADMIN_EMAIL" ]; then
  ADMIN_EMAIL=$(grep -E '^ADMIN_EMAIL=' .env | cut -d= -f2- || true)
fi
if [ -z "$ADMIN_PASSWORD" ]; then
  ADMIN_PASSWORD=$(grep -E '^ADMIN_PASSWORD=' .env | cut -d= -f2- || true)
fi
if [ -z "$ADMIN_EMAIL" ] || [ -z "$ADMIN_PASSWORD" ]; then
  echo "Missing ADMIN_EMAIL/ADMIN_PASSWORD in .env" >&2
  exit 1
fi

FRONTEND_PORT="${FRONTEND_PORT:-3100}"
FRONTEND_BASE_URL="http://localhost:${FRONTEND_PORT}"

LOGIN_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${FRONTEND_BASE_URL}/api/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${ADMIN_EMAIL}\",\"password\":\"${ADMIN_PASSWORD}\"}")
LOGIN_CODE=$(printf "%s" "$LOGIN_RESPONSE" | tail -n 1)
LOGIN_JSON=$(printf "%s" "$LOGIN_RESPONSE" | head -n -1)
if [ "$LOGIN_CODE" != "200" ]; then
  echo "Login failed with HTTP ${LOGIN_CODE}" >&2
  exit 1
fi
TOKEN=$(LOGIN_JSON="$LOGIN_JSON" python3 - <<'PY'
import json
import os
raw = os.environ.get("LOGIN_JSON", "")
try:
    data = json.loads(raw)
except json.JSONDecodeError:
    data = {}
print(data.get("access_token") or data.get("accessToken") or "")
PY
)
if [ -z "$TOKEN" ]; then
  echo "Login failed: token missing" >&2
  exit 1
fi

DB_USER=$(docker compose exec -T db sh -lc 'echo ${POSTGRES_USER:-}')
DB_NAME=$(docker compose exec -T db sh -lc 'echo ${POSTGRES_DB:-}')
if [ -z "$DB_USER" ] || [ -z "$DB_NAME" ]; then
  echo "Unable to determine POSTGRES_USER/POSTGRES_DB from db container" >&2
  exit 1
fi
RECALL_ID=$(docker compose exec -T db psql -U "$DB_USER" -d "$DB_NAME" -Atc "select id from patient_recalls order by id desc limit 1;")
if [ -z "$RECALL_ID" ]; then
  echo "No patient_recalls rows found. Run ops/seed_recalls_dev.sh first." >&2
  exit 1
fi

LIST_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  "${FRONTEND_BASE_URL}/api/recalls?limit=1" \
  -H "Authorization: Bearer $TOKEN")
if [ "$LIST_CODE" != "200" ]; then
  echo "Recalls list failed with HTTP ${LIST_CODE}" >&2
  exit 1
fi

timestamp=$(date -u +"%Y-%m-%dT%H:%M:%S")

curl -fsS "${FRONTEND_BASE_URL}/api/recalls/export_count" -H "Authorization: Bearer $TOKEN" >/dev/null
curl -fsS "${FRONTEND_BASE_URL}/api/recalls/export_count" -H "Authorization: Bearer $TOKEN" >/dev/null
curl -fsS -X POST "${FRONTEND_BASE_URL}/api/recalls/${RECALL_ID}/contact" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"method":"phone","outcome":"smoke test"}' >/dev/null
curl -fsS "${FRONTEND_BASE_URL}/api/recalls/export_count" -H "Authorization: Bearer $TOKEN" >/dev/null

sleep 1

log_output=$(docker compose logs --since "$timestamp" backend)
if command -v rg >/dev/null; then
  match_miss=$(printf "%s" "$log_output" | rg -n "cache=miss" -S || true)
  match_hit=$(printf "%s" "$log_output" | rg -n "cache=hit" -S || true)
  match_invalidate=$(printf "%s" "$log_output" | rg -n "export_count_cache_invalidate" -S || true)
else
  match_miss=$(printf "%s" "$log_output" | grep -E "cache=miss" || true)
  match_hit=$(printf "%s" "$log_output" | grep -E "cache=hit" || true)
  match_invalidate=$(printf "%s" "$log_output" | grep -E "export_count_cache_invalidate" || true)
fi

if [ -z "$match_miss" ] || [ -z "$match_hit" ] || [ -z "$match_invalidate" ]; then
  echo "Smoke failed: missing expected cache logs" >&2
  echo "$log_output" >&2
  exit 1
fi

echo "Smoke OK: recalls list, export_count cache hit/miss, invalidation logged."
