# Permissions and Basic Audit Plan

## Current behaviour (V1)
All users effectively have full access (create/edit appointments, notes, billing, documents, etc.).

## Future requirement (V2+)
The practice owner/admin must be able to restrict access per user via tick boxes (capabilities),
e.g.:
- can create/edit appointments
- can write clinical notes
- can take payments / cash-up
- can delete documents
- can manage users

## Capability-based permissions design
### Data model
- capabilities: (code, description)
- user_capabilities: (user_id, capability_id)

### Default policy
- Seed a baseline set of capabilities.
- Assign all capabilities to all existing users by default (preserves V1 behaviour).
- Later, owner/admin can remove capabilities per user without refactoring.

### Enforcement approach
- Backend is authoritative:
  - protected endpoints require a capability (e.g. `billing.payments.write`)
- Frontend is UX:
  - hide/disable buttons if capability is missing (optional in V2; backend guard is required)

### Suggested initial capability set (example)
- appointments.view, appointments.write, appointments.cancel, appointments.reschedule
- patients.view, notes.write
- documents.upload, documents.download, documents.delete
- billing.view, billing.payments.write, billing.cashup
- recalls.export
- admin.users.manage, admin.permissions.manage

## Basic audit level (not heavy)
### What to record
- timestamp
- actor user_id
- action (string)
- entity_type + entity_id
- minimal details (optional JSON: e.g. changed fields)

### Minimum audited actions
- Appointment: create/update/reschedule/cancel
- Billing: payment recorded (and any void/refund if supported later)
- Documents: upload/delete
- Permissions: capability changes (when enabled)

This is intended to support accountability and basic troubleshooting, not full forensic logging.
