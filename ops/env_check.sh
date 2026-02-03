#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ENV_FILE="${ENV_FILE:-.env}"

if [ ! -f "$ENV_FILE" ]; then
  echo "Env check failed: missing $ENV_FILE"
  echo "Create it from .env.example:"
  echo "  cp .env.example .env"
  exit 1
fi

# Load .env to validate required keys in one place before health/verify work.
set -a
. "$ENV_FILE"
set +a

required_vars=(
  POSTGRES_DB
  POSTGRES_USER
  POSTGRES_PASSWORD
  POSTGRES_PORT
  BACKEND_PORT
  FRONTEND_PORT
  APP_ENV
  SECRET_KEY
  JWT_SECRET
  JWT_ALG
  ACCESS_TOKEN_EXPIRE_MINUTES
  RESET_TOKEN_EXPIRE_MINUTES
  RESET_TOKEN_DEBUG
  RESET_REQUESTS_PER_MINUTE
  RESET_CONFIRM_PER_MINUTE
  ADMIN_EMAIL
  ADMIN_PASSWORD
)

missing=0

usage_hint() {
  case "$1" in
    POSTGRES_DB|POSTGRES_USER|POSTGRES_PASSWORD|POSTGRES_PORT)
      echo "docker-compose.yml (db/backend services)"
      ;;
    BACKEND_PORT|FRONTEND_PORT)
      echo "docker-compose.yml port mapping + ops/health.sh"
      ;;
    APP_ENV|SECRET_KEY|JWT_SECRET|JWT_ALG|ACCESS_TOKEN_EXPIRE_MINUTES|RESET_TOKEN_EXPIRE_MINUTES|RESET_TOKEN_DEBUG|RESET_REQUESTS_PER_MINUTE|RESET_CONFIRM_PER_MINUTE)
      echo "backend runtime config (backend/app/core/settings.py)"
      ;;
    ADMIN_EMAIL|ADMIN_PASSWORD)
      echo "bootstrap admin + ops/health.sh auth checks"
      ;;
    *)
      echo "project runtime configuration"
      ;;
  esac
}

example_value() {
  case "$1" in
    POSTGRES_DB) echo "dental_pms" ;;
    POSTGRES_USER) echo "dental_pms" ;;
    POSTGRES_PASSWORD) echo "change-me" ;;
    POSTGRES_PORT) echo "5432" ;;
    BACKEND_PORT) echo "8000" ;;
    FRONTEND_PORT) echo "3000" ;;
    APP_ENV) echo "development" ;;
    SECRET_KEY) echo "replace-with-32-plus-char-secret-key" ;;
    JWT_SECRET) echo "replace-with-32-plus-char-jwt-secret" ;;
    JWT_ALG) echo "HS256" ;;
    ACCESS_TOKEN_EXPIRE_MINUTES) echo "120" ;;
    RESET_TOKEN_EXPIRE_MINUTES) echo "30" ;;
    RESET_TOKEN_DEBUG) echo "false" ;;
    RESET_REQUESTS_PER_MINUTE) echo "5" ;;
    RESET_CONFIRM_PER_MINUTE) echo "10" ;;
    ADMIN_EMAIL) echo "admin@example.com" ;;
    ADMIN_PASSWORD) echo "ChangeMe123!" ;;
    *) echo "<value>" ;;
  esac
}

for var in "${required_vars[@]}"; do
  value="${!var:-}"
  if [ -z "$value" ]; then
    missing=1
    echo "Env check failed: missing $var"
    echo "  used by: $(usage_hint "$var")"
    echo "  set in .env, e.g.: $var=$(example_value "$var")"
  fi
done

if [ "${missing}" -ne 0 ]; then
  exit 1
fi

if [ "${#ADMIN_PASSWORD}" -lt 12 ]; then
  echo "Env check failed: ADMIN_PASSWORD must be at least 12 characters"
  exit 1
fi

echo "Env check: OK ($ENV_FILE)"
