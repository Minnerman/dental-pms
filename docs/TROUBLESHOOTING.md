# Troubleshooting

## Login

- Login URL: `http://100.100.149.40:3100/login`
- If the UI says "Invalid credentials":
  - Run `./ops/scripts/reset_admin_password.sh` and log in with the same email/password you entered there.
  - After changing `.env`, recreate containers so the new values are injected:
    - `docker compose up -d --force-recreate backend`
- Common pitfall: piping into `python - <<'PY'` will consume stdin and can break interactive password input. Use `python -c` for interactive flows.
