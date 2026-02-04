#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

extract_value() {
  local key="$1"
  local data="$2"
  awk -F= -v k="$key" '$1 == k {print substr($0, index($0, "=") + 1)}' <<<"$data" | tail -n 1
}

start_epoch="$(date +%s)"

db_output="$(bash "$ROOT_DIR/ops/backup_db.sh")"
attachments_output="$(bash "$ROOT_DIR/ops/backup_attachments.sh")"

db_file="$(extract_value backup_file "$db_output")"
db_size="$(extract_value backup_size_bytes "$db_output")"
backup_root="$(extract_value backup_root "$db_output")"

attachments_file="$(extract_value backup_file "$attachments_output")"
attachments_size="$(extract_value backup_size_bytes "$attachments_output")"
attachments_source="$(extract_value attachments_source "$attachments_output")"

end_epoch="$(date +%s)"
duration_seconds=$((end_epoch - start_epoch))

echo "$db_output"
echo "$attachments_output"
echo "backup_run_status=ok"
echo "duration_seconds=$duration_seconds"
echo "backup_root=$backup_root"
echo "db_file=$db_file"
echo "db_size_bytes=$db_size"
echo "attachments_file=$attachments_file"
echo "attachments_size_bytes=$attachments_size"
echo "attachments_source=$attachments_source"
