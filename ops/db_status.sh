#!/usr/bin/env bash
set -euo pipefail

ROOT="$HOME/dental-pms"
cd "$ROOT"

current="$(docker compose exec backend sh -lc 'python -m alembic current' | tail -n 1 | awk '{print $1}')"
head_rev="$(docker compose exec backend sh -lc 'python -m alembic heads' | tail -n 1 | awk '{print $1}')"

if [ -z "${current:-}" ] || [ -z "${head_rev:-}" ]; then
  echo "Migration status: unknown (could not read revisions)"
  exit 1
fi

echo "Alembic current: ${current}"
echo "Alembic head:    ${head_rev}"

if [ "$current" = "$head_rev" ]; then
  echo "Migration status: OK"
else
  echo "Migration status: BEHIND"
  echo "Run: ops/db_upgrade.sh"
fi
