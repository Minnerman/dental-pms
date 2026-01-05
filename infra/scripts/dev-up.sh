#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
cp -n .env.example .env || true
docker compose up -d --build
echo "Up. Backend: http://localhost:8000/health  Frontend: http://localhost:3000"
