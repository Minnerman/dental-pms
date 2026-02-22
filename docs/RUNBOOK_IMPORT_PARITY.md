# Import / Parity Runbook Notes

- `./ops/verify.sh` may recreate or clear local database state as part of its reset/build flow.
- If you run proof seeding or full-cohort parity after `verify.sh`, first rehydrate the database for the target cohort/domain (for example: patient import + canonical import) or parity/proof results may reflect only the post-reset seed data.
- When recording close-out evidence, note whether parity was run before or after `verify.sh`, and document any explicit rehydrate step.
