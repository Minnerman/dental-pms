# R4 import scaffold (fixtures)

This scaffold provides a safe, idempotent import path for legacy R4 data using
synthetic fixture files. It does not connect to SQL Server.

## How to run

From the backend container (recommended):

```bash
docker compose exec -T backend python -m app.scripts.r4_import --source fixtures
```

The command prints a JSON summary and exits non-zero only on hard failures.

## Legacy keys

- Patients are keyed by `legacy_source="r4"` and `legacy_id=<PatientCode>`.
- Appointments are keyed by `legacy_source="r4"` and `legacy_id=<appointment_id>`
  (or a deterministic composite key when a stable ID is unavailable).

Unmapped appointment patient references are stored with `patient_id = NULL` and
counted in the summary.

## Next step (not in this stage)

Add a real SQL Server source behind environment variables and reuse the same
importer API.

## Unmapped queue (Stage 94)

Admin-only queue to review imported appointments with `patient_id IS NULL`.

UI: `/admin/legacy/unmapped-appointments`  
API: `GET /admin/legacy/unmapped-appointments?legacy_source=r4&from=YYYY-MM-DD&to=YYYY-MM-DD`
