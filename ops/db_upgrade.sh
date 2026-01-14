#!/usr/bin/env bash
set -euo pipefail

ROOT="$HOME/dental-pms"
cd "$ROOT"

docker compose exec backend sh -lc 'python -m alembic upgrade head'
