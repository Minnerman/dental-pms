# R4 Finance Opening-Balance Full Eligible-Row Artefact Package Request Record 20260509

Status date: 2026-05-09

Request record baseline: `origin/master@d32a087f0e9e3aaaf5ac4d485d204aa8043842ed`

Request ID: `r4ob-full-eligible-request-20260509-000001`

This is an owner-authorised docs-only request record. It records the
non-sensitive request metadata approved by the Project owner for a future full
eligible-row opening-balance artefact package.

This record is not an artefact creation or access approval. It does not
authorise R4 access, real R4 artefact access, artefact creation, artefact
copying, artefact hashing, artefact storage, artefact validation, artefact
execution, validation/no-write, guarded apply/write, PMS DB connection, finance
import, or production execution.

No R4 access occurred. No real R4 artefact was accessed, created, copied,
hashed, stored, validated, or executed. No patient data was used. No PMS
database connection occurred. No scratch execution occurred.

`finance_import_ready=false`. Live finance import remains out of scope.
Migration/import is not complete. Production readiness is not established. Full
eligible-row artefact execution has not happened.

## Related Records

- package request/template:
  `docs/r4/R4_FINANCE_OPENING_BALANCE_FULL_ELIGIBLE_ARTEFACT_PACKAGE_REQUEST.md`
- package request/template sign-off:
  `docs/r4/R4_FINANCE_OPENING_BALANCE_FULL_ELIGIBLE_ARTEFACT_PACKAGE_REQUEST_SIGNOFF.md`
- readiness/gap assessment:
  `docs/r4/R4_FINANCE_OPENING_BALANCE_FULL_ELIGIBLE_ARTEFACT_PACKAGE_REQUEST_READINESS.md`
- candidate request record:
  `docs/r4/R4_FINANCE_OPENING_BALANCE_FULL_ELIGIBLE_ARTEFACT_PACKAGE_REQUEST_CANDIDATE.md`
- provenance/redaction governance:
  `docs/r4/R4_FINANCE_OPENING_BALANCE_FULL_ELIGIBLE_ARTEFACT_PROVENANCE_REDACTION_PROPOSAL.md`
- provenance/redaction governance sign-off:
  `docs/r4/R4_FINANCE_OPENING_BALANCE_FULL_ELIGIBLE_ARTEFACT_PROVENANCE_REDACTION_SIGNOFF.md`

## Owner Roles

| Role | Value |
| --- | --- |
| Requesting owner | Project owner |
| Artefact owner | Project owner / migration data owner |
| Approving owner/role | Project owner |
| Data-governance role | No separate data-governance person exists; Project owner is also the data, artefact, requesting, and approving owner. |

Use role labels only in this request track. Do not record personal names.

## Request Metadata

| Field | Owner-authorised value |
| --- | --- |
| Source system | R4 source system. |
| Specific source details | R4 opening-balance source context using PatientStats-derived eligible-row context. No table extracts, patient-level contents, raw R4 export contents, or clinical details are included in this request record. Exact source/export details must be captured only in a later separately authorised artefact package creation/access slice. |
| Final extraction purpose | Create a governed full eligible-row artefact package for future scratch/test-only validation/no-write consideration. This request record does not authorise extraction, validation/no-write, guarded apply/write, or import. |
| Final extraction method | Approved R4 export/query method to be documented and performed only in a later separately authorised artefact creation/access slice. This record does not perform or authorise extraction. |
| Final extraction window/effective date | Request record date: 2026-05-09. Effective extraction window/date must be confirmed and recorded in the later artefact creation/access slice before any artefact is created or accessed. This record does not invent an extraction timestamp. |
| Artefact location policy | Access-controlled non-repo storage only. No raw artefact contents in git. No patient-level contents in docs, PRs, logs, or evidence summaries. Exact storage location must be approved and recorded in the later artefact creation/access slice before any artefact is created, copied, hashed, stored, validated, or executed. |
| Manifest ID convention | `r4ob-full-eligible-YYYYMMDD-000001` |
| Request-scoped proposed manifest ID | `r4ob-full-eligible-20260509-000001` |
| Tool/CLI requirement | Future validation/no-write or guarded apply/write must use the committed guarded apply CLI from the repo SHA used for that future authorised slice. The exact tool/CLI commit SHA must be recorded in that future slice. This request record does not run the tool. |
| Owner statement | I confirm that no patient-level contents will be committed in docs, PRs, logs, or evidence summaries. |

