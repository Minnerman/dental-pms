# Clinical notes migration contract

Status: design and acceptance contract; not evidence that migration or R4 parity is complete.

## Scope and evidence

The user wants a less crowded, R4-familiar clinical-notes workspace. The approved
architecture is a unified, source-aware, paged view over the existing native and
imported tables. It is **not** a flattened replacement table, a new import, or
permission to access or modify R4. R4 writes remain prohibited. Any new source
profiling requires separately authorised, positively verified read-only access.

Evidence used for the UI direction:

- **Observed in supplied R4 screenshots:** an independently scrolling notes panel;
  Today and dated groups; All / Treatment / Notes filters; search and clear
  controls; author/provider attribution; a dated-group lock icon; narrative and
  treatment events in the same feed. Disclosure controls are visible, but exact
  collapse behaviour and panel-resize gestures are not established by still images.
- **Observed in supplied template screenshots:** searchable categories/templates,
  a narrative editor with an inline answer placeholder and New Target / Save
  controls, and a separate searchable code-assignment pane. This does not establish
  prompt types, dropdown choices, validation, or automatic insertion behaviour.
- **Confirmed by published R4 help:** editable clinical-note templates can belong
  to categories, be assigned to treatment codes, or be used through free-text
  input. See [R4 v8.1.3](https://help.carestreamdental.com/rh/web/server/R4/projects_responsive/R4%20Online%20Help/8.1.3.htm).
- **Confirmed by published R4 help:** an author/provider-only note editing and
  locking policy exists. Exact lock timing, unlock permissions, and revision
  retention are not established by that source. See [R4 v8.1.6](https://help.carestreamdental.com/rh/web/server/R4/projects_responsive/R4%20Online%20Help/8.1.6.htm).
- **Distinct mechanism:** the chart-in-use concurrency lock is not a note signature
  or finalisation rule. See [R4 v8.1.4](https://help.carestreamdental.com/rh/web/server/R4/projects_responsive/R4%20Online%20Help/8.1.4.htm).

The familiar layout is a product design choice, not proof of data equivalence.
Sensei Cloud, SoftDent and WinOMS documentation must not be treated as R4 evidence.
No patient text or screenshots belong in this document, test fixtures, or reports.

## Source-aware records and presentation

1. Keep each record's original source namespace and source key. A UI/feed identifier
   must distinguish equal keys from different tables or systems. Preserve the
   original patient reference and its explicit PMS patient mapping; quarantine
   unresolved or ambiguous mappings rather than attaching notes by name or guess.
2. Retain original clinical/event dates, creation/modification dates, author and
   provider codes, raw text, and available code/tooth/event associations. Preserve
   source precision and raw values where interpretation is incomplete. Do not
   substitute an import timestamp for an unknown clinical date, infer a timezone,
   or assign the importer as the historical author.
3. The unified view must identify the source and keep narrative notes distinct from
   treatment events and other imported record types. Never infer completed
   treatment, billing, authorship, lock/signature status, or a clinical finding
   merely from note wording or a template/code association.
4. Use stable ordering with a source/key tie-breaker and a consistent pagination
   boundary. Date headings and filters are presentation only: they must not drop
   records, change chronology, or merge separate records. Unknown dates remain
   visibly classified rather than assigned a convenient date.
5. Preserve raw content independently of any safe display conversion. Rendering
   must not execute imported HTML, scripts, macros, or links automatically. If a
   format cannot be rendered faithfully, retain it and disclose the limitation;
   do not silently strip it or replace it with a generated summary.
6. Existing imported records remain read-only. Corrections are separate attributed,
   dated records linked to their original; they do not overwrite imported text.
   Native edits require explicit revisions with retained previous content and
   author/time attribution. Concurrent edits must not silently overwrite each
   other. These are PMS safety requirements, not claims about R4's revision model.
7. A later authorised import must be replay-safe using stable source identity.
   Replaying the same source record cannot create another patient note. Changed
   content for the same key must be detected and reconciled, never silently
   overwritten or treated as a second unrelated note. Identical text with distinct
   legitimate source keys must not be deduplicated solely by content.

## Templates and historical notes

- Keep reusable template definitions separate from completed patient-note content.
- Retain available template identifiers/versions, prompt definitions, selected
  answers and code mappings without inventing missing metadata. Classify unknown
  tokens and mappings for review.
- A new native templated note retains the completed text and the template snapshot
  used to create it. Later template edits must not change an existing note.
- Never re-expand historical notes using today's template, patient values,
  clinician details, or treatment status. Never generate a clinical assertion,
  treatment completion, or charge merely because a template was inserted.

## Acceptance gate for later migration work

Before claiming migration coverage, an authorised profiling exercise must define
the actual source tables, supported formats, mapping rules, exclusions and unknowns.
No conversion or compatibility percentage is promised before that evidence exists.

Acceptance requires documented, reproducible checks using protected evidence:

- Reconcile source and destination counts by **source, patient mapping and date**,
  including unknown-date buckets, exclusions, corrections and any separately
  represented revisions. Explain every difference; a filtered UI count alone is
  insufficient.
- Compare per-record content checksums using an explicitly documented serialization
  that preserves the original content. Check identity/association metadata
  separately. Do not normalize away whitespace, Unicode, or formatting differences
  simply to make a comparison pass.
- Report unknown/unmapped author codes, patients, dates, status values, templates,
  treatment codes, tooth references and unsupported formats as explicit categories.
  No ambiguous record may disappear from reconciliation.
- Verify samples covering long notes, multiline text, Unicode and punctuation,
  supported formatting, treatment codes and tooth associations, multiple records
  on one date, unknown dates/authors, historical locks/revisions when available,
  and template answers. Synthetic fixtures test the rules; authorised source
  samples are needed to establish real conversion fidelity.
- Test replay without duplicates, same-key changed-content detection, cross-source
  key collisions, deterministic pagination/filtering, patient isolation, imported
  read-only enforcement, and explicit native correction/revision behaviour.
- Keep patient content out of logs, Git, screenshots and public reports. Publish
  classifications and aggregate reconciliation results, retaining detailed evidence
  only in the authorised protected location.

An unresolved source format or mapping blocks the affected claim of fidelity, not
unrelated PMS development. It must remain preserved and explicitly classified.
