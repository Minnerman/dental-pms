# Stage 53 Backup + Restore Drill Report

- Date: 2026-02-03_234315
- Branch: stage53-backup-restore-drill
- Commit: db1000b
- Drill mode: Option A (isolated compose project)
- Compose project: dentalpms_drill_20260203234315

## Services and Volumes
- Services: backend, db, frontend, r4_import
- Volumes: dental_pms_db_data, dental_pms_attachments
- Attachment mount: backend `/data` (attachments under `/data/attachments`)

## Backup Artefacts (not committed)
- DB dump: `.run/stage53/db_2026-02-03_234315.sql` (50M)
- Uploads archive: `.run/stage53/uploads_2026-02-03_234315.tgz` (122B)

## Restore Steps Executed
1. Started isolated stack with `COMPOSE_PROJECT_NAME=dentalpms_drill_20260203234315`.
2. Verified env and app health (`ops/env_check.sh`, `ops/health.sh`).
3. Restored attachments archive into `dentalpms_drill_20260203234315_dental_pms_attachments`.
4. Dropped and recreated DB schema in drill DB (`DROP SCHEMA public CASCADE; CREATE SCHEMA public;`).
5. Restored DB dump with strict mode (`psql -v ON_ERROR_STOP=1 ...`).
6. Re-ran health checks post-restore.

## Verification Evidence
- Health: `.run/stage53/health_2026-02-03_234315.log` (green)
- DB table listing: `.run/stage53/db_tables_2026-02-03_234315.txt`
- Counts after restore:
  - patients: 477
  - appointments: 200
  - r4_bpe_entries: 1
  - r4_bpe_furcations: 0
  - r4_perio_probes: 0
  - attachment files in `/data/attachments`: 0
- Alembic current: `0048_r4_charting_canonical_content_hash (head)`

## Notes
- Backup binaries (`*.sql`, `*.tgz`) are intentionally kept out of git.
- Drill used isolated compose project to avoid impacting the default project volumes.
