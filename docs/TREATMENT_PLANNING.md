# Treatment planning — first clinical workspace

## Scope

The Planned chart is separate from Current diagnosis. Explicitly starting a plan
captures the then-current native tooth, root, crown, surface and bridge findings,
and the existing local imported tooth-state projection. It does not contact R4.
The copy is retained rather than recaptured on refresh or when diagnosis changes.
Unspecified findings remain unspecified. Missing or partial imported coverage is
labelled; it is never silently filled from a later live chart.

This first version has one planning workspace per patient. Multiple courses,
replacement snapshots, connected planned bridge groups, planned crown-material
colours and automatic updates of diagnosis after completion are deferred.
The existing diagnostic bridge geometry remains part of the captured chart.

## Planning and fees

- Four compact levels target a tooth, its whole root area, its crown or selected
  surfaces. General examination, hygiene and visit items use Add treatment.
- A clinical read-only picker uses the same active treatment/fee catalogue as
  Practice Treatments. Catalogue administration remains restricted as before.
- The selected catalogue identity, name/code, patient category and price basis
  are saved with each item. Price-list changes do not reprice existing items.
- The drawing kind is selected explicitly. Free-text names and codes are not
  interpreted as clinical anatomy.
- Fixed fees can use the catalogue amount. Ranges require an agreed amount;
  unavailable prices are not treated as free. Overrides and waivers require
  reasons. An intentional catalogue zero remains distinct from a waived fee.
- Proposed work is a distinct overlay; it does not erase baseline anatomy.
  Completed items and outstanding items have separate lists and totals.
- Both lists use compact, two-line selectable rows. One shared toolbar beside
  the totals operates on the highlighted item; Details preserves the complete
  quote, target, fee explanation and revision. Planned/completed P/C markers are
  50% larger without changing tooth anatomy or shifting the chart on selection.
- Earlier native items remain separate and manageable through the earlier-item
  view; they are not retrospectively adopted into a copied chart.

## Completion and history

Adding or editing a proposal creates neither a clinical procedure nor a charge.
Completion requires clinical and billing permissions and explicit confirmation
of the saved fee. It uses the existing atomic procedure/ledger completion path;
positive fees create one charge and a zero fee creates no charge. It does not
create an invoice or mark diagnosis as treated automatically.

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

Migrations 0059 and 0060 are required. Migration 0060 adds completion/reversal
records and the voided procedure status without rewriting source records.
Apply and verify only in disposable or
explicitly authorised environments. A populated planning workspace must not be
silently dropped by a downgrade; 0060 also refuses downgrade when completion
cycles, reversals or voided procedures exist. This feature does not authorise production
deployment, a production migration, R4 access or alteration, or any AI service.
Local preview examples and their fees are synthetic, not the practice price list.

After linked planning items exist, do not offer an older application binary as a
writable rollback: it lacks the revision-aware endpoint guard for those items.
Likewise, an application predating 0060 does not understand voided completions
and must not be used against a database containing these corrections.
Preserve the database and obtain a compatible fix or a separately reviewed
recovery path. Likewise, switching a local preview back to its earlier database
after new entries have been saved would hide those entries and is not a safe
rollback without reconciliation.
