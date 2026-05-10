# Dental PMS Domain Migration, Support, and Cutover Evidence Request

Status date: 2026-05-10

Baseline:
`origin/master@fa47726d4bafcd9ab59f9a7d3cf469603d84d728`

## Scope / Non-Authorisation

This is evidence-request documentation only. It does not access R4,
production, PMS databases, scratch SQLite, real artefacts, patient data,
backups, Google Workspace, or credentials.

This request does not run migration, validation/no-write, guarded apply/write,
finance import, opening-balance import, invoice import, payment import, staging
import, patient data import, backup, restore, rclone, deployment, monitoring
setup, or cutover commands.

R4 remains the live/main PMS. Dental PMS is not live/main PMS.
`finance_import_ready=false`.

Live/default PMS DB writes, actual PMS Postgres writes, production execution,
production cutover, live finance import, invoice/payment/staging import,
patient data import, and Dental PMS live/main PMS status remain unauthorised.
Production readiness remains incomplete.

## Evidence Redaction Policy

Evidence must use non-sensitive role, decision, timestamp, category,
classification, and yes/no/pending formats only.

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
- private infrastructure details;
- R4 artefact paths;
- source database paths;
- monitoring logs containing secrets or patient data;
- support contact private details;
- cutover channels containing private contact details.

## Appointments / Treatments / Recalls Migration Decision Evidence

Accept only:

- domain area;
- included/excluded/pending decision;
- owner decision role;
- timestamp;
- reason classification;
- duplicate policy classification;
- contact/recall policy classification;
- no patient data exposed confirmation;
- no secrets exposed confirmation.

Required domain areas:

- appointments;
- treatments;
- recalls;
- charting/clinical view links;
- documents-to-workflow links;
- reception workflow dependency;
- clinical workflow dependency;
- finance-view dependency, non-import only.

Domain migration decisions do not authorise patient data import. Domain
migration decisions do not authorise finance import. Domain migration
decisions do not authorise invoice/payment/staging import. Any import or write
requires separate explicit owner approval and final go/no-go gating.

## Monitoring / Support Readiness Evidence

Accept only:

- monitoring owner role accepted: yes/no;
- support owner role accepted: yes/no;
- first support window classification;
- escalation route classification;
- alert/log review classification;
- smoke/regression evidence linked: yes/no;
- production target evidence linked: yes/no;
- no private URLs exposed confirmation;
- no credentials exposed confirmation;
- no patient data exposed confirmation.

Do not include:

- private URLs;
- hostnames if unsafe;
- IP addresses;
- credentials;
- logs containing patient data or secrets;
- private staff contact details;
- private support escalation details.

## Cutover Communications Readiness Evidence

Accept only:

- communication owner role accepted: yes/no;
- audience classification;
- message template classification;
- timing classification;
- channel classification;
- go/no-go/hold/rollback state classification;
- no patient data exposed confirmation;
- no secrets exposed confirmation;
- no private contact details exposed confirmation.

Required audiences:

- owner/business;
- reception/front desk;
- clinical users;
- finance/admin users;
- ops/support users;
- patients if applicable;
- external vendor/support if applicable.

Communications evidence does not authorise production cutover. Communications
evidence does not authorise Dental PMS live/main PMS status. Patient-facing
communication requires owner approval. Final go/no-go must be separately
recorded.

## Evidence Intake Table

