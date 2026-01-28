#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  cat <<'EOF'
Usage:
  bash ops/run_backend_script.sh <script_path> [args...]

Example:
  bash ops/run_backend_script.sh scripts/ng_person_lookup.py --surname "SMITH" --dob 1970-01-01
EOF
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

docker compose run --rm \
  -v "$REPO_ROOT:/app" \
  -w /app \
  -e DATABASE_URL \
  backend \
  python "$@"
