#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ ! -f "frontend/package.json" ]; then
  echo "frontend/package.json not found; cannot run typecheck."
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm not found; skipping typecheck."
  exit 0
fi

npm --prefix frontend run typecheck
