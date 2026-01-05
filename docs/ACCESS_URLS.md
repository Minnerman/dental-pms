# Dental PMS — Access URLs (Tailscale)

These are the correct URLs to use from a HOME laptop.

## Home laptop URLs
- http://100.100.149.40:3100
- http://100.100.149.40:3100/api/health

## Server local checks (SSH into practice-server)
- http://localhost:3100/api/health
- http://localhost:8100/health

## Ports in use (current)
- Frontend: 3100
- Backend: 8100
- Postgres: 5442

## Notes
- Do NOT use "localhost" from the HOME laptop (that points to the laptop, not the server).
- If the browser shows old content, use hard refresh (Ctrl+Shift+R) or open a private window.
