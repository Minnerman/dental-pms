# R4 SQL Server READ-ONLY WARNING
- R4 SQL Server is STRICTLY READ-ONLY (SELECT-only; no writes/procs/DDL; all --apply writes must be Postgres-only).
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

## Session summary (2026-01-23)

### Completed today
- Stage 126 completed: PR #111 merged (SHA `be1ef8b`).
- Tests/verification: `bash ops/health.sh`, `bash ops/verify.sh`; CI ran backend pytest + Playwright smoke.
- Merged PR #109 (`stage124-fix`) after rebasing it on `master` and fixing the status distribution stats so recalls checks pass.
- Verified `bash ops/health.sh` and `bash ops/verify.sh` to ensure the merged baseline is healthy.

### Parked work
- `stage126-calendar-readonly` branch has WIP changes (also stored in `wip/local-dirty-20260123-004630` at commit `6201864`) that contain the beginnings of the appointments calendar backend + UI.

### Next session steps
1. `git status --porcelain`
2. `git log -1 --oneline`
3. `git checkout stage126-calendar-readonly && git pull --ff-only`
4. `git rebase master` (or `git merge master` if rebase conflicts persist)
5. `git cherry-pick 6201864` (or merge the `wip/local-dirty-20260123-004630` branch) to recover the Calendar work
4. Finish Stage 126: implement `/api/appointments` filters/joins/total flag + calendar UI + Playwright spec; include the Stage 125 completion note in `docs/STATUS.md` and run verify/test commands before opening the PR.
5. After Stage 126 merges, begin Stage 127 (link table + API + modal + tests).
