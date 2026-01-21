# R4 SQL Server source (read-only dry-run)

Stage 97 adds a read-only SQL Server source to validate connectivity and basic
stats before enabling any import. It does not write to Postgres.

## Prerequisites

- SQL Server ODBC driver installed (recommended: "ODBC Driver 18 for SQL Server")
- Network access to the SQL Server host/port (default 1433)
- Read-only SQL Server account with access to `sys2000.dbo.Patients` and `sys2000.dbo.Appts`

## Environment variables

```
R4_SQLSERVER_ENABLED=true
R4_SQLSERVER_HOST=sql.example.local
R4_SQLSERVER_PORT=1433
R4_SQLSERVER_DATABASE=sys2000
# Legacy aliases (use DATABASE/TRUST_SERVER_CERT instead).
R4_SQLSERVER_DB=sys2000
R4_SQLSERVER_USER=readonly_user
R4_SQLSERVER_PASSWORD=change-me
R4_SQLSERVER_DRIVER=ODBC Driver 18 for SQL Server
R4_SQLSERVER_ENCRYPT=true
R4_SQLSERVER_TRUST_SERVER_CERT=false
# Legacy alias (use TRUST_SERVER_CERT instead).
R4_SQLSERVER_TRUST_CERT=false
R4_SQLSERVER_TIMEOUT_SECONDS=8
```

## Legacy TLS note (SQL Server 2008 R2)

Some older SQL Server installs only negotiate TLS 1.0/1.1. The backend container can enable a
scoped OpenSSL legacy policy (via `OPENSSL_CONF` + `OPENSSL_MODULES`) to allow those protocols
without changing the host OS or the R4 server.

Note: `openssl s_client` probes against SQL Server/TDS endpoints can be inconclusive. The
authoritative check is a successful `pyodbc` connection plus a `--dry-run` or bounded import.

## Dry-run command

```
docker compose exec -T backend python -m app.scripts.r4_import --source sqlserver --dry-run --limit 10
```

The command prints a JSON summary (counts, date range if available, and sample
patient codes/appointments).

## Apply import (explicit)

```
docker compose exec -T backend python -m app.scripts.r4_import --source sqlserver --apply \
  --appts-from 2026-01-01 --appts-to 2026-01-07
```

Imports are gated behind `--apply`; without it, the CLI defaults to dry-run and
does not write to Postgres.

See `docs/r4/R4_DRY_RUN_AND_PILOT_IMPORT.md` for the full runbook.

## Pagination notes

SQL Server 2008 R2 lacks `OFFSET/FETCH`, so the source uses keyset pagination on
`PatientCode` and appointment start time (with a tie-breaker column).

## Security notes

- Read-only queries only (no writes).
- Use least-privilege credentials dedicated to read-only access.
