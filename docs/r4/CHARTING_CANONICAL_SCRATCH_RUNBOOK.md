# Charting Canonical Scratch Dry-Run/Parity Runbook

This runbook prepares the isolated PMS target required for the current-master
all-domain charting canonical dry-run/parity transcript.

It is intentionally scratch-only:

- R4 access remains SQL Server SELECT-only.
- PMS writes are allowed only to a throwaway Docker Compose project and its
  project-scoped Postgres volume.
- The long-lived default `dental-pms` Compose project and `dental_pms` database
  must not be used.
- Production compose, runtime, Docker, frontend, and ops files are not changed.

## Active Domain Scope

Use the active 15-domain charting canonical scope:

```bash
DOMAINS="appointment_notes,bpe,bpe_furcation,chart_healing_actions,completed_questionnaire_notes,completed_treatment_findings,old_patient_notes,patient_notes,perio_plaque,perioprobe,restorative_treatments,temporary_notes,treatment_notes,treatment_plan_items,treatment_plans"
```

Use this date window unless the readiness docs are updated with a narrower
current-master window:

```bash
CHARTING_FROM="2017-01-01"
CHARTING_TO="2026-02-01"
```

Use a high per-domain cohort limit, then check the selector report to prove the
limit did not truncate any domain before continuing:

```bash
COHORT_LIMIT="50000"
COHORT_ORDER="hashed"
COHORT_SEED="564"
```

## Scratch Project Setup

Run this from a clean worktree based on the master commit under test.

```bash
cd /home/amir/dental-pms-charting-dryrun-execution
git rev-parse HEAD
git rev-parse origin/master
git status --short
```

Create a unique Compose project, artifact directory, scratch DB name, and
alternate ports. Do not reuse `COMPOSE_PROJECT_NAME=dental-pms`.

```bash
export SCRATCH_PROJECT="dentalpms_charting_scratch_$(date +%Y%m%d_%H%M%S)"
export SCRATCH_DB="dental_pms_charting_scratch"
export SCRATCH_POSTGRES_PORT="5549"
export SCRATCH_BACKEND_PORT="8209"
export SCRATCH_FRONTEND_PORT="3209"
export RUN_DIR=".run/charting_canonical_all_domain_${SCRATCH_PROJECT}"
mkdir -p "$RUN_DIR"
```

Create an untracked scratch `.env` in the clean worktree. Keep R4 SQL Server
credentials out of this file; `docker-compose.r4.yml` loads them from the local
secret file.

```bash
umask 077
cat > .env <<EOF
POSTGRES_DB=${SCRATCH_DB}
POSTGRES_USER=dental_pms
POSTGRES_PASSWORD=scratch-only-change-me
POSTGRES_PORT=${SCRATCH_POSTGRES_PORT}
BACKEND_PORT=${SCRATCH_BACKEND_PORT}
FRONTEND_PORT=${SCRATCH_FRONTEND_PORT}
APP_ENV=development
SECRET_KEY=scratch-charting-secret-key-change-me-32chars
JWT_SECRET=scratch-charting-jwt-secret-change-me-32chars
JWT_ALG=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=120
RESET_TOKEN_EXPIRE_MINUTES=30
RESET_TOKEN_DEBUG=false
RESET_REQUESTS_PER_MINUTE=5
RESET_CONFIRM_PER_MINUTE=10
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=ScratchAdmin123!
FEATURE_CHARTING_VIEWER=false
ENABLE_TEST_ROUTES=false
NEXT_PUBLIC_FEATURE_CHARTING_VIEWER=0
REQUIRE_CHARTING_PARITY=0
NEXT_PUBLIC_API_BASE=/api
FRONTEND_BASE_URL=http://localhost:${SCRATCH_FRONTEND_PORT}
BACKEND_BASE_URL=http://localhost:${SCRATCH_BACKEND_PORT}
APP_BASE_URL=http://localhost:${SCRATCH_FRONTEND_PORT}
R4_SQLSERVER_ENABLED=false
R4_SQLSERVER_READONLY=true
EOF
```

