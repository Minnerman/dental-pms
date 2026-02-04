# Ops Backups (Stage 56)

## Scope
- DB logical backup: PostgreSQL `pg_dump` from compose `db`.
- Attachments backup: backend `/data` mount (volume or bind), with `ATTACHMENTS_PATH` override.
- Rotation: keep last `BACKUP_KEEP` files per stream (default `14`).

## Backup location
- Default resolution order:
  1) `BACKUP_DIR` (if set)
  2) `/srv/dental-pms/backups` (if this directory already exists)
  3) `./.run/backups` (repo-local fallback)
- DB backups are written to `db/db_YYYY-MM-DD_HHMMSS.sql.gz`.
- Attachments backups are written to `attachments_YYYY-MM-DD_HHMMSS.tgz`.

## Manual run
```bash
bash ops/backup_db.sh
bash ops/backup_attachments.sh
bash ops/backup_run.sh
```

Optional overrides:
```bash
BACKUP_DIR=/srv/dental-pms/backups BACKUP_KEEP=21 bash ops/backup_run.sh
ATTACHMENTS_PATH=/srv/dental-pms/attachments BACKUP_KEEP=14 bash ops/backup_attachments.sh
```

## Success criteria
- Script exits `0`.
- Output contains `backup_run_status=ok`.
- Latest files exist and are non-empty.
- Retention deletes older files when count exceeds `BACKUP_KEEP`.

## Restore quick steps (minimal)
Reference: Stage 53 drill entry (`2026-02-03`) in `docs/STATUS.md` and local evidence in `.run/stage53/REPORT.md`.

DB restore (destructive):
```bash
CONFIRM=YES ./ops/db_restore.sh ./path/to/db_dump.sql
```

Stage 53 strict replay variant:
```bash
docker compose exec -T db sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"'
gzip -dc ./path/to/db_YYYY-MM-DD_HHMMSS.sql.gz | docker compose exec -T db sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1'
```

Attachments restore (volume-backed default):
```bash
docker run --rm -v "<compose_project>_dental_pms_attachments:/v" -v "$PWD":/b alpine:3.20 sh -lc 'rm -rf /v/* && tar -xzf /b/path/to/attachments_YYYY-MM-DD_HHMMSS.tgz -C /v'
```

## Scheduling templates
Template units are provided at:
- `ops/systemd/dental-pms-backup.service`
- `ops/systemd/dental-pms-backup.timer`

Install manually (Stage 56 does not auto-install):
```bash
sudo cp ops/systemd/dental-pms-backup.service /etc/systemd/system/
sudo cp ops/systemd/dental-pms-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now dental-pms-backup.timer
systemctl list-timers --all | grep dental-pms-backup || true
```

## Safety
- Do not commit backup artefacts (`*.sql`, `*.sql.gz`, `*.tgz`).
- Keep off-host encrypted copies for disaster recovery.
