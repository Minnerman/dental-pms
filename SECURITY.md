# Security Policy

## Reporting a vulnerability
If you discover a security issue, please report it privately.

- Preferred: open a GitHub Security Advisory for this repo.
- Alternative: contact the maintainer directly (practice admin).

Please include a short description, reproduction steps, and any relevant logs.

## Secrets and credentials
- Do not commit `.env` files or secret values.
- Rotate credentials immediately if any secret is exposed.
- Use least-privilege accounts and per-environment credentials.

## R4 SQL Server safety (read-only)
- R4 SQL Server is strictly READ-ONLY.
- Never run `INSERT/UPDATE/DELETE/MERGE`, DDL, or stored procedures against R4.
- Use SELECT-only queries and read-only credentials only.
- Avoid any tool/script that could write to R4 under any circumstance.
