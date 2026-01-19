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
- or `R4_SQLSERVER_TRUST_CERT=true`

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
R4_SQLSERVER_DB=sys2000
R4_SQLSERVER_USER=readonly_user
R4_SQLSERVER_PASSWORD=change-me
R4_SQLSERVER_DRIVER=ODBC Driver 18 for SQL Server
R4_SQLSERVER_ENCRYPT=true
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

## G) Rollback (dev-only guidance)

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

## H) Troubleshooting

Common failures and fixes:
- Driver not found: install `msodbcsql18` or `msodbcsql17`.
- TLS handshake failures (SQL 2008 R2): set `R4_SQLSERVER_ENCRYPT=false` or `R4_SQLSERVER_TRUST_CERT=true`.
- Login failed: confirm user/password and server access.
- Timeout: increase `R4_SQLSERVER_TIMEOUT_SECONDS` or check network latency.