Validate the scratch env and inspect for project/port collisions before any
container is started.

```bash
export COMPOSE_PROJECT_NAME="$SCRATCH_PROJECT"
bash ops/env_check.sh
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml config > "$RUN_DIR/compose_config.yml"
docker compose ls | tee "$RUN_DIR/compose_ls_before.txt"
docker ps --format '{{.Names}} {{.Ports}}' | tee "$RUN_DIR/docker_ps_before.txt"
```

Abort if any selected port is already listening:

```bash
for port in "$SCRATCH_POSTGRES_PORT" "$SCRATCH_BACKEND_PORT" "$SCRATCH_FRONTEND_PORT"; do
  if ss -ltn | awk '{print $4}' | grep -q ":${port}$"; then
    echo "Port ${port} is already in use; choose another scratch port."
    exit 1
  fi
done
```

Confirm the R4 secret file is readable without printing secrets. The future R4
commands still pass `-e R4_SQLSERVER_ENABLED=true` and
`-e R4_SQLSERVER_READONLY=true` explicitly, so the command environment enforces
the R4 latch and read-only mode even if the local secret omits either key.

```bash
test -r /home/amir/secrets/dental-pms-r4.env
rg -q '^R4_SQLSERVER_ENABLED=true$' /home/amir/secrets/dental-pms-r4.env
```

## Start Scratch DB And Apply Migrations

Start only the scratch database first. The project name and `.env` make the
volume name project-scoped, for example
`${SCRATCH_PROJECT}_dental_pms_db_data`.

```bash
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml up -d db
```

Wait for scratch Postgres:

```bash
for attempt in $(seq 1 30); do
  if docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml exec -T db sh -lc 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'; then
    break
  fi
  sleep 2
done
```

Apply migrations into the scratch DB only:

```bash
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml run --rm --no-deps backend sh -lc 'python -m alembic upgrade head'
```

Start backend only; the frontend is not required for this transcript.

```bash
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml up -d backend
```

## Required Safety Checks Before Any Apply

Do not run `--apply --confirm APPLY` until all checks in this section pass.

Confirm the Compose project is the scratch project:

```bash
test "$COMPOSE_PROJECT_NAME" = "$SCRATCH_PROJECT"
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml ps | tee "$RUN_DIR/compose_ps_before_apply.txt"
```

Confirm the target database is the scratch database:

```bash
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml exec -T db sh -lc '
  test "$POSTGRES_DB" = "dental_pms_charting_scratch"
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "select current_database();"
' | tee "$RUN_DIR/current_database_before_apply.txt"
```

Confirm backend points at the scratch Postgres service and not the default
long-lived target:

```bash
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml exec -T -e R4_SQLSERVER_ENABLED=true -e R4_SQLSERVER_READONLY=true backend sh -lc '
  test "$R4_SQLSERVER_ENABLED" = "true"
  test "$R4_SQLSERVER_READONLY" = "true"
  case "$DATABASE_URL" in
    *"@db:5432/dental_pms_charting_scratch") exit 0 ;;
    *) echo "Unexpected DATABASE_URL target"; exit 1 ;;
  esac
'
```

Confirm the scratch canonical tables are empty before the first import:

```bash
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml exec -T db sh -lc '
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "select count(*) from r4_patient_mappings;"
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "select count(*) from r4_charting_canonical_records;"
' | tee "$RUN_DIR/scratch_counts_before_apply.txt"
```

## All-Domain Execution Sequence

Every command that touches R4 passes `-e R4_SQLSERVER_ENABLED=true` and
`-e R4_SQLSERVER_READONLY=true`. The SQL Server extractor and cohort/parity
helpers also require the read-only config before querying R4.

Select the deterministic all-domain cohort:

