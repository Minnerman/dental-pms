# Practical completion UAT checklist

Use one designated synthetic/test patient and representative staff accounts. Allow 45–60 minutes. Record `pass` or `fail` and a short blocker note for every row; a failure is a blocker only when it prevents or makes unsafe routine practice work.

## Reception/admin

| Action | Expected result | Pass/fail | Blocker note |
| --- | --- | --- | --- |
| Sign in as reception, open the main work areas, then sign out. | Authentication succeeds, permitted navigation loads, and sign-out returns to login. |  |  |
| Create a test patient, find them by partial search, reopen the record, and edit contact details. | The patient is searchable once, the correct record opens, and edits persist after refresh. |  |  |
| Add and edit a patient note, then open its audit history. | The current note is shown and created/updated audit entries identify the acting user. |  |  |
| Create an appointment, move it to another valid slot, refresh, then cancel it with a reason. | The diary and day sheet show the persisted slot and final cancelled state without duplication. |  |  |
| Archive and restore the test patient after dependent workflow checks are complete. | The archived record leaves ordinary active views and returns with its history after restore. |  |  |

## Dentist/clinical

| Action | Expected result | Pass/fail | Blocker note |
| --- | --- | --- | --- |
| Open the test patient’s clinical page, select a tooth and surface, and view tooth history. | Both arches, tooth surfaces, clinical summary and history render without error. |  |  |
| Add a tooth note and a planned treatment, then change the treatment to a supported next status. | The chart, history and treatment plan refresh; planned and completed/history states remain distinct. |  |  |
| Record a valid six-value BPE entry and reopen the clinical page. | The saved BPE values persist and render using the current supported notation. |  |  |
| Sign in as a clinical read-only user and reopen the same record. | Clinical information remains viewable while note, BPE and treatment mutation controls are unavailable. |  |  |

## Finance/recall/documents

| Action | Expected result | Pass/fail | Blocker note |
| --- | --- | --- | --- |
| Record one routine payment and one adjustment, then refresh the ledger and daily cash-up. | Both entries, balance and cash-up totals persist with the correct signs and payment method. |  |  |
| Use a user without `billing.view`/`billing.cashup` to open patient finance, cash-up, reports and the global audit feed. | Financial data and the global audit feed remain blocked; no background finance request succeeds. |  |  |
| Create or update a recall, find it with the worklist filters, and use the booking hand-off. | The recall remains visible under the selected filters and the patient booking context opens correctly. |  |  |
| Generate a patient document from an active template and save it to the test patient. | The generated document is listed once with the correct metadata and no raw merge-field error. |  |  |
| Upload a small synthetic attachment, refresh the list, and open/download it. | Metadata and filename are safe, the file is available once, and the action is audited. |  |  |

## Operational sign-off

| Action | Expected result | Pass/fail | Blocker note |
| --- | --- | --- | --- |
| Run the standard application health check. | Backend, frontend, proxy/login and database checks pass at the intended runtime SHA. |  |  |
| Confirm the scheduled backup timer and latest natural backup status without running a manual backup. | The timer is enabled/active and the latest scheduled run is successful under current retention. |  |  |
| Confirm the documented application-only rollback references and operator contact are available. | Backend/frontend rollback can be performed without changing the database or volumes. |  |  |
| Record tester names/roles, date, overall result and every accepted blocker/deferment. | Owner and staff have one complete sign-off record and no unresolved daily-use blocker. |  |  |
