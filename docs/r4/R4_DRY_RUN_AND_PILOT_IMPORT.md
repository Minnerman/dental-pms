# R4 SQL Server dry-run and pilot import runbook

This runbook covers safe, read-only dry-runs and a tightly scoped pilot import
from R4 SQL Server into the PMS.

## A) Preconditions

- Confirm SQL Server version (2008 R2) and database name (`sys2000`).
- Create a least-privilege SQL login with read-only access to:
  - `sys2000.dbo.Patients`
  - `sys2000.dbo.Appts`
- Confirm network reachability to SQL Server host:port (default 1433).

## B) Ubuntu prerequisites (two paths)

### Option 1: pyodbc + Microsoft ODBC Driver (preferred)

Example (Ubuntu 22.04, adjust as needed):

```bash
sudo apt-get update
sudo apt-get install -y unixodbc unixodbc-dev
curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | sudo gpg --dearmor -o /usr/share/keyrings/microsoft.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft.gpg] https://packages.microsoft.com/ubuntu/22.04/prod jammy main" | sudo tee /etc/apt/sources.list.d/mssql-release.list
sudo apt-get update
sudo ACCEPT_EULA=Y apt-get install -y msodbcsql18
```

If SQL Server 2008 R2 fails TLS handshakes with Driver 18, try:
- driver 17 (`msodbcsql17`)
- `R4_SQLSERVER_ENCRYPT=false`
- or `R4_SQLSERVER_TRUST_SERVER_CERT=true`

### Option 2: pyodbc + Driver 17

```bash
sudo ACCEPT_EULA=Y apt-get install -y msodbcsql17
```

## C) Environment variables

Add to `.env` (placeholders only):

```
R4_SQLSERVER_ENABLED=true
R4_SQLSERVER_HOST=sql.example.local
R4_SQLSERVER_PORT=1433
R4_SQLSERVER_DATABASE=sys2000
# Legacy alias (use R4_SQLSERVER_DATABASE instead).
R4_SQLSERVER_DB=sys2000
R4_SQLSERVER_USER=readonly_user
R4_SQLSERVER_PASSWORD=change-me
R4_SQLSERVER_DRIVER=ODBC Driver 18 for SQL Server
R4_SQLSERVER_ENCRYPT=true
R4_SQLSERVER_TRUST_SERVER_CERT=false
# Legacy alias (use R4_SQLSERVER_TRUST_SERVER_CERT instead).
R4_SQLSERVER_TRUST_CERT=false
R4_SQLSERVER_TIMEOUT_SECONDS=8
```

Safe defaults:
- Imports only occur with `--apply` **and** `--confirm APPLY`.
- Without those flags, the CLI runs dry-run only.

## D) Dry-run steps

Basic connectivity + counts:

```bash
docker compose exec -T backend python -m app.scripts.r4_import --source sqlserver --dry-run
```

Sample a small window:

```bash
docker compose exec -T backend python -m app.scripts.r4_import --source sqlserver --dry-run --limit 10
```

Record:
- patient count
- appointment count
- sample patient codes
- sample appointment IDs/patient codes

## E) Pilot import (tiny window)

Start with a 1–2 day window:

```bash
docker compose exec -T backend python -m app.scripts.r4_import --source sqlserver --apply --confirm APPLY \
  --appts-from 2026-01-01 --appts-to 2026-01-03
```

Verify:
- importer summary counts
- unmapped legacy queue: `/admin/legacy/unmapped-appointments`
- conflict stats (if any)

## E2) Resume after timeout or interrupted run (patients-only)

Long-running imports can exceed shell timeouts even though the backend keeps running.
Use checkpoint output plus idempotency to confirm completion or resume safely.

Decision tree:

1) Output cut off / timeout:
   - Check Postgres counts for the window.
   - Rerun the same apply command to confirm `created=0, updated=0`.

2) Partial import suspected:
   - Use last checkpoint `last_patient_code=X` and resume with `--patients-from X+1`.
   - Keep the same `--patients-to` and rerun idempotency at the end.

Postgres count query:

