#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

ARCHIVE="dbdata.tgz"
docker run --rm -v dental-pms_dental_pms_db_data:/v -v "$PWD":/b \
  busybox tar -czf "/b/${ARCHIVE}" -C /v .

echo "Backup complete: ${ARCHIVE}"
