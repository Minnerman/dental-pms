#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

ARCHIVE="dbdata.tgz"
if [ ! -f "$ARCHIVE" ]; then
  echo "Archive not found: $ARCHIVE"
  exit 1
fi

docker run --rm -v dental-pms_dental_pms_db_data:/v -v "$PWD":/b \
  busybox sh -c "rm -rf /v/* && tar -xzf /b/${ARCHIVE} -C /v"

echo "Restore complete from: ${ARCHIVE}"
