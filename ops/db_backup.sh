#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root_dir"

mkdir -p backups

container_id="$(docker compose ps -q db)"
if [ -z "$container_id" ]; then
  echo "db container not found; is the compose stack running?" >&2
  exit 1
fi

timestamp="$(date +%Y%m%d-%H%M)"
backup_file="backups/dental-pms-${timestamp}.sql"

if ! docker compose exec -T db sh -lc 'command -v pg_dump >/dev/null'; then
  echo "pg_dump not found in db container" >&2
  exit 1
fi

docker compose exec -T db sh -lc 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB"' > "$backup_file"

echo "Backup completed: $backup_file"
