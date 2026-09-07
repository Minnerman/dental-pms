# Treatment planning — first clinical workspace

## Scope

The Planned chart is separate from Current diagnosis. Explicitly starting a plan
captures the then-current native tooth, root, crown, surface and bridge findings,
and the existing local imported tooth-state projection. It does not contact R4.
The copy is retained rather than recaptured on refresh or when diagnosis changes.
Unspecified findings remain unspecified. Missing or partial imported coverage is
labelled; it is never silently filled from a later live chart.

This version has one planning workspace per patient. Multiple courses and
replacement snapshots are deferred. Bridges and dentures are linked appliances.
The existing diagnostic bridge geometry remains part of the captured chart.

## Planning and fees

- One clinical navigation row provides Current · Diagnosis, Planned and History,
  with Refresh alongside. Notes remain in the resizable sidebar and main patient
  Notes tab; no duplicate clinical Notes or Treatment plan subtabs are needed.
- Four compact levels target a tooth, its whole root area, its crown or selected
  surfaces. A fifth Miscellaneous tab records a patient-specific description
  (up to 2,000 characters) and explicit agreed fee, for example splints, retainers,
  examinations or visits. Zero requires an explicit waiver with a reason.
  Catalogue-based general treatments remain available through Add treatment.
- Miscellaneous items retain custom provenance and have no catalogue ID/quote.
  They do not create practice price-list entries, infer tooth targets or change
  the captured chart. They share the same lists, fee edits and audited lifecycle.
  Saved descriptions are preserved, not retrospectively rewritten.
- The Add treatment dialog also offers **Other treatment** for an explicitly
  selected tooth, whole-root, crown or surface target. It uses the same custom
  provenance and agreed fee/reasoned waiver; no procedure drawing is inferred.
- A clinical read-only picker uses the same active treatment/fee catalogue as
  Practice Treatments. Catalogue administration remains restricted as before.
  It initially searches all five practice levels, excluding unassigned demo/legacy
  entries from new selection. Selected-level filtering remains optional. A
  categorised treatment supplies its level, retaining the selected tooth where
  applicable and clearing incompatible surfaces. A compact review shows the
  target/drawing before Add; More options exposes manual settings and fee changes.
  Existing unassigned saved items keep their editing/history
  path. The opt-in `classified_only` API filter runs before count/paging and leaves
  older API queries compatible. The current UK-date price is resolved consistently during
  catalogue display and save; versions and effective dates are retained in new
  quotes. See [Practice treatment fees](PRACTICE_TREATMENT_FEES.md).
- For catalogue items, the selected identity, name/code, patient category and
  price basis are saved. Price-list changes do not reprice existing items.
- Drawing/material defaults can be saved explicitly in Practice Treatments.
  Owned routine-v1 identities supply reviewable suggestions when no default is
  saved; these do not backfill historical items or persist a practice setting.
  Free-text names and codes are never interpreted as clinical anatomy. Missing
  settings remain a manual choice. Crown/bridge/veneer, denture and filling/inlay
  materials use the diagnosis palette. Material
  can be corrected separately on an outstanding item, with its revision history;
  the fee, target and status remain unchanged. Old unspecified materials stay
  unspecified. Completed items must be uncompleted before material correction.
- Fixed fees can use the catalogue amount. Ranges require an agreed amount;
  unavailable prices are not treated as free. Overrides and waivers require
  explicit reasons. Entering an agreed amount for an unpriced routine records
  the factual default reason that no practice price was set; it remains editable
  under More options. An intentional catalogue zero remains distinct from a waiver.
- Proposed work is a distinct overlay; it does not erase baseline anatomy.
  Completed items and outstanding items have separate lists and totals.
- Both lists use compact, two-line selectable rows. One shared toolbar beside
  the totals operates on the highlighted item; Details preserves the complete
  quote, target, fee explanation and revision. Planned/completed P/C markers are
  50% larger without changing tooth anatomy or shifting the chart on selection.
- Earlier native items remain separate and manageable through the earlier-item
  view; they are not retrospectively adopted into a copied chart.

### Linked bridges and dentures

Add bridge opens a small arch selector: click the first and last teeth, then
review/edit the suggested abutment/pontic/abutment roles. Wings and cantilevers
are represented by explicit member roles; no support suitability is inferred.
Every intervening position belongs to the contiguous span. Add denture selects
one arch and explicit replacement teeth, including non-contiguous sites or Full
denture. An explicit material is required for a new appliance; one material and
one save cover the whole appliance. An unambiguous
matching fee template may be preselected for review; otherwise select it once.
Appliance pickers filter matching explicit/default routine profiles before
paging, not by treatment-name guesses.

One item stores an explicit appliance member list in existing planning JSON,
with a null legacy tooth target rather than falsely assigning the group to its
first tooth. Bridge quotes retain the original unit fee and multiply by member
count; denture quotes retain one appliance fee regardless of replacement count.
The scaled total quote stays frozen, including for later Edit fee/catalogue
restoration. Total overrides need not divide evenly between units. Owned small/
large acrylic and cobalt-chrome routines check replacement count/material;
custom configured profiles remain flexible. Existing individual bridge/denture
items are not silently regrouped or repriced.

