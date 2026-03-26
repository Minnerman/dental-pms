# Auth + RBAC (MVP)

## Default dev admin
Set in `.env` (use a valid email format):
- `ADMIN_EMAIL`
- `ADMIN_PASSWORD`

On backend startup, the admin user is created if it does not already exist.

## Endpoints (via frontend proxy)
- `POST /api/auth/login` body: `{ "email": "...", "password": "..." }`
- `GET /api/me` requires `Authorization: Bearer <token>`
- `GET /api/health`
- `GET /api/users` (superadmin only)
- `POST /api/users` (superadmin only)
- `GET /api/users/{id}` (superadmin only)
- `PATCH /api/users/{id}` (superadmin only)
- `POST /api/users/{id}/reset-password` (superadmin only)
- `GET /api/users/roles` (superadmin only)

## Roles (initial)
- dentist
- senior_admin
- reception
- nurse
- external
- superadmin

Only `superadmin` can access the `/users` management surface (for now).

## UI
- Users management: `/users` (superadmin only)
