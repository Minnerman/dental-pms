# R4 Finance Opening-Balance Full Eligible-Row Artefact Package Request Candidate

Status date: 2026-05-09

Candidate baseline: `origin/master@9effaa1e110129f2cbbeb1b03cad6170f6c2bca6`

This is a docs-only candidate request record. It records owner-provided role
labels and explicit approval to create this candidate record only.

This candidate is not a complete final full eligible-row artefact package
request. It does not create, access, inspect, copy, hash, store, validate, or
execute any real full eligible-row artefact.

No R4 access occurred. No real R4 artefact was accessed. No real patient data
was used. No PMS database connection occurred. No scratch execution occurred.

`finance_import_ready=false`. Live finance import remains out of scope.
Migration/import is not complete. Production readiness is not established. Full
eligible-row artefact execution has not happened.

## Related Records

- package request/template:
  `docs/r4/R4_FINANCE_OPENING_BALANCE_FULL_ELIGIBLE_ARTEFACT_PACKAGE_REQUEST.md`
- package request/template sign-off:
  `docs/r4/R4_FINANCE_OPENING_BALANCE_FULL_ELIGIBLE_ARTEFACT_PACKAGE_REQUEST_SIGNOFF.md`
- package request readiness/gap assessment:
  `docs/r4/R4_FINANCE_OPENING_BALANCE_FULL_ELIGIBLE_ARTEFACT_PACKAGE_REQUEST_READINESS.md`
- provenance/redaction governance:
  `docs/r4/R4_FINANCE_OPENING_BALANCE_FULL_ELIGIBLE_ARTEFACT_PROVENANCE_REDACTION_PROPOSAL.md`
- provenance/redaction governance sign-off:
  `docs/r4/R4_FINANCE_OPENING_BALANCE_FULL_ELIGIBLE_ARTEFACT_PROVENANCE_REDACTION_SIGNOFF.md`

## Owner Role Labels

The owner provided these role labels for this candidate record:

- requesting owner: Project owner;
- artefact owner: Project owner / migration data owner;
- approving owner or role: Project owner.

No separate data-governance person exists for this project. The Project owner is
the project owner, data owner, artefact owner, approving owner, and requesting
owner for this candidate record.

Use role labels only. Do not record personal names in this request track.

## Owner Approval Recorded

The Project owner approves creating this docs-only candidate full eligible-row
artefact package request record.

This approval is limited to creating this candidate repo record. It does not
authorise:

- R4 access;
- real R4 artefact access;
- artefact creation;
- artefact copying;
- artefact hashing;
- artefact storage;
- artefact validation;
- artefact execution;
- real patient data use;
- PMS DB connection;
- guarded scratch apply;
- CLI validation/no-write;
- live/default PMS DB writes;
- actual PMS Postgres writes;
- finance import;
- invoice, payment, or staging import;
- production execution;
- full eligible-row artefact execution.

## Candidate Request Fields

| Field | Candidate value or status |
| --- | --- |
| Request ID | Pending owner-provided request ID. This candidate record does not assign one. |
| Requested by | Project owner. |
| Artefact owner | Project owner / migration data owner. |
| Approving owner | Project owner. |
| Source system | High-level context only: R4 `PatientStats` balance snapshot planning. Specific source details remain pending. |
| Extraction purpose | Candidate context only: future full eligible-row opening-balance artefact package request governance. Final extraction purpose remains pending. |
| Extraction method | Pending owner-provided method description. No extraction was performed. |
| Extraction effective date | Pending owner-provided effective date or window. |
| Creation timestamp | Pending future artefact creation timestamp. No artefact was created. |
| Operator/actor identifier | Pending safe non-sensitive role or actor identifier, if later required. |
| Expected artefact location policy | Pending future approved storage/location policy. No artefact storage is authorised. |
| Manifest ID | Pending future manifest ID convention or concrete manifest ID. |
| Source artefact SHA256 | Pending future source artefact SHA256. No real artefact was accessed or hashed. |
| Manifest checksum | Pending future manifest checksum. |
| Expected total | Pending future expected total. |
| Eligible row count | Pending future eligible row count. |
| Excluded row count | Pending future excluded row count, if applicable. |
| Repo SHA | Candidate record baseline: `9effaa1e110129f2cbbeb1b03cad6170f6c2bca6`. Any future final request must bind to its current repo SHA. |
| Tool/CLI version or commit SHA | Pending future tool, CLI version, or commit SHA requirement. |
| Inclusion rules | High-level context only: eligible non-zero `PatientStats` balance rows if all later gates pass. Final inclusion rules remain pending. |
| Exclusion rules | High-level context only: zero balances no-op and ambiguous rows fail closed unless later approved otherwise. Final exclusion rules remain pending. |
| Zero/negative balance policy | High-level context only: positive and negative balances may be eligible if all gates pass; zero balances create no row. Final policy remains pending. |
| Duplicate handling policy | High-level context only: duplicate source or mapped-patient ambiguity must fail closed. Final policy remains pending. |
| Currency/decimal policy | High-level context only: balances must be handled as exact decimal/pence values. Final policy remains pending. |
| Storage approval | Not approved for artefact creation or storage by this candidate. Future explicit approval required. |
| Redaction approval | Role-label/no-patient-content boundary applies to this candidate. Future artefact redaction approval remains required. |
| Scratch/test target approval | Not approved by this candidate. Future explicit scratch/test target approval required. |
| Validation/no-write authorisation | Not authorised. Future explicit authorisation required. |
| Guarded apply/write authorisation | Not authorised. Future explicit authorisation required. |
| Notes | Candidate record only. Use role labels only. No patient-level contents, full artefact contents, unredacted DSNs, secrets, or production/live-looking target details are included. |

## Remaining Required Inputs

Before a complete specific full eligible-row artefact package request can be
created, the owner must still provide or approve:

- request ID;
- specific source details;
- final extraction purpose, method, and window;
- artefact location policy;
- manifest ID convention or concrete manifest ID;
- tool/CLI requirement;
- final inclusion and exclusion rules;
- final zero/negative, duplicate, and currency policies;
- storage, redaction, and scratch-target approval statuses;
- validation/no-write status;
- guarded apply/write status.

Any later request must also restate that no patient-level contents will be
committed.

## Stop Conditions

Stop before expanding this candidate if any later step would require:

- R4 access;
- real R4 artefact access;
- real patient data;
- artefact creation, copying, hashing, storage, validation, or execution;
- PMS DB connection or write;
- guarded scratch apply;
- CLI validation/no-write;
- finance import;
- invoice, payment, or staging import;
- production execution;
- full eligible-row artefact execution;
- backend, frontend, Docker, compose, runtime, or ops changes;
- wording that implies live import, production readiness, or completed full
  eligible-row artefact execution.
