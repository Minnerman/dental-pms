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

The owner subsequently selected **external AI** rather than an on-site model,
with provider/API-key setup deferred. The specific provider, model, billing and
privacy/retention arrangements have not been selected or approved. This is a
direction decision, not authorization to activate a processor or send notes.
Keep any future API key server-side, never in browser code or chat. Treat note
text as potentially identifiable health information even without separate name
or address fields; removing those fields alone does not establish anonymity.
The owner's stated 16GB practice-server RAM is not a verified capacity audit and
does not by itself rule out small local models; no server inspection or local
model installation was requested or performed.

Do not connect a new processor without resolving the privacy/setup requirements.
A future implementation should show
suggestions for explicit review and application to the unsaved draft, preserving
clinical meaning, tooth references, quantities and negation. Normal note saving,
permissions and revision history remain separate; historical records must never
be silently rewritten.
