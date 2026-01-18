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
R4_SQLSERVER_DB=sys2000
R4_SQLSERVER_USER=readonly_user
R4_SQLSERVER_PASSWORD=change-me
R4_SQLSERVER_DRIVER=ODBC Driver 18 for SQL Server
R4_SQLSERVER_ENCRYPT=true
R4_SQLSERVER_TRUST_CERT=false
R4_SQLSERVER_TIMEOUT_SECONDS=8
```

## Dry-run command

```
docker compose exec -T backend python -m app.scripts.r4_import --source sqlserver --dry-run
```

The command prints a JSON summary (counts, date range if available, and sample
patient codes/appointments).

## Security notes

- Read-only queries only (no writes).
- Use least-privilege credentials dedicated to read-only access.
