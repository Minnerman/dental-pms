# Development Notes

## Common commands
- Start services: `docker compose up -d`
- Health check: `./ops/health.sh`
- Frontend build: `cd frontend && npm run build`
- Backend migrations: `docker compose run --rm backend alembic upgrade head`

## Build + deploy cycle
1) `cd frontend && npm run build`
2) `docker compose build frontend`
3) `docker compose up -d frontend`
4) `./ops/health.sh`

## Backend changes
1) `docker compose build backend`
2) `docker compose run --rm backend alembic upgrade head`
3) `docker compose up -d backend`
4) `./ops/health.sh`

## Troubleshooting
- Frontend proxy may take a few seconds after restart; `./ops/health.sh` retries.
- If migrations fail, confirm `alembic current` and `alembic heads` match.
