# Dev seeds and smoke checks

These helpers are for development environments only.

## Seed recall data

Run the seed script to create a small set of recall rows and communications:

```
bash ops/seed_recalls_dev.sh
```

Guards:
- Requires `APP_ENV=development` or `ALLOW_DEV_SEED=1` in `.env`.
- Script is idempotent: it clears prior seeded rows (notes like `seed:`) and recreates them.

## Recall smoke test

Run a quick end-to-end check of the recalls pipeline:

```
bash ops/smoke_recalls.sh
```

This will:
- Call `/recalls` and `/recalls/export_count`
- Trigger a contact write on a seeded recall
- Confirm export_count cache hit/miss + invalidation logs

## Cleanup

Re-run the seed script to reset seeded recall data.
