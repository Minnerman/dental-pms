#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

default_backup_root() {
  if [ -n "${BACKUP_DIR:-}" ]; then
    printf '%s\n' "$BACKUP_DIR"
    return
  fi
  if [ -d "/srv/dental-pms/backups" ]; then
    printf '%s\n' "/srv/dental-pms/backups"
    return
  fi
  printf '%s\n' "$ROOT_DIR/.run/backups"
}

validate_keep_count() {
  if ! [[ "$1" =~ ^[0-9]+$ ]]; then
    echo "BACKUP_KEEP must be a non-negative integer" >&2
    exit 1
  fi
}

prune_old() {
  local dir="$1"
  local pattern="$2"
  local keep="$3"
  local files=()
  local delete_count=0

  mapfile -t files < <(find "$dir" -maxdepth 1 -type f -name "$pattern" -printf '%f\n' | sort)
  if [ "${#files[@]}" -le "$keep" ]; then
    printf '0\n'
    return
  fi

  delete_count=$(("${#files[@]}" - keep))
  for ((i = 0; i < delete_count; i++)); do
    rm -f -- "$dir/${files[$i]}"
  done
  printf '%s\n' "$delete_count"
}

BACKUP_ROOT="$(default_backup_root)"
BACKUP_KEEP="${BACKUP_KEEP:-14}"
validate_keep_count "$BACKUP_KEEP"

DB_DIR="$BACKUP_ROOT/db"
mkdir -p "$DB_DIR"

timestamp="$(date +%Y-%m-%d_%H%M%S)"
backup_file="$DB_DIR/db_${timestamp}.sql.gz"

docker compose exec -T db sh -lc 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB"' | gzip -c >"$backup_file"

if [ ! -s "$backup_file" ]; then
  echo "DB backup failed: $backup_file is empty" >&2
  exit 1
fi

deleted_count="$(prune_old "$DB_DIR" 'db_*.sql.gz' "$BACKUP_KEEP")"
size_bytes="$(wc -c <"$backup_file" | tr -d ' ')"

echo "backup_type=db"
echo "backup_root=$BACKUP_ROOT"
echo "backup_file=$backup_file"
echo "backup_size_bytes=$size_bytes"
echo "retention_keep=$BACKUP_KEEP"
echo "retention_deleted=$deleted_count"
