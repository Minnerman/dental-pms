# R4 Finance Opening-Balance Full Eligible-Row Artefact Package Request Readiness

Status date: 2026-05-09

Assessment baseline: `origin/master@2870ab70641ccb4dbb11e0177bf9cfe9b9eb1259`

This is a readiness and gap note only. It assesses whether the committed docs
contain enough non-sensitive, owner-provided information to create a specific
full eligible-row opening-balance artefact package request record.

No specific full eligible-row artefact package request record has been created
by this note. The signed-off package request/template remains the governing
structure:

- `docs/r4/R4_FINANCE_OPENING_BALANCE_FULL_ELIGIBLE_ARTEFACT_PACKAGE_REQUEST.md`

This note does not authorise artefact creation, artefact access, artefact
copying, artefact hashing, artefact storage, validation/no-write, guarded
apply/write, execution, import, or production use.

No R4 access occurred. No real R4 artefact was accessed. No real patient data
was used. No PMS database connection occurred. No scratch execution occurred.

`finance_import_ready=false`. Live finance import remains out of scope.
Migration/import is not complete. Production readiness is not established. Full
eligible-row artefact execution has not happened.

## Decision

A specific full eligible-row artefact package request record cannot be created
from the current committed docs without inventing owner-provided details.

The repo contains the approved request structure, governance rules, and some
source/policy context. It does not contain a complete, concrete owner-approved
request payload for the future full eligible-row package.

## Required Inputs Present

The following non-sensitive inputs or constraints are present in committed docs:

- approved package request/template and owner sign-off;
- approved provenance/redaction governance proposal and owner sign-off;
- current assessment repo SHA:
  `2870ab70641ccb4dbb11e0177bf9cfe9b9eb1259`;
- high-level source context: the opening-balance source track is based on R4
  `PatientStats` balance snapshot planning;
- extraction purpose context: future full eligible-row opening-balance package
  governance;
- source policy context: `PatientStats` rows only, non-zero balances eligible
  if all future gates pass, and zero balances treated as no-op unless a later
  explicit proof changes that policy;
- zero/negative balance policy context: positive and negative balances may be
  eligible if all gates pass; zero balances create no row;
- duplicate handling context: duplicate source or mapped-patient ambiguity must
  fail closed;
- currency/decimal context: balances must be handled as exact decimal/pence
  values;
- scratch/test-only target constraint;
- explicit rule that no patient-level contents or full artefact contents may be
  committed.

These items are not enough to create a specific request record because several
request fields still require owner selection, approval, or confirmation.

## Missing Inputs Requiring Owner Decision

The following required request fields are missing, ambiguous, or not yet
owner-approved for a specific full eligible-row package request:

- request ID;
- requesting owner;
- artefact owner;
- approving owner or role;
- specific source system description for the request record;
- final extraction purpose for the specific request;
- extraction method description for this specific request;
- extraction effective date or window;
- expected artefact location policy;
- proposed manifest ID convention or concrete manifest ID;
- tool/CLI version or commit SHA requirement for the request record;
- final inclusion rules for the specific request;
- final exclusion rules for the specific request;
- final zero/negative balance policy for the specific request;
- final duplicate handling policy for the specific request;
- final currency/decimal policy for the specific request;
- storage approval status;
- redaction approval status;
- scratch/test target approval status;
- validation/no-write authorisation status;
- guarded apply/write authorisation status;
- explicit owner statement for the specific request that no patient-level
  contents will be committed.

The current repo SHA is available for this assessment, but any future specific
request record should bind to the repo SHA current at that future request
record slice.

## Next Owner Decision Required

Before a specific package request record can be created, the owner must provide
or explicitly approve a non-sensitive request payload that fills every required
field above. The payload must remain limited to governance/request metadata and
must not include patient-level contents, full artefact contents, unredacted DSNs,
secrets, or production/live-looking target details.

Any future request record remains a separate explicit slice. Creating that
record would still not authorise R4 access, real artefact access, artefact
creation, artefact hashing, artefact storage, validation/no-write, guarded
apply/write, PMS DB connection, finance import, production execution, or full
eligible-row artefact execution unless a later task explicitly authorises that
exact gate.
