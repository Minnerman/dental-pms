# Dental PMS agent rules

Hard guardrails
- R4 SQL Server is strictly READ-ONLY: SELECT-only. No schema changes, no DML, no stored procedures, no temp tables.
- Charting must match R4 output exactly. If semantics are unclear, record as unknown/raw rather than guessing.

Workflow
- Work only on a branch (never commit directly on master).
- Keep changes staged by topic; prefer multiple small commits over one huge commit.
- Update docs/STATUS.md only once the work is real and tests pass.

Required checks
- bash ops/health.sh
- bash ops/verify.sh
- docker compose exec -T backend pytest -q
