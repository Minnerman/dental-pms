# Dental PMS Production Target, User/Access, and UAT Evidence Request

Status date: 2026-05-10

Baseline:
`origin/master@0d4a4fc5e743c8d0843ed3ca3ff8ddb526dfed65`

## Scope / Non-Authorisation

This is evidence-request documentation only. It does not verify the production
target, access production, perform cutover, access R4, connect to PMS
databases, query scratch SQLite, access patient data, inspect real artefacts,
access Google Workspace, access backups, or create, inspect, validate, handle,
or request credentials.

This request does not run deployment, migration, backup, restore, rclone,
import, finance, invoice, payment, staging, validation/no-write, guarded
apply/write, or cutover commands.

R4 remains the live/main PMS. Dental PMS is not live/main PMS.
`finance_import_ready=false`. Production readiness remains incomplete.

## Evidence Redaction Policy

Evidence must use non-sensitive role, status, timestamp, classification, and
redacted command/result formats only.

Do not include:

- credentials;
- tokens;
- DSNs;
- passwords;
- private URLs;
- exact private filesystem paths;
- raw dumps;
- backup contents;
- generated rclone config;
- OAuth material;
- service-account material;
- crypt passwords or salts;
- patient data;
- patient-level identifiers;
- private staff contact details;
- private infrastructure details.

## Production Target Acceptance Evidence

Accept only:

- production target label/classification;
- owner/operator acceptance: yes/no;
- deployment target accepted: yes/no;
- frontend health classification: pass/fail/not checked;
- backend/app health classification: pass/fail/not checked;
- monitoring/logging owner role accepted: yes/no;
- support contact role accepted: yes/no;
- no secrets exposed confirmation;
- no patient data exposed confirmation.

Do not include:

- private URLs;
- hostnames if unsafe;
- IP addresses;
- credentials;
- infrastructure secrets;
- logs containing patient data or secrets.

## User/Access Review Evidence

Required role areas:

- admin;
- reception/front desk;
- clinical users;
- finance/admin users;
- support/ops users.

Accept only:

- role reviewed: yes/no;
- access level classification;
- least-privilege accepted: yes/no;
- inactive/unknown users removed or blocked: yes/no;
- MFA/password policy classification if safe;
- approver role;
- timestamp;
- no credentials exposed confirmation;
- no patient data exposed confirmation.

Do not include:

- passwords;
- tokens;
- reset links;
- personal phone numbers;
- private email addresses unless intentionally safe;
- patient data;
- credential screenshots.

## UAT / Practice Workflow Evidence

Required workflow areas:

- reception appointment/search workflow;
- clinical charting/viewing workflow;
- document workflow;
- recall workflow;
- admin/settings workflow;
- finance-view workflow, non-import only;
- smoke/regression result classification.

Accept only:

- workflow area;
- pass/fail/blocked;
- approver role;
- timestamp;
- blocker classification;
- no patient data exposed confirmation;
- no secrets exposed confirmation.

UAT evidence does not authorise live finance import. UAT evidence does not
authorise invoice/payment/staging import. UAT evidence does not authorise
production cutover. Any live/main PMS change requires final go/no-go approval.

## Evidence Intake Table

| Evidence area | Required evidence | Acceptable format | Current status | Required approver role | Blocker if missing |
| --- | --- | --- | --- | --- | --- |
| Production target acceptance | Target classification, owner/operator acceptance, deployment target acceptance, frontend/backend/app health classification, monitoring/support roles accepted | yes/no, role, timestamp, classification, pass/fail/not checked | Pending evidence | Project owner / production operator | No-go until accepted |
| Monitoring/logging owner role | Role acceptance and escalation ownership | yes/no, role, timestamp | Pending evidence | Project owner / production operator | No-go until accepted |
| Support contact role | Support owner role acceptance | yes/no, role, timestamp | Pending evidence | Project owner | No-go until accepted |
| Admin access review | Admin role reviewed, least privilege accepted, unknown users removed/blocked | yes/no, role, timestamp, classification | Pending evidence | Practice owner / access owner | No-go until accepted |
| Reception access review | Reception/front desk role reviewed | yes/no, role, timestamp, classification | Pending evidence | Practice owner / access owner | No-go until accepted |
| Clinical access review | Clinical role reviewed | yes/no, role, timestamp, classification | Pending evidence | Practice owner / clinical workflow owner | No-go until accepted |
| Finance/admin access review | Finance/admin role reviewed | yes/no, role, timestamp, classification | Pending evidence | Finance owner | No-go until accepted |
| Support/ops access review | Support/ops role reviewed | yes/no, role, timestamp, classification | Pending evidence | Ops/support owner | No-go until accepted |
| UAT reception workflow | Appointment/search workflow result | pass/fail/blocked, role, timestamp, blocker classification | Pending evidence | Practice workflow owner | No-go until accepted |
| UAT clinical workflow | Clinical charting/viewing workflow result | pass/fail/blocked, role, timestamp, blocker classification | Pending evidence | Clinical workflow owner | No-go until accepted |
| UAT documents workflow | Document workflow result | pass/fail/blocked, role, timestamp, blocker classification | Pending evidence | Practice workflow owner | No-go until accepted |
| UAT recalls workflow | Recall workflow result | pass/fail/blocked, role, timestamp, blocker classification | Pending evidence | Practice workflow owner | No-go until accepted |
| UAT finance-view workflow | Finance-view workflow result, non-import only | pass/fail/blocked, role, timestamp, blocker classification | Pending evidence | Finance owner | No-go until accepted |
| Smoke/regression result | Smoke/regression result classification | pass/fail/blocked, role, timestamp, blocker classification | Pending evidence | Technical owner | No-go until accepted |
| Final owner go/no-go input | Owner decision after all evidence gates | go/no-go/hold, role, timestamp, reason classification | Pending evidence | Final go/no-go owner | No cutover until accepted |

## Stop Conditions

Stop before recording evidence or proceeding to any execution if:

- production access is required;
- R4 access is required;
- PMS database access is required;
- scratch SQLite access is required;
- patient data would be exposed;
- credentials, secrets, or private paths would be exposed;
- private infrastructure details would be exposed;
- Google Workspace access is requested;
- backup, restore, or rclone execution is requested;
- deployment, migration, or import execution is requested;
- live finance import is requested;
- invoice/payment/staging import is requested;
- Dental PMS live/main PMS status is requested without final go/no-go approval;
- production cutover is requested;
- evidence cannot be recorded safely without sensitive detail.

## Current Status

This request is recorded as a planning and evidence-intake aid only. Production
target acceptance, user/access review evidence, UAT/practice workflow evidence,
smoke/regression evidence, backup/restore proof, rollback owner acceptance, and
final go/no-go approval remain unavailable.
