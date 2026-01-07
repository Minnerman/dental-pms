# R4 UX Mapping

This doc maps common R4 workflows to the PMS UI.

## Diary / Day Sheet
- R4 Day Sheet: `/appointments` with the "Day sheet" toggle.
- Calendar view: same page with the "Calendar" toggle.
- Actions: right-click appointment for cancel/cut/copy; click slot to paste.

## Patient workspace
- R4 patient tabs: in-app tabs at the top of the shell (persisted).
- Patient home: `/patients/[id]` summary + appointments + finance snapshot.
- Book appointment: patient home "Book appointment" button.
- Patient alerts/flags: badges in patient header + Day Sheet icons.

## Cancellations
- Cancel with reason: diary context menu -> Cancel… (reason required).
- Reason shows in patient appointment history.

## Recalls
- Recall list/worklist: `/recalls` with overdue/30/60/90 filters.
- Patient recall controls: Recall panel on `/patients/[id]`.

## Finance / Ledger
- Patient ledger: `/patients/[id]` Ledger tab with charges/payments and running balance.
- Quick payment: Patient home -> Finance panel -> Add payment.
- Cash-up: `/cashup` daily totals by payment method.

## Clinical chart
- Odontogram + tooth history: `/patients/[id]` Clinical tab -> Chart.
- Treatment plan: `/patients/[id]` Clinical tab -> Treatment plan.
- Clinical notes: `/patients/[id]` Clinical tab -> Notes.

## Notes and treatments
- Notes master-detail: `/notes` left list + right detail.
- Treatments master-detail: `/treatments` list + detail panel.
