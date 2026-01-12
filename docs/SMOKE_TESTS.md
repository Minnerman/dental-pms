# Dental PMS manual smoke checklist

Run these checks after patient UX changes or infra updates.

## Services
- docker compose ps
- ./ops/health.sh

## Full verification scripts
- bash ops/verify.sh
- bash ops/verify_prod_404.sh

## Route checks (expect HTTP 200)
- curl -fsS http://localhost:3100/patients/5 >/dev/null
- curl -fsS http://localhost:3100/patients/5/clinical >/dev/null
- curl -fsS http://localhost:3100/patients/5/documents >/dev/null
- curl -fsS http://localhost:3100/patients/5/attachments >/dev/null

## Not found checks (expect HTTP 404)
- curl -fsS -o /dev/null -w "%{http_code}\n" http://localhost:3100/patients/99999999
- curl -fsS -o /dev/null -w "%{http_code}\n" http://localhost:3100/patients/99999999/clinical
- Production Next server enforces 404 via server-side guard; verify with ops/verify_prod_404.sh.

## UI smoke (manual)
- Patient summary loads without layout overflow (desktop + mobile width).
- Book appointment opens and scrolls the booking panel on summary tab.
- Documents tab shows an empty-state CTA when no documents exist.
- Attachments tab shows an empty-state CTA when no attachments exist.
- Clinical tab shows empty-state guidance for notes/procedures when empty.

## Stage 31 appointments workflow acceptance checks
- Booking can be initiated from patient page, appointments page, and deep link (`/appointments?book=1`, optional `patientId=`).
- Booking opens reliably after refresh, tab switches, and back/forward navigation.
- Deep link `/appointments?book=1` opens the booking UI once and cleans the URL.
- Optional deep link `/appointments?book=1&patientId=5` preselects the patient.
- Required fields enforced (date/time, duration, patient, clinician/resource if applicable).
- Successful create appears immediately on calendar and persists after refresh.
- Backend errors surface as clear user messages.
- Timezone sanity: UK local times display consistently.