```bash
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml exec -T -e R4_SQLSERVER_ENABLED=true -e R4_SQLSERVER_READONLY=true backend \
  python -m app.scripts.r4_cohort_select \
    --domains "$DOMAINS" \
    --date-from "$CHARTING_FROM" \
    --date-to "$CHARTING_TO" \
    --limit "$COHORT_LIMIT" \
    --mode union \
    --order "$COHORT_ORDER" \
    --seed "$COHORT_SEED" \
    --output /tmp/charting_all_domain_codes.csv \
  | tee "$RUN_DIR/cohort_select.stdout"
```

Inspect `cohort_select.stdout` before continuing:

- `domain_errors` must be `{}`.
- `selected_count` must be greater than zero.
- No `domain_counts` value may equal `COHORT_LIMIT`; equality means the domain
  might be truncated and the run must be repeated with a higher limit.

Copy the selected cohort file out of the backend container:

```bash
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml cp backend:/tmp/charting_all_domain_codes.csv "$RUN_DIR/charting_all_domain_codes.csv"
```

Import patients into the scratch PMS DB so charting rows can map to PMS patient
IDs. This is a scratch DB write only.

```bash
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml exec -T -e R4_SQLSERVER_ENABLED=true -e R4_SQLSERVER_READONLY=true backend \
  python -m app.scripts.r4_import \
    --source sqlserver \
    --entity patients \
    --patient-codes-file /tmp/charting_all_domain_codes.csv \
    --apply \
    --confirm APPLY \
    --stats-out /tmp/charting_all_domain_patients_stats.json \
  | tee "$RUN_DIR/patients_apply.stdout"
```

Run the charting canonical dry-run after patient mappings exist. This reads R4
and the scratch DB but does not write PMS charting rows.

```bash
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml exec -T -e R4_SQLSERVER_ENABLED=true -e R4_SQLSERVER_READONLY=true backend \
  python -m app.scripts.r4_import \
    --source sqlserver \
    --entity charting_canonical \
    --dry-run \
    --patient-codes-file /tmp/charting_all_domain_codes.csv \
    --domains "$DOMAINS" \
    --charting-from "$CHARTING_FROM" \
    --charting-to "$CHARTING_TO" \
    --batch-size 50 \
    --run-summary-out /tmp/charting_all_domain_dryrun_summary.json \
    --output-json /tmp/charting_all_domain_dryrun_report.json \
  | tee "$RUN_DIR/charting_dryrun.stdout"
```

Apply charting canonical rows into the scratch PMS DB only:

```bash
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml exec -T -e R4_SQLSERVER_ENABLED=true -e R4_SQLSERVER_READONLY=true backend \
  python -m app.scripts.r4_import \
    --source sqlserver \
    --entity charting_canonical \
    --patient-codes-file /tmp/charting_all_domain_codes.csv \
    --domains "$DOMAINS" \
    --charting-from "$CHARTING_FROM" \
    --charting-to "$CHARTING_TO" \
    --batch-size 50 \
    --state-file /tmp/charting_all_domain_apply_state.json \
    --run-summary-out /tmp/charting_all_domain_apply_summary.json \
    --apply \
    --confirm APPLY \
    --stats-out /tmp/charting_all_domain_apply_stats.json \
    --output-json /tmp/charting_all_domain_apply_report.json \
  | tee "$RUN_DIR/charting_apply.stdout"
```

Rerun the same apply with a fresh state file to prove idempotency against the
scratch PMS DB:

```bash
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml exec -T -e R4_SQLSERVER_ENABLED=true -e R4_SQLSERVER_READONLY=true backend \
  python -m app.scripts.r4_import \
    --source sqlserver \
    --entity charting_canonical \
    --patient-codes-file /tmp/charting_all_domain_codes.csv \
    --domains "$DOMAINS" \
    --charting-from "$CHARTING_FROM" \
    --charting-to "$CHARTING_TO" \
    --batch-size 50 \
    --state-file /tmp/charting_all_domain_rerun_state.json \
    --run-summary-out /tmp/charting_all_domain_rerun_summary.json \
    --apply \
    --confirm APPLY \
    --stats-out /tmp/charting_all_domain_rerun_stats.json \
    --output-json /tmp/charting_all_domain_rerun_report.json \
  | tee "$RUN_DIR/charting_idempotency_rerun.stdout"
```

