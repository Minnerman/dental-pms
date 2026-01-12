# Dental PMS manual smoke checklist

Run these checks after patient UX changes or infra updates.

## Services
- docker compose ps
- ./ops/health.sh

## Route checks (expect HTTP 200)
- curl -fsS http://localhost:3100/patients/5 >/dev/null
- curl -fsS http://localhost:3100/patients/5/clinical >/dev/null
- curl -fsS http://localhost:3100/patients/5/documents >/dev/null
- curl -fsS http://localhost:3100/patients/5/attachments >/dev/null

## Not found checks (expect HTTP 404)
- curl -fsS -o /dev/null -w "%{http_code}\n" http://localhost:3100/patients/99999999
- curl -fsS -o /dev/null -w "%{http_code}\n" http://localhost:3100/patients/99999999/clinical

## UI smoke (manual)
- Patient summary loads without layout overflow (desktop + mobile width).
- Book appointment opens and scrolls the booking panel on summary tab.
- Documents tab shows an empty-state CTA when no documents exist.
- Attachments tab shows an empty-state CTA when no attachments exist.
- Clinical tab shows empty-state guidance for notes/procedures when empty.
