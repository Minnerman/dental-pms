# Dental PMS — Ops Checklist (Quick)

## Start / Stop
- Start: `cd ~/dental-pms && docker compose up -d --build`
- Stop: `cd ~/dental-pms && docker compose down`

## Check status
- `cd ~/dental-pms && docker compose ps`

## Health checks (run on the server)
- Quick script: `ops/health.sh`
- Backend: `curl -fsS http://localhost:8100/health`
- Frontend proxy: `curl -fsS http://localhost:3100/api/health`
- Admin users list (requires token): `curl -fsS http://localhost:3100/api/users -H "Authorization: Bearer <token>"`
- Patients list (requires token): `curl -fsS http://localhost:3100/api/patients -H "Authorization: Bearer <token>"`
- Appointments list (requires token): `curl -fsS http://localhost:3100/api/appointments -H "Authorization: Bearer <token>"`
- Audit log (requires token): `curl -fsS http://localhost:3100/api/audit -H "Authorization: Bearer <token>"`

## Logs (if something looks wrong)
- Backend: `cd ~/dental-pms && docker compose logs --tail=200 backend`
- Frontend: `cd ~/dental-pms && docker compose logs --tail=200 frontend`
- DB: `cd ~/dental-pms && docker compose logs --tail=200 db`

## Restart a service (safe)
- Backend: `cd ~/dental-pms && docker compose restart backend`
- Frontend: `cd ~/dental-pms && docker compose restart frontend`

## Update code (if you later use git)
- `cd ~/dental-pms && git pull`
- `cd ~/dental-pms && docker compose up -d --build`

## Backups (database volume)
- Backup: `ops/backup_db_volume.sh`
- Restore: `ops/restore_db_volume.sh`

## Notes
- Use Tailscale URLs from `docs/ACCESS_URLS.md` when accessing from home.
- Never use “localhost” on the home laptop (it points to the laptop, not the server).

## Common fixes

### 1) “This site can’t be reached” from HOME laptop
- Use the **Tailscale IP URL** from `docs/ACCESS_URLS.md` (not localhost).
- Example: `http://100.x.y.z:3100`
- If it looks stale: hard refresh (Ctrl+Shift+R) or private window.

### 2) Port already in use (e.g. bind error on 8000/8100/3100)
- See what is using the port:
  - `sudo ss -ltnp | grep -E ':3100|:8100|:5442|:8000' || true`
- If it’s a different project, do **not** stop it. Instead change ports in `.env` and restart this stack:
  - edit `.env` (FRONTEND_PORT/BACKEND_PORT/POSTGRES_PORT)
  - `docker compose up -d --build`

### 3) Backend shows OK but frontend says API unreachable
- Check the proxy route:
  - `curl -fsS http://localhost:3100/api/health`
- Restart only the frontend:
  - `docker compose restart frontend`
- Then hard refresh in the browser.

### 4) Docker daemon not running / “Cannot connect to the Docker daemon”
- `sudo systemctl status docker --no-pager -l`
- `sudo systemctl restart docker`

### 5) Next compile error (module not found)
- Ensure `frontend/tsconfig.json` includes the `@/*` alias.
- Update imports to use `@/lib/auth` and rebuild frontend.