Run consolidated parity across the active domains:

```bash
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml exec -T -e R4_SQLSERVER_ENABLED=true -e R4_SQLSERVER_READONLY=true backend \
  python -m app.scripts.r4_parity_run \
    --patient-codes-file /tmp/charting_all_domain_codes.csv \
    --domains "$DOMAINS" \
    --date-from "$CHARTING_FROM" \
    --date-to "$CHARTING_TO" \
    --output-json /tmp/charting_all_domain_parity.json \
    --output-dir /tmp/charting_all_domain_parity_domains \
  | tee "$RUN_DIR/parity.stdout"
```

## Artefacts To Capture

Copy machine-readable artefacts out of the backend container:

```bash
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml cp backend:/tmp/charting_all_domain_patients_stats.json "$RUN_DIR/charting_all_domain_patients_stats.json"
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml cp backend:/tmp/charting_all_domain_dryrun_summary.json "$RUN_DIR/charting_all_domain_dryrun_summary.json"
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml cp backend:/tmp/charting_all_domain_dryrun_report.json "$RUN_DIR/charting_all_domain_dryrun_report.json"
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml cp backend:/tmp/charting_all_domain_apply_summary.json "$RUN_DIR/charting_all_domain_apply_summary.json"
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml cp backend:/tmp/charting_all_domain_apply_stats.json "$RUN_DIR/charting_all_domain_apply_stats.json"
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml cp backend:/tmp/charting_all_domain_apply_report.json "$RUN_DIR/charting_all_domain_apply_report.json"
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml cp backend:/tmp/charting_all_domain_rerun_summary.json "$RUN_DIR/charting_all_domain_rerun_summary.json"
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml cp backend:/tmp/charting_all_domain_rerun_stats.json "$RUN_DIR/charting_all_domain_rerun_stats.json"
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml cp backend:/tmp/charting_all_domain_rerun_report.json "$RUN_DIR/charting_all_domain_rerun_report.json"
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml cp backend:/tmp/charting_all_domain_parity.json "$RUN_DIR/charting_all_domain_parity.json"
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml cp backend:/tmp/charting_all_domain_parity_domains "$RUN_DIR/charting_all_domain_parity_domains"
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml ps > "$RUN_DIR/compose_ps_after.txt"
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml logs --no-color --tail=300 backend > "$RUN_DIR/backend_logs_tail.txt"
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml logs --no-color --tail=300 db > "$RUN_DIR/db_logs_tail.txt"
```

Capture final scratch row counts:

```bash
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml exec -T db sh -lc '
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "select count(*) from r4_patient_mappings;"
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "select domain, count(*) from r4_charting_canonical_records group by domain order by domain;"
' | tee "$RUN_DIR/scratch_counts_after.txt"
```

Minimum pass/fail evidence for the transcript:

- `cohort_select.stdout`: no `domain_errors`, nonzero `selected_count`, no
  `domain_counts` value at `COHORT_LIMIT`.
- `charting_all_domain_dryrun_report.json`: all requested domains represented;
  `unmapped_patients` is zero after patient import.
- `charting_all_domain_apply_stats.json`: `unmapped_patients_total` is zero.
- `charting_all_domain_rerun_stats.json`: no unexpected creates on the
  idempotency rerun.
- `charting_all_domain_parity.json`: `overall.status` is `pass`.
- `charting_all_domain_parity_domains/*.json`: per-domain pass/no-data/fail
  detail for the active 15 domains.

## Cleanup Or Reset

Preserve `$RUN_DIR` until the transcript is summarized. To reset the scratch PMS
target, tear down only the scratch project and its project-scoped volumes:

```bash
test "$COMPOSE_PROJECT_NAME" = "$SCRATCH_PROJECT"
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml down -v --remove-orphans
rm -f .env
```

After cleanup, confirm the long-lived default stack still exists separately and
that the scratch project is gone:

```bash
docker compose ls
docker ps --format '{{.Names}} {{.Ports}}'
```