| Evidence area | Required evidence | Acceptable format | Current status | Required approver role | Blocker if missing |
| --- | --- | --- | --- | --- | --- |
| Appointments migration decision | Included/excluded/pending decision, duplicate policy classification, no patient data exposed confirmation | yes/no/pending, role, timestamp, classification | Pending evidence | Owner plus migration owner | No appointment migration/import until approved |
| Treatments migration decision | Included/excluded/pending decision, duplicate policy classification, no patient data exposed confirmation | yes/no/pending, role, timestamp, classification | Pending evidence | Owner plus clinical workflow owner | No treatment migration/import until approved |
| Recalls migration decision | Included/excluded/pending decision, contact/recall policy classification | yes/no/pending, role, timestamp, classification | Pending evidence | Owner plus migration owner | No recall migration/import until approved |
| Charting/clinical workflow dependency decision | Dependency decision and clinical workflow impact classification | yes/no/pending, role, timestamp, classification | Pending evidence | Clinical workflow owner | No-go until accepted |
| Documents workflow dependency decision | Dependency decision and document workflow impact classification | yes/no/pending, role, timestamp, classification | Pending evidence | Practice workflow owner | No-go until accepted |
| Reception workflow dependency decision | Dependency decision and reception workflow impact classification | yes/no/pending, role, timestamp, classification | Pending evidence | Practice workflow owner | No-go until accepted |
| Finance-view dependency decision, non-import only | Dependency decision and finance-view impact classification | yes/no/pending, role, timestamp, classification | Pending evidence | Finance owner | Does not authorise finance import |
| Monitoring owner role | Monitoring owner role accepted | yes/no, role, timestamp | Pending evidence | Project owner / production operator | No-go until accepted |
| Support owner role | Support owner role accepted | yes/no, role, timestamp | Pending evidence | Project owner / support operator | No-go until accepted |
| First support window | Support window classification | classification, role, timestamp | Pending evidence | Support owner | No-go until accepted |
| Escalation route classification | Escalation route classification without private details | classification, role, timestamp | Pending evidence | Support owner | No-go until accepted |
| Alert/log review classification | Alert/log review classification without secrets or patient data | classification, role, timestamp | Pending evidence | Monitoring owner | No-go until accepted |
| Owner/business communication readiness | Audience, timing, owner, and message template classification | yes/no, role, timestamp, classification | Pending evidence | Communication owner | No-go until accepted |
| Reception communication readiness | Audience, timing, owner, and message template classification | yes/no, role, timestamp, classification | Pending evidence | Communication owner | No-go until accepted |
| Clinical communication readiness | Audience, timing, owner, and message template classification | yes/no, role, timestamp, classification | Pending evidence | Communication owner | No-go until accepted |
| Finance/admin communication readiness | Audience, timing, owner, and message template classification | yes/no, role, timestamp, classification | Pending evidence | Communication owner plus finance owner | No-go until accepted |
| Ops/support communication readiness | Audience, timing, owner, and message template classification | yes/no, role, timestamp, classification | Pending evidence | Communication owner plus support owner | No-go until accepted |
| Patient-facing communication readiness, if applicable | Owner approval, audience classification, timing classification, message classification | yes/no/not applicable, role, timestamp, classification | Pending evidence | Owner/business | No patient-facing communication until approved |
| External vendor/support communication readiness, if applicable | Owner approval, vendor/support classification, timing classification | yes/no/not applicable, role, timestamp, classification | Pending evidence | Owner plus support owner | No external escalation until accepted |
| Final owner go/no-go input | Final owner decision after all evidence gates | go/no-go/hold, role, timestamp, reason classification | Pending evidence | Final go/no-go owner | No cutover until explicit final approval |

## Stop Conditions

Stop before recording evidence or proceeding to any execution if:

- R4 access is required;
- real artefact access is required;
- production access is required;
- PMS database access is required;
- scratch SQLite access is required;
- patient data would be exposed;
- credentials, secrets, or private paths would be exposed;
- private infrastructure details would be exposed;
- private support/contact details would be exposed;
- raw dumps or backup contents would be exposed;
- Google Workspace access is requested;
- backup, restore, or rclone execution is requested;
- migration, validation, or import execution is requested;
- monitoring setup execution is requested;
- deployment execution is requested;
- live finance import is requested;
- opening-balance import is requested;
- invoice/payment/staging import is requested;
- patient data import is requested;
- Dental PMS live/main PMS status is requested without final go/no-go approval;
- production cutover is requested;
- patient-facing communication is requested without owner approval;
- evidence cannot be recorded safely without sensitive detail.

## Current Status

This request is recorded as a planning and evidence-intake aid only. Domain
migration decisions, monitoring/support readiness, cutover communications
acceptance, backup/restore proof, production target acceptance, UAT/access
evidence, rollback owner acceptance, and final go/no-go approval remain
unavailable.
