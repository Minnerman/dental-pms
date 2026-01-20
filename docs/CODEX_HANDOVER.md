# R4 SQL Server READ-ONLY WARNING
- R4 SQL Server is strictly READ-ONLY.
- Do not change, amend, delete, update, insert, create, or run stored procedures on R4.
- Use SELECT-only queries and read-only credentials only.
- Avoid any tool/script that could write to R4 under any circumstance.

# Codex end-of-session / handover note

## Stage 108 / R4 patients-only import

### What was fixed
- CI failure in `tests/r4_import/test_importer.py:54` where the second import expected `patients_updated == 0` but CI showed `== 2`.
- Root cause: `R4Patient.date_of_birth` was allowed to parse as `datetime`, so fixture DOBs became datetimes and differed from the stored `date`, triggering idempotency updates on rerun.
- Fix: reverted `R4Patient.date_of_birth` typing back to `date | None` in `backend/app/services/r4_import/types.py`. This stabilised fixture parsing and restored idempotency.

### Outcome
- PR #90 is green and merged (squash + branch deleted).
- Stage 108 status updated in `docs/STATUS.md`.
- `recalls-api` now passes.

### Evidence / commands run
- `gh run view 21181247456 --log-failed` (confirmed failing assertion)
- `docker compose exec -T backend pytest tests/r4_import/test_importer.py -q`
- `bash ops/health.sh`
- `bash ops/verify.sh`
- `gh pr checks 90 --watch --interval 20`
- `gh pr merge 90 --squash --delete-branch`
- `bash ops/health.sh`

### Critical safety reminder (R4 SQL Server)
- R4 SQL Server is strictly READ-ONLY.
- Do not change, amend, delete, update, insert, create, or run stored procedures on R4.
- Use SELECT-only queries and read-only credentials only.
- Avoid any tool/script that could write to R4 under any circumstance.

## Next actions to take (pick one)

### A) Run the Stage 108 pilot: patients-only import (safe)
Proceed with the patients-only pipeline and keep `--dry-run` first. Only reads from R4; writes only to local PMS DB.

1. Run dry-run summary with a small bounded range (if supported):

```bash
docker compose exec -T backend python -m app.scripts.r4_import patients --dry-run --patients-from <N> --patients-to <M>
```

2. If dry-run looks correct, run apply for the same bounded range:

```bash
docker compose exec -T backend python -m app.scripts.r4_import patients --patients-from <N> --patients-to <M>
```

3. Verify idempotency by rerunning apply on the same range and confirming `patients_updated == 0`:

```bash
docker compose exec -T backend python -m app.scripts.r4_import patients --patients-from <N> --patients-to <M>
```

4. Record pilot results (counts + any anomalies) in `docs/STATUS.md`.

(If the CLI syntax is slightly different in your repo, keep the same principle: dry-run -> bounded apply -> rerun apply to confirm idempotency.)

### B) Draft Stage 109 plan
Stage 109 should be a small, low-risk follow-up. Suggested options:

- Add tighter normalisation rules (e.g., whitespace/phone/email canonicalisation) with tests ensuring idempotency.
- Add patient mapping quality reporting (missing fields, invalid DOBs, duplicate NHS numbers, etc.).
- Add better resume support for long imports (keyset paging checkpoints logged).

If you want, paste the exact `r4_import.py --help` output and I will write the exact pilot commands for your current CLI flags (still keeping R4 read-only).
