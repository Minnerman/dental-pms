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
mkdir -p "$BACKUP_ROOT"

timestamp="$(date +%Y-%m-%d_%H%M%S)"
archive_name="attachments_${timestamp}.tgz"
backup_file="$BACKUP_ROOT/$archive_name"
source_desc=""

if [ -n "${ATTACHMENTS_PATH:-}" ]; then
  if [ ! -d "$ATTACHMENTS_PATH" ]; then
    echo "ATTACHMENTS_PATH does not exist: $ATTACHMENTS_PATH" >&2
    exit 1
  fi
  tar -czf "$backup_file" -C "$ATTACHMENTS_PATH" .
  source_desc="path:$ATTACHMENTS_PATH"
else
  backend_container="$(docker compose ps -q backend)"
  if [ -z "$backend_container" ]; then
    echo "backend container not found; set ATTACHMENTS_PATH or start the stack" >&2
    exit 1
  fi

  mount_info="$(docker inspect --format '{{range .Mounts}}{{if eq .Destination "/data"}}{{.Type}}|{{.Name}}|{{.Source}}{{end}}{{end}}' "$backend_container")"
  if [ -z "$mount_info" ]; then
    echo "unable to resolve backend /data mount" >&2
    exit 1
  fi

  IFS='|' read -r mount_type mount_name mount_source <<<"$mount_info"
  case "$mount_type" in
    volume)
      docker run --rm -v "$mount_name:/v:ro" -v "$BACKUP_ROOT:/b" alpine:3.20 sh -lc "tar -czf '/b/$archive_name' -C /v ."
      source_desc="volume:$mount_name"
      ;;
    bind)
      tar -czf "$backup_file" -C "$mount_source" .
      source_desc="bind:$mount_source"
      ;;
    *)
      echo "unsupported mount type for /data: $mount_type" >&2
      exit 1
      ;;
  esac
fi

if [ ! -s "$backup_file" ]; then
  echo "attachments backup failed: $backup_file is empty" >&2
  exit 1
fi

deleted_count="$(prune_old "$BACKUP_ROOT" 'attachments_*.tgz' "$BACKUP_KEEP")"
size_bytes="$(wc -c <"$backup_file" | tr -d ' ')"

echo "backup_type=attachments"
echo "backup_root=$BACKUP_ROOT"
echo "backup_file=$backup_file"
echo "backup_size_bytes=$size_bytes"
echo "attachments_source=$source_desc"
echo "retention_keep=$BACKUP_KEEP"
echo "retention_deleted=$deleted_count"