The proposed manifest ID above does not mean a manifest exists. The actual
manifest ID and checksum must be generated and approved only in a later
separately authorised artefact and manifest creation slice.

## Request Policies

### Inclusion Rules

- Include only full eligible opening-balance rows that satisfy the approved R4
  opening-balance policy and are represented in an approved manifest.
- Include only rows that can be safely summarised without committing
  patient-level contents.
- Exact manifest-level inclusion must be confirmed in the later artefact and
  manifest slice.

### Exclusion Rules

- Exclude ineligible rows.
- Exclude ambiguous rows.
- Exclude unsupported rows.
- Exclude rows failing source or manifest checks.
- Exclude any row that cannot be safely represented without sensitive committed
  contents.
- Exclude any row that would require invoice, payment, or staging import
  intent.
- Exact manifest-level exclusion must be confirmed in the later artefact and
  manifest slice.

### Zero And Negative Balance Policy

- Zero balances must be explicitly classified in the manifest and excluded from
  opening-balance write proof unless separately approved.
- Negative balances must be explicitly classified in the manifest and must not
  be written unless the existing guarded apply design safely supports them and a
  separate policy approval exists.
- If support is ambiguous, fail closed and exclude from execution proof.

### Duplicate Handling Policy

- Fail closed on ambiguous duplicate source rows.
- Future guarded apply/write must rely on manifest-scoped idempotency
  references.
- Duplicate detection and any duplicate exclusions must be recorded in the
  manifest or evidence summary without patient-level contents.

### Currency And Decimal Policy

- Use GBP/pence-safe decimal handling.
- Expected total must be recorded exactly in the approved manifest.
- Any rounding or precision discrepancy must stop validation/apply until
  resolved.
- Do not infer final totals from the bounded fixture.

## Approval Statuses

| Gate | Status |
| --- | --- |
| Storage approval | Governance approved. Specific artefact storage location is not approved by this record and remains required in the later artefact creation/access slice. |
| Redaction approval | Governance approved. Specific artefact redaction review remains required in the later artefact creation/access slice. |
| Scratch/test target approval | Scratch/test-only constraint approved. Specific scratch/test target is not approved by this record and remains required before validation/no-write. |
| Validation/no-write status | Not authorised by this request record. Requires separate explicit authorisation after artefact/manifest package approval. |
| Guarded apply/write status | Not authorised by this request record. Requires validation/no-write evidence review/sign-off and separate explicit guarded apply/write authorisation. |
| Live finance import | Separate and unauthorised. |

## Non-Authorisation

This request record explicitly does not authorise:

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
- local scratch SQLite DB access;
- guarded scratch apply;
- CLI validation/no-write;
- live/default PMS DB writes;
- actual PMS Postgres writes;
- finance import;
- invoice, payment, or staging import;
- production execution;
- full eligible-row artefact execution.

## Redaction Boundary

Committed docs, PRs, logs, and evidence summaries for this request track must
not include:

- patient names;
- dates of birth;
- addresses;
- phone numbers;
- emails;
- clinical details;
- full artefact contents;
- raw R4 export contents;
- table extracts;
- unredacted DSNs or secrets;
- production/live-looking target details.

## Remaining Future Gates

Any future full eligible-row artefact package work remains separate and must
receive explicit authorisation for each gate:

1. artefact creation/access authorisation;
2. artefact storage approval;
3. manifest, checksum, and expected-total approval;
4. validation/no-write authorisation;
5. validation/no-write evidence sign-off;
6. guarded apply/write readiness check;
7. guarded apply/write authorisation;
8. guarded apply/write evidence sign-off;
9. live import, which remains separate and unauthorised.

No future gate is satisfied by this request record alone.
