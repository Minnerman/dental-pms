# Product decisions

## UK postcode/address lookup — 2026-09-06

The owner chose **Ideal Postcodes** for the later postcode-to-address lookup
integration. Keep manual address entry available. This decision does not
authorize account creation, purchases, credential changes, sharing patient data,
or activating the service. Confirm the intended service configuration and costs
before connecting it.

## Clinical note writing assistance — 2026-09-06

The owner requested an AI writing-correction control beside Note text. There is
no configured AI provider or on-site model in the current application. The
control is visibly marked **Not connected** and only explains this limitation;
it receives no note text, makes no requests and does not change or save a draft.

On-site versus approved external processing remains undecided. Do not connect a
new processor or download/configure a model without resolving that choice and
the relevant privacy/setup requirements. A future implementation should show
suggestions for explicit review and application to the unsaved draft, preserving
clinical meaning, tooth references, quantities and negation. Normal note saving,
permissions and revision history remain separate; historical records must never
be silently rewritten.
