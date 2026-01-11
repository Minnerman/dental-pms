# Architecture

## Overview
- Frontend: Next.js app served on port 3100
- Backend: FastAPI app served on port 8100
- Database: Postgres on port 5442 (container 5432)

## Containers and ports
- frontend: `http://localhost:3100`
- backend: `http://localhost:8100`
- db: host port `5442` -> container `5432`

## Key backend routers
- `/patients` (patients + recall settings)
- `/appointments`
- `/notes`
- `/document-templates`
- `/patients/{id}/documents` and `/patient-documents`
- `/patients/{id}/attachments` and `/attachments`
- `/recalls`
- `/settings`
- `/audit`

## Storage
- Attachments are stored on the backend container filesystem at `/data` (mounted volume).

## Migrations
- Alembic migrations live in `backend/alembic/versions`.
- Apply with: `docker compose run --rm backend alembic upgrade head`.
- Revision IDs must be <= 32 characters due to the `alembic_version.version_num` column size.
