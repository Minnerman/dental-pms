#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."  # repo root

read -r -p "Admin email to reset: " EMAIL
read -r -s -p "New password (won't echo): " PASS
echo
echo "Password length entered: ${#PASS}"
if [ "${#PASS}" -lt 4 ]; then
  echo "ERROR: password looks empty/too short"
  exit 1
fi

printf '%s\n%s\n' "$EMAIL" "$PASS" | docker compose exec -T backend python -c '
import sys
from app.db.session import SessionLocal
from app.models.user import User
from app.core.security import hash_password, verify_password

email = sys.stdin.readline().strip().lower()
pwd = sys.stdin.readline().rstrip("\n")

db = SessionLocal()
u = db.query(User).filter(User.email == email).first()
assert u, f"User not found: {email}"

u.hashed_password = hash_password(pwd)
u.is_active = True
u.must_change_password = True
db.commit()

u2 = db.query(User).filter(User.email == email).first()
ok = verify_password(pwd, u2.hashed_password)
print("DB reset OK. verify_password ->", bool(ok))
assert ok, "Hash verification failed"
'

docker compose restart backend

# wait for healthy
for i in $(seq 1 60); do
  status="$(docker inspect -f '{{.State.Health.Status}}' dental_pms_backend 2>/dev/null || echo starting)"
  echo "backend health: $status"
  [ "$status" = "healthy" ] && break
  sleep 1
done

# tests (no output body)
code="$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Content-Type: application/json" \
  -X POST "http://127.0.0.1:8100/auth/login" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}")"
echo "Direct backend login HTTP: $code"

code2="$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Content-Type: application/json" \
  -X POST "http://127.0.0.1:3100/api/auth/login" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}")"
echo "Frontend proxy login HTTP: $code2"

echo "Done."
