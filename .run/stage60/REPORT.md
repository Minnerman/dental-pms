# Stage 60 Release Rehearsal Report

- Date (local): 2026-02-04 13:57:38 GMT (+0000)
- Date (UTC): 2026-02-04 13:57:38 UTC
- Branch: `stage60-release-rehearsal`
- Commit under test: `d3a383b01a6fd778858acdf802df89ed3c50b7c5`

## Checklist Summary

- `ops/env_check.sh`: PASS (`.run/stage60/env_check.txt`)
- `ops/health.sh` before rehearsal: PASS (`.run/stage60/health_before.txt`)
- `ops/verify.sh`: PASS (`.run/stage60/verify.txt`)
- Backend tests (`pytest -q`): PASS, `214 passed, 2 skipped` (`.run/stage60/pytest.txt`)
- Playwright smoke (wrapper equivalent command): PASS, `25 passed, 4 skipped` (`.run/stage60/playwright_smoke.txt`)
- Playwright parity (wrapper equivalent command): PASS, `25 passed, 4 skipped` (`.run/stage60/playwright_parity.txt`)
- Backup run: PASS (`.run/stage60/backup_run.txt`)
- Backup validation: PASS (`gzip -t` and `tar -tzf`), artefacts in `.run/stage60/backup_validation.txt`
- RC restore smoke: PASS (`.run/stage60/restore_context.txt`, `.run/stage60/health_rc_before_restore.txt`, `.run/stage60/health_rc_after_restore.txt`)

## Backup Artefacts Validated

- Latest DB backup: `.run/backups/db/db_2026-02-04_135334.sql.gz`
- Latest attachments backup: `.run/backups/attachments_2026-02-04_135336.tgz`
- Validation checks:
  - `gzip -t` on DB dump: PASS
  - `tar -tzf | head` on attachments archive: PASS

## Restore Rehearsal Result (Isolated RC Project)

- RC project name: `dentalpms_rc_20260204_135625`
- RC ports: postgres `6542`, backend `9100`, frontend `4100`
- DB restore commands completed with `ON_ERROR_STOP=1` and full replay of latest DB backup.
- RC health before restore: backend + frontend proxy OK.
- RC health after restore: backend + frontend proxy OK.
- RC stack teardown and temporary restore SQL cleanup completed.

## Notes

- `ops/playwright_docker.sh` does not expose `--smoke` / `--parity` flags; equivalent explicit Playwright invocations were used and logs were captured to the requested file names.
- Initial RC attempt using raw `COMPOSE_PROJECT_NAME` with default compose failed because `container_name` entries in `docker-compose.yml` conflict across projects. Rehearsal was rerun with a temporary compose variant (container names removed) and isolated ports; final RC restore smoke passed.
