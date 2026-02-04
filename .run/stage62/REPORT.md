# Stage 62 Production-Mode Dry Run Report

- Date (local): 2026-02-04 14:36:15 GMT (+0000)
- Date (UTC): 2026-02-04 14:36:15 UTC
- Branch: `stage62-prodmode-dryrun`
- Commit under test: `6d693d8eb890d255ced57bdae8a83ccc8b4155bd`

## Systemd Unit Validation

- Repo units present and captured: `.run/stage62/systemd_units.txt`
- Host unit status checks:
  - Timer status: `.run/stage62/backup_timer_status.txt`
  - Service status: `.run/stage62/backup_service_status.txt`
- Result: units are present in-repo; host systemd unit names are not installed/available in this environment (`could not be found`), and direct start requires interactive auth.

## Backup Run Result

- Script run (`ops/backup_run.sh`): PASS (`.run/stage62/backup_run_script.txt`)
- Latest DB backup validated with `gzip -t`: PASS
- Latest DB path: `.run/backups/db/db_2026-02-04_143334.sql.gz` (`.run/stage62/latest_db_path.txt`)
- Systemd service execution: not validated as active service in this environment (journal captured at `.run/stage62/backup_service_journal.txt`).

## Rollback Smoke (Isolated RC Project)

- RC project context: `.run/stage62/rollback_context.txt`
- RC health before restore: PASS (`.run/stage62/rc_health_before_restore.txt`)
- RC restore commands (`DROP SCHEMA ...; psql replay`) completed with `ON_ERROR_STOP=1`: PASS
- RC health after restore: PASS (`.run/stage62/rc_health_after_restore.txt`)
- RC quick DB count snapshot: PASS (`.run/stage62/rc_counts.txt`, `patients=882`)
- RC teardown (`docker compose down -v`) and temp SQL cleanup completed.

## Final Gates

- `bash ops/health.sh`: PASS (`.run/stage62/health_final.txt`)
- `bash ops/verify.sh`: PASS (`.run/stage62/verify_final.txt`)
- `docker compose exec -T backend pytest -q`: PASS (`214 passed, 2 skipped`) (`.run/stage62/pytest_final.txt`)

## Caveats

- A first-request warm-up can intermittently return a transient frontend connection reset immediately after container start; retries succeeded and no persistent failure was observed.
