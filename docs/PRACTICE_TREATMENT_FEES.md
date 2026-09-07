# Practice treatment index and effective-dated fees

The administrator's **More → Treatments** page is the practice's routine price
index. It groups treatments in this order: tooth, root, crown, surface and
miscellaneous. The former **Other existing treatments** section is omitted from
this page. Its uncategorised records are retained in storage for existing patient
plans and history; this display change does not delete or deactivate treatments.
Ordinary reads never infer or assign their level.

The treatment-planning picker uses the same active, categorised practice list.
It searches all five levels by default; **Selected level only** is an optional
filter. Uncategorised demo/legacy entries are not offered for new selection, but
existing saved items retain their captured identity, fee and editing/history path.
Unpriced practice treatments are still offered and require an agreed fee or
explicit waiver. Choosing another category does not silently move the clinical
target: **Use Tooth level** (or its equivalent) explicitly changes the level,
retains the selected tooth where applicable and clears incompatible surfaces and
drawing selection. The dentist still chooses the drawing and any missing target.

## Routine list and day-to-day use

**Add missing routine treatments** explicitly adds the owner's routine list. It
is idempotent and does not invent prices, remove existing records or rewrite
saved patient plans. If exactly one compatible existing entry matches a routine
name after trimming and case-folding, this explicit action classifies that entry
while retaining its identity, content, prices and active/inactive state. Multiple
matches or a conflicting level reject the whole action for manual review before
any changes are made. A fee marked **Not set** is not a free treatment.

The button opens an in-page confirmation (not a browser confirmation prompt).
Nothing is submitted until **Add missing treatments** is chosen. The result stays
visible and reports either how many were added or that the full routine list was
already present. Use **+ Add treatment** within a category for a different entry
of your own. Pending requests cannot be submitted twice or dismissed; an
unconfirmed result can be safely retried because routine initialization is
idempotent. Existing prices are never replaced by this action.

Use the fee-scheme selector for clinic private, domiciliary private or Denplan.
Each row shows the current fee and its next scheduled change. **Edit fee** opens
the current price, new price and effective date, all upcoming changes and paged
fee history. Fixed amounts, agreed ranges, not-applicable and explicitly unset
fees remain distinct. Blank, negative, over-precision and over-limit amounts are
not converted to zero. An explicit fixed zero is retained as £0.00.

- Today changes the current catalogue price; a future date schedules a price.
- The authoritative day is the server's `Europe/London` practice date, including
  daylight-saving transitions. No background job is required for activation.
- If more than one version has the same effective date, the newest revision is
  the applicable price. Earlier revisions remain available in history.
- To correct a scheduled price, choose **Change this date's fee** and save the
  corrected amount. This does not remove other future changes.
- Backdating native changes is rejected. An original fee without a recorded
  effective date remains an undated baseline; the application does not invent
  historical dates.
- Treatment Details edits name, level, practice code, description, ordering,
  duration, active state and the existing Denplan inclusion default.

Every level also offers **Other treatment** during patient planning, with an
explicit target, description and agreed fee or reasoned waiver. These one-off
items do not create catalogue rows or fabricated quotes. For a repeatable
routine price, add a treatment to the index instead.

## Clinical and financial boundaries

Catalogue selection and quote validation share the current-fee resolver. Fee
publication and plan creation lock the same treatment record, including when
there was no previous fee row. New catalogue snapshots retain the selected fee
version and effective date when present. A stale quote is rejected instead of
silently substituted. Existing saved prices, diagnoses, procedures, invoices and
ledger entries are never repriced when the practice index changes.

The new fee editor uses an expected schedule revision and a request identifier.
Duplicate unchanged requests return the existing result; conflicting requests
fail closed. Pending saves block the editor. An unknown result locks its values
and permits an unchanged retry, or explicit closure and review. Unsaved browser
drafts are not guaranteed to survive forced reload or closing the browser.

## Storage and operational scope

Additive migration `0061_treatment_index_effective_fees` is required. Existing
fee rows are retained as the original baseline and new fee versions are appended
with provenance. The legacy fee-list API remains compatible, resolving today's
prices; its replacement write appends today's differences rather than deleting
history or future schedules. The new dated editor is the preferred writer.

Do not use older application writers after date-effective data is entered.
Restoring an older database would discard newer clinical and fee records. A
production migration or deployment remains separately authorised; local preview
verification is not a production rollout. No R4 access or R4 changes are needed.
