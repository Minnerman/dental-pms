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
