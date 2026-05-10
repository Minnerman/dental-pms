#!/usr/bin/env bash
set -euo pipefail

# Non-secret rclone upload runner scaffold.
# Do not run without explicit owner/operator authorisation.
# Credentials, generated rclone config, and crypt secrets must live outside Git.
# Destination is Google Workspace / owner-controlled online storage.
# Non-live restore proof remains required before any production cutover.

required_vars=(
  RCLONE_CONFIG
  BACKUP_SOURCE_ARCHIVE
  BACKUP_DESTINATION
)

missing_vars=()
for var_name in "${required_vars[@]}"; do
  if [ -z "${!var_name:-}" ]; then
    missing_vars+=("${var_name}")
  fi
done

if [ "${#missing_vars[@]}" -gt 0 ]; then
  printf 'missing_required_env=%s\n' "$(IFS=,; echo "${missing_vars[*]}")" >&2
  exit 2
fi

echo "backup_runner=backup_rclone_upload"
echo "dry_run_default=true"
echo "confirmation_status=${BACKUP_UPLOAD_CONFIRM:-not_set}"
echo 'redacted_command_shape=rclone copy "$BACKUP_SOURCE_ARCHIVE" "$BACKUP_DESTINATION" --config "$RCLONE_CONFIG"'

if [ "${BACKUP_UPLOAD_CONFIRM:-}" != "UPLOAD_TO_OWNER_CONTROLLED_STORAGE" ]; then
  echo "dry_run=true"
  echo "refusing_real_upload_without_confirmation=BACKUP_UPLOAD_CONFIRM=UPLOAD_TO_OWNER_CONTROLLED_STORAGE"
  exit 0
fi

echo "dry_run=false"
echo "real_upload_confirmation=accepted"

if ! command -v rclone >/dev/null 2>&1; then
  echo "rclone_not_found=true" >&2
  exit 2
fi

if [ ! -f "${RCLONE_CONFIG}" ]; then
  echo "rclone_config_file_unavailable=true" >&2
  echo "rclone_config_path_not_printed=true" >&2
  exit 2
fi

if [ ! -f "${BACKUP_SOURCE_ARCHIVE}" ]; then
  echo "backup_source_archive_unavailable=true" >&2
  echo "backup_source_archive_path_not_printed=true" >&2
  exit 2
fi

rclone copy "${BACKUP_SOURCE_ARCHIVE}" "${BACKUP_DESTINATION}" --config "${RCLONE_CONFIG}"
echo "backup_upload_status=completed"
