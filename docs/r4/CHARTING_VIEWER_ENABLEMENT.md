# Charting Viewer Enablement (Stage 146)

## Default behavior
- The charting viewer is disabled by default.
- `/config` returns `"charting_viewer": false`.
- Charting endpoints return `403` when disabled.
- The Charting tab is hidden; direct route shows a disabled message.

## Enable in staging

Pick the path used by your environment.

### Docker Compose (env file)
1. Set `FEATURE_CHARTING_VIEWER=true` in the environment file used by staging.
2. Restart containers:
   ```bash
   docker compose up -d
   ```
3. Verify:
   ```bash
   curl http://<backend-host>/config
   ```
   Expect `"charting_viewer": true`.
4. UI checks:
   - Charting tab is visible on a patient page.
   - Direct route `/patients/<id>/charting` loads.

### systemd service
1. Set `FEATURE_CHARTING_VIEWER=true` in the service environment.
2. Restart service:
   ```bash
   sudo systemctl restart dental-pms
   ```
3. Verify with `/config` as above.

## Enable in production
1. Schedule enablement off-hours if possible.
2. Set `FEATURE_CHARTING_VIEWER=true` and restart services.
3. Verify `/config` shows enabled and the Charting tab appears.
4. Monitor for errors or performance regressions.

## Rollback
1. Set `FEATURE_CHARTING_VIEWER=false` or unset it.
2. Restart services.
3. Verify:
   - `/config` shows `"charting_viewer": false`.
   - Charting endpoints return `403`.
   - Charting tab is hidden; direct route shows disabled message.

## Safety notes
- Read-only banner is always displayed in the viewer.
- Pagination defaults limit rows and show totals.
- **R4 SQL Server is strictly read-only.** Codex must only run `SELECT` queries against R4. **No writes of any kind**: no `UPDATE/INSERT/DELETE/MERGE`, no DDL (`CREATE/ALTER/DROP`), no stored procedures, no temp-table side effects, no schema changes, and nothing that could modify or impact the R4 server.

## Local UI parity tests (deterministic seed)
1. Enable test routes and the viewer:
   - `APP_ENV=test`
   - `ENABLE_TEST_ROUTES=1`
   - `FEATURE_CHARTING_VIEWER=true`
2. Restart services.
3. Seed demo charting data:
   ```bash
   docker compose exec -T backend python -m app.scripts.seed_charting_demo --apply
   ```
4. Run Playwright parity tests:
   ```bash
   NEXT_PUBLIC_FEATURE_CHARTING_VIEWER=1 docker compose exec -T frontend \
     npx playwright test tests/charting-viewer.spec.ts tests/charting-parity.spec.ts
   ```

## CI parity job assumptions
- Parity runs with `APP_ENV=test`, `ENABLE_TEST_ROUTES=1`, and `FEATURE_CHARTING_VIEWER=true`.
- CI parity sets `REQUIRE_CHARTING_PARITY=1` so charting tests fail (not skip) if the viewer is disabled.
- Charting rate limiting is skipped only when `APP_ENV=test` (CI parity).
- `BACKEND_BASE_URL` points at the host-mapped backend (`http://localhost:8100`) because Playwright runs on the GitHub runner, not inside Compose.

## CI parity troubleshooting
- Seed 404:
  - Ensure `APP_ENV=test` and `ENABLE_TEST_ROUTES=1` are passed into Compose.
  - Confirm `/test/seed/charting` exists via `/openapi.json` in CI logs.
- Seed 500:
  - Check backend logs for DB constraints or missing admin user.
  - Re-run migrations and seed; verify `ADMIN_EMAIL` and `ADMIN_PASSWORD`.
- Seed 429:
  - Indicates rate limiting still active; confirm `APP_ENV=test` in backend container.