Each appliance has one compact row, revision, completion, charge and audited
Uncomplete action. There is no partial appliance completion or reversal. Proposal
may precede extraction, but completion checks effective Current anatomy: replacement
sites must be explicitly missing, supports available, and implant fixtures cannot
be wings. A rejected group saves no partial procedures or charges. Completion
shows rootless pontics/denture teeth and role-specific connected bridge artwork;
ordinary native anatomy is never fabricated. Proposed artwork is only in Planned;
completed artwork appears in both views. Later material edits retain appliance
identity; explicit anatomy/native bridge changes supersede it. Patient and tooth
journals retain every member/role, including voided completion history.
If later Current findings establish support that the frozen planning baseline
does not contain, Planned retains its unapplied-effect warning instead of
inventing historical support anatomy; Current uses the reviewed current findings.

## Completion and history

Adding or editing a proposal creates neither a clinical procedure nor a charge.
Completion requires clinical and billing permissions and explicit confirmation
of the saved fee. It uses the existing atomic procedure/ledger completion path;
positive fees create one charge and a zero fee creates no charge. It does not
create an invoice or rewrite the original diagnosis observations.

### Completed appearance in both charts

The Planned chart folds active native completions over the immutable captured
baseline in completion order. Planned extraction is a blue/teal cross; completed
extraction removes the tooth anatomy. An implant completion displays the implant
fixture. Crowns and selected filling surfaces use the explicit saved material,
with root filling/post/core and apicectomy using the existing diagnosis artwork.
Uncomplete recomputes from the baseline and remaining active completions, not a
destructive whole-tooth restore. Missing support is not invented: for example a
crown at a missing site does not manufacture natural roots.

Current · Diagnosis presents the same completion effects over native observations
without rewriting them. A patient-scoped read-only audit projection supplies
active completion identity/order and latest explicitly observed field order.
Later tooth conditions/reset supersede older effects; later crown, root or
individual surface observations supersede only their fields. Movement, rotation
and deciduous identity remain independent and do not resurrect an extracted tooth.
Thus Uncomplete preserves later diagnostic edits as well as original history.

Current authoring uses the effective anatomy for eligibility and a projection
revision token under the patient lock, in addition to native row revisions.
Ambiguous completion metadata is reported as unavailable and blocks edits rather
than guessing. Native tooth rows/revisions and the captured baseline remain raw;
no historical clinical information is backfilled. These additions use existing
JSON/audit storage and require no new migration.

Version checks prevent stale edits. Request fingerprints distinguish safe
retries from reuse with different content, and item revisions retain the saved
quote/fee/status history. Completed items cannot be edited through ordinary
status/fee controls; declined and cancelled items remain final.

### Correcting an accidental completion

Uncomplete is an explicit, permission-checked correction, not deletion. It
requires clinical and billing write permissions, the current item revision,
a nonblank reason (maximum 500 characters), finance confirmation and a guarded
request identifier. The item returns to its exact previous Proposed or Accepted
status. Its original procedure is marked voided, retained with its original
text, author and time, and excluded from active completed-treatment projections.
The journal displays the voided completion and correction reason explicitly.

The original charge is retained. A positive saved fee receives an equal negative
adjustment; a zero fee creates no ledger entry. Payments and invoices are not
changed and no refund is sent. If payment was already recorded, the correction
may leave account credit that requires the normal finance workflow. Re-completing
the item creates a separate procedure/charge cycle, not a duplicate first charge.
Completion cycles, reversals, item revisions and audit entries retain the history.

Items completed before migration 0060 can be corrected only when adjacent saved
item revisions and a unique matching procedure/charge establish the original
state unambiguously. No historical completion is backfilled during migration.
Ambiguous or mismatched records, invoice-linked charges and duplicate references
fail closed and require review instead of a guessed reversal. Earlier unlinked
items remain outside this correction workflow.

## Release boundary

Migrations 0059, 0060, 0061 and 0062 are required. Migration 0060 adds completion/reversal
records and the voided procedure status without rewriting source records.
Migration 0061 adds the explicit practice treatment index and immutable dated
fee history, preserving the original undated fees. Populated index/history
metadata blocks its destructive downgrade.
Migration 0062 adds nullable practice planning defaults and their revision;
no existing treatment defaults, prices or clinical records are backfilled.
Populated defaults/revision history or grouped items block downgrade to a binary
that does not understand them.
Apply and verify only in disposable or
explicitly authorised environments. A populated planning workspace must not be
silently dropped by a downgrade; 0060 also refuses downgrade when completion
cycles, reversals or voided procedures exist. This feature does not authorise production
deployment, a production migration, R4 access or alteration, or any AI service.
Local preview examples and their fees are synthetic, not the practice price list.

Miscellaneous uses the existing schema (no additional migration). Once custom
items exist, retain a compatible API/frontend that understands nullable catalogue
linkage and custom provenance; older planning binaries cannot safely read or edit
those records. Unknown save results must be retried with the same request token or
explicitly reviewed before entering the treatment again. In-page progress dialogs
protect the current request, not forced browser reload or closing the browser.

After linked planning items exist, do not offer an older application binary as a
writable rollback: it lacks the revision-aware endpoint guard for those items.
Likewise, an application predating 0060 does not understand voided completions
and must not be used against a database containing these corrections.
Preserve the database and obtain a compatible fix or a separately reviewed
recovery path. Likewise, switching a local preview back to its earlier database
after new entries have been saved would hide those entries and is not a safe
rollback without reconciliation.
