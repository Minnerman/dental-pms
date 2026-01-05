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
- `GET /api/users` (admin only)
- `POST /api/users` (admin only)
- `PATCH /api/users/{id}` (admin only)
- `GET /api/users/roles` (admin only)

## Roles (initial)
- dentist
- senior_admin
- reception
- nurse
- external
- superadmin

Only `superadmin` can list/create users (for now).

## UI
- Users management: `/users` (admin only)
