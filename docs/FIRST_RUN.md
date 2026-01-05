# First Run

## Configure
1) Copy the example env file:
```bash
cp .env.example .env
```
2) Edit `.env` and set:
- `SECRET_KEY` (min 32 chars)
- `ADMIN_EMAIL`
- `ADMIN_PASSWORD` (min 12 chars)

Never commit `.env`.

## What happens on first login
If the database has zero users, the backend creates an initial admin from
`ADMIN_EMAIL` / `ADMIN_PASSWORD` and forces a password change on first login.

## Start
```bash
docker compose up -d
```

## Verify
```bash
./ops/health.sh
```

## Login
- URL: `http://<server-ip>:3100/login`
- First login will force the change-password flow.

## Rotate admin password safely
Preferred method:
1) Sign in as an admin.
2) Go to `/users`.
3) Use the reset-password action for the target admin.
4) Complete the change-password flow.
