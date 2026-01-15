#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Load .env without printing values
if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi

echo "Dental PMS health"

docker compose ps

echo
echo "Backend:"
curl -fsS http://localhost:8100/health

echo
echo "Frontend proxy:"
frontend_ok=0
for attempt in $(seq 1 10); do
  if curl -fsS http://localhost:3100/api/health >/dev/null; then
    frontend_ok=1
    break
  fi
  sleep 1
done
if [ "$frontend_ok" -ne 1 ]; then
  echo "Frontend proxy: failed after retries"
  exit 1
fi
echo "Frontend proxy: ok"

echo
echo "Auth + data (using ADMIN_EMAIL/ADMIN_PASSWORD from .env):"
ADMIN_EMAIL="${ADMIN_EMAIL:-}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-}"
if [ -z "$ADMIN_EMAIL" ]; then
  ADMIN_EMAIL=$(grep -E '^ADMIN_EMAIL=' .env | cut -d= -f2- || true)
fi
if [ -z "$ADMIN_PASSWORD" ]; then
  ADMIN_PASSWORD=$(grep -E '^ADMIN_PASSWORD=' .env | cut -d= -f2- || true)
fi
if [ -z "$ADMIN_EMAIL" ] || [ -z "$ADMIN_PASSWORD" ]; then
  echo "Health auth failed: missing ADMIN_EMAIL/ADMIN_PASSWORD"
  exit 1
fi

LOGIN_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST http://localhost:3100/api/auth/login \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"${ADMIN_EMAIL}\",\"password\":\"${ADMIN_PASSWORD}\"}")
LOGIN_CODE="${LOGIN_RESPONSE##*$'\n'}"
LOGIN_JSON="${LOGIN_RESPONSE%$'\n'*}"
if [ "$LOGIN_CODE" != "200" ]; then
  LOGIN_KEYS="$(
    LOGIN_JSON="$LOGIN_JSON" python3 - <<'PY'
import json
import os

raw = os.environ.get("LOGIN_JSON", "")
try:
    data = json.loads(raw) if raw else {}
except json.JSONDecodeError:
    data = {}
print("keys=" + ",".join(sorted(data.keys())))
PY
  )"
  echo "Health auth failed: login HTTP ${LOGIN_CODE} (${LOGIN_KEYS})"
  exit 1
fi
TOKEN="$(
  LOGIN_JSON="$LOGIN_JSON" python3 - <<'PY'
import json
import os

raw = os.environ.get("LOGIN_JSON", "")
data = json.loads(raw) if raw else {}
print(data.get("access_token") or data.get("accessToken") or "")
PY
)"
if [ -z "$TOKEN" ]; then
  LOGIN_KEYS="$(
    LOGIN_JSON="$LOGIN_JSON" python3 - <<'PY'
import json
import os

data = json.loads(os.environ.get("LOGIN_JSON", "") or "{}")
print("keys=" + ",".join(sorted(data.keys())))
PY
  )"
  echo "Health auth failed: token missing (${LOGIN_KEYS})"
  exit 1
fi

curl -fsS http://localhost:3100/api/patients -H "Authorization: Bearer $TOKEN" >/dev/null
curl -fsS http://localhost:3100/api/audit -H "Authorization: Bearer $TOKEN" >/dev/null
echo "Auth checks: OK"
