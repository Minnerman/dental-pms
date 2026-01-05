#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root_dir"

if [ $# -ne 1 ]; then
  echo "Usage: CONFIRM=YES ./ops/db_restore.sh <backup.sql>" >&2
  exit 1
fi

backup_file="$1"

if [ ! -f "$backup_file" ]; then
  echo "Backup file not found: $backup_file" >&2
  exit 1
fi

if [ "${CONFIRM:-}" != "YES" ]; then
  echo "Refusing to restore without CONFIRM=YES" >&2
  exit 1
fi

container_id="$(docker compose ps -q db)"
if [ -z "$container_id" ]; then
  echo "db container not found; is the compose stack running?" >&2
  exit 1
fi

if ! docker compose exec -T db sh -lc 'command -v psql >/dev/null'; then
  echo "psql not found in db container" >&2
  exit 1
fi

docker compose exec -T db sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < "$backup_file"

echo "Restore completed from: $backup_file"
