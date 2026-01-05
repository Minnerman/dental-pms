# Audit Trail (MVP)

All patient-facing data writes must be attributable to a user. The API captures this
for Patients, Appointments, and Notes.

## Rules
- Every create action sets `created_by_user_id` and `updated_by_user_id`.
- Every update action sets `updated_by_user_id`.
- `created_by` and `updated_by` are included in API responses as `{ id, email, role }`.
- Soft-delete uses audit action `delete`.
- Restore uses audit action `restore`.

## Fields
- `created_at` / `updated_at` (timestamps)
- `created_by_user_id` (required)
- `updated_by_user_id` (nullable)
- `deleted_at` / `deleted_by_user_id` for soft-deletes

## Audit log (append-only)
Audit events are stored in the `audit_logs` table and never updated or deleted.

## Immutability
- No update/delete endpoints are exposed for audit rows.
- In production, add a DB trigger to block UPDATE/DELETE on `audit_logs`.

## Notes
- Anonymous writes are not allowed.
- The seed admin user is created at startup only.