```bash
docker compose exec -T db psql -U dental_pms -d dental_pms -c \\
  "select count(*) from patients where legacy_source='r4' and legacy_id ~ '^[0-9]+$' and legacy_id::int between <START> and <END>;"
```

Idempotency rerun (same window):

```bash
docker compose exec -T backend python -m app.scripts.r4_import \\
  --source sqlserver \\
  --entity patients \\
  --apply \\
  --confirm APPLY \\
  --patients-from <START> \\
  --patients-to <END>
```

Resume using a checkpoint:

```bash
docker compose exec -T backend python -m app.scripts.r4_import \\
  --source sqlserver \\
  --entity patients \\
  --apply \\
  --confirm APPLY \\
  --patients-from <LAST_PATIENT_CODE_PLUS_1> \\
  --patients-to <END>
```

Example (real pilot window, no patient data):

```
Window: 1000101-1005100
Checkpoint: {"event":"r4_import_checkpoint","last_patient_code":1005100,"processed":5000}
Resume: --patients-from 1005101 --patients-to 1005100 (no-op, already complete)
```

## F) Stage 103: treatments + treatment plans

Run treatments before treatment plans (CodeID enrichment later).

Dry-run treatments:

```bash
docker compose exec -T backend python -m app.scripts.r4_import --source sqlserver --dry-run --entity treatments
```

Dry-run treatment plans:

```bash
docker compose exec -T backend python -m app.scripts.r4_import --source sqlserver --dry-run --entity treatment_plans
```

Optionally filter by patient code or TP number:

```bash
docker compose exec -T backend python -m app.scripts.r4_import --source sqlserver --dry-run \
  --entity treatment_plans --patients-from 1000 --patients-to 1100 --tp-from 1 --tp-to 20
```

Apply (gated):

```bash
docker compose exec -T backend python -m app.scripts.r4_import --source sqlserver --apply --confirm APPLY \
  --entity treatments

docker compose exec -T backend python -m app.scripts.r4_import --source sqlserver --apply --confirm APPLY \
  --entity treatment_plans
```

Inspect in admin UI (read-only):
- `http://100.100.149.40:3100/admin/r4/treatment-plans`
- Search by legacy patient code to see imported plans + items.

## G) Stage 105: full treatment plan import (batched + resumable)

Full import (safe defaults; resumable on re-run):

```bash
docker compose run --rm r4_import python -m app.scripts.r4_import \
  --source sqlserver --apply --confirm APPLY --entity treatments

docker compose run --rm r4_import python -m app.scripts.r4_import \
  --source sqlserver --apply --confirm APPLY --entity treatment_plans \
  --batch-size 1000 --sleep-ms 50 --progress-every 5000
```

Notes:
- The importer is idempotent; re-running the same command resumes safely.
- Progress is printed as compact JSON lines when `--apply` is used.
- Adjust `--batch-size` and `--sleep-ms` if SQL Server load is high.

Summary report (Postgres-only; no SQL Server connection required):

```bash
docker compose run --rm backend python -m app.scripts.r4_import \
  --entity treatment_plans_summary
```

## H) Rollback (dev-only guidance)

If the pilot window was incorrect, remove rows by legacy markers. Use extreme
caution and avoid production unless approved.

Example (psql):

```sql
DELETE FROM appointments
WHERE legacy_source = 'r4'
  AND starts_at >= '2026-01-01'
  AND starts_at < '2026-01-04';

DELETE FROM patients
WHERE legacy_source = 'r4'
  AND created_at >= now() - interval '1 day';
```

Notes:
- Prefer filtering by `legacy_source` and date windows.
- Do not delete records that were manually resolved unless you intend to reset.

## I) Troubleshooting

Common failures and fixes:
- Driver not found: install `msodbcsql18` or `msodbcsql17`.
- TLS handshake failures (SQL 2008 R2): set `R4_SQLSERVER_ENCRYPT=false` or `R4_SQLSERVER_TRUST_SERVER_CERT=true`.
- Login failed: confirm user/password and server access.
- Timeout: increase `R4_SQLSERVER_TIMEOUT_SECONDS` or check network latency.
