# R4 Appointment Core Promotion Scratch Runbook

This runbook proves guarded R4 appointment promotion into core
`appointments` in an isolated scratch PMS database only.

It is not a live/default DB promotion path:

- R4 access remains SQL Server SELECT-only.
- PMS writes are allowed only to a throwaway Compose project and a scratch/test
  Postgres database.
- The default `dental_pms` database must never be targeted.
- Normal appointment routes, importers, runtime, Docker, compose, frontend, and
  ops files are not changed.

## Scratch Setup

Run from a clean worktree based on the master commit under test.

```bash
cd /home/amir/dental-pms-appointment-core-promotion-scratch
git rev-parse HEAD
git rev-parse origin/master
git status --short
```

Create a unique scratch project, DB, ports, and artefact directory.

```bash
export SCRATCH_PROJECT="dentalpms_appt_core_apply_$(date +%Y%m%d_%H%M%S)"
export SCRATCH_DB="dental_pms_appointment_core_promotion_scratch"
export SCRATCH_POSTGRES_PORT="5554"
export SCRATCH_BACKEND_PORT="8214"
export SCRATCH_FRONTEND_PORT="3214"
export RUN_DIR=".run/appointment_core_promotion_${SCRATCH_PROJECT}"
mkdir -p "$RUN_DIR"
```

Create an untracked scratch `.env`. Keep R4 credentials in the local secret
file; R4 commands below explicitly set `R4_SQLSERVER_ENABLED=true` and
`R4_SQLSERVER_READONLY=true`.

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
SECRET_KEY=scratch-appointment-core-promotion-secret-32chars
JWT_SECRET=scratch-appointment-core-promotion-jwt-32chars
JWT_ALG=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=120
RESET_TOKEN_DEBUG=false
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=ScratchAdmin123!
FEATURE_CHARTING_VIEWER=false
ENABLE_TEST_ROUTES=false
NEXT_PUBLIC_FEATURE_CHARTING_VIEWER=0
NEXT_PUBLIC_API_BASE=/api
FRONTEND_BASE_URL=http://localhost:${SCRATCH_FRONTEND_PORT}
BACKEND_BASE_URL=http://localhost:${SCRATCH_BACKEND_PORT}
APP_BASE_URL=http://localhost:${SCRATCH_FRONTEND_PORT}
R4_SQLSERVER_ENABLED=false
R4_SQLSERVER_READONLY=true
EOF
```

Preflight the target before any container starts.

```bash
export COMPOSE_PROJECT_NAME="$SCRATCH_PROJECT"
bash ops/env_check.sh
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml config > "$RUN_DIR/compose_config.yml"
docker compose ls | tee "$RUN_DIR/compose_ls_before.txt"
docker ps --format '{{.Names}} {{.Ports}}' | tee "$RUN_DIR/docker_ps_before.txt"
for port in "$SCRATCH_POSTGRES_PORT" "$SCRATCH_BACKEND_PORT" "$SCRATCH_FRONTEND_PORT"; do
  if ss -ltn | awk '{print $4}' | grep -q ":${port}$"; then
    echo "Port ${port} is already in use; choose another scratch port."
    exit 1
  fi
done
test -r /home/amir/secrets/dental-pms-r4.env
rg -q '^R4_SQLSERVER_READONLY=true$' /home/amir/secrets/dental-pms-r4.env
```

Start only the scratch database and apply migrations.

```bash
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml up -d db
for attempt in $(seq 1 30); do
  if docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml exec -T db sh -lc 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'; then
    break
  fi
  sleep 2
done
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml run --rm --no-deps backend sh -lc 'python -m alembic upgrade head'
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml up -d backend
```

Confirm the DB target is scratch-only.

```bash
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml exec -T db sh -lc '
  test "$POSTGRES_DB" = "dental_pms_appointment_core_promotion_scratch"
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "select current_database();"
' | tee "$RUN_DIR/current_database_before_apply.txt"
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml exec -T backend sh -lc '
  case "$DATABASE_URL" in
    *"@db:5432/dental_pms_appointment_core_promotion_scratch") exit 0 ;;
    *) echo "Unexpected DATABASE_URL target"; exit 1 ;;
  esac
'
```

## Scratch Import And Dry-Run

Import supporting R4 users, patients, and appointment staging rows into the
scratch PMS database only.

```bash
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml exec -T -e R4_SQLSERVER_ENABLED=true -e R4_SQLSERVER_READONLY=true backend \
  python -m app.scripts.r4_import --source sqlserver --entity users --apply --confirm APPLY --stats-out /tmp/r4_users_stats.json \
  | tee "$RUN_DIR/r4_users_apply.stdout"
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml cp backend:/tmp/r4_users_stats.json "$RUN_DIR/r4_users_stats.json"

docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml exec -T -e R4_SQLSERVER_ENABLED=true -e R4_SQLSERVER_READONLY=true backend \
  python -m app.scripts.r4_import --source sqlserver --entity patients --apply --confirm APPLY --stats-out /tmp/r4_patients_stats.json \
  | tee "$RUN_DIR/r4_patients_apply.stdout"
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml cp backend:/tmp/r4_patients_stats.json "$RUN_DIR/r4_patients_stats.json"

docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml exec -T -e R4_SQLSERVER_ENABLED=true -e R4_SQLSERVER_READONLY=true backend \
  python -m app.scripts.r4_import --source sqlserver --entity appointments --apply --confirm APPLY --stats-out /tmp/r4_appointments_stats.json \
  | tee "$RUN_DIR/r4_appointments_apply.stdout"
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml cp backend:/tmp/r4_appointments_stats.json "$RUN_DIR/r4_appointments_stats.json"
```

Run the required no-core-write promotion dry-run report before guarded apply.

```bash
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml exec -T backend \
  python -m app.scripts.r4_appointment_promotion_dryrun \
    --cutover-date 2026-04-29 \
    --output-json /tmp/appointment_promotion_dryrun_report.json \
  | tee "$RUN_DIR/appointment_promotion_dryrun.stdout"
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml cp backend:/tmp/appointment_promotion_dryrun_report.json "$RUN_DIR/appointment_promotion_dryrun_report.json"
```

## Guarded Scratch Apply

The apply command refuses default/live databases, requires
`--confirm SCRATCH_APPLY`, validates the dry-run report, refuses unmapped
promote candidates, refuses unresolved clinicians when required, refuses
null-patient/deleted/manual-review/invalid-datetime/conflicting rows, and emits
JSON with before/after core appointment counts.

```bash
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml exec -T backend \
  python -m app.scripts.r4_appointment_core_promotion_apply \
    --dryrun-report-json /tmp/appointment_promotion_dryrun_report.json \
    --output-json /tmp/appointment_core_promotion_apply.json \
    --confirm SCRATCH_APPLY \
  | tee "$RUN_DIR/appointment_core_promotion_apply.stdout"
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml cp backend:/tmp/appointment_core_promotion_apply.json "$RUN_DIR/appointment_core_promotion_apply.json"
```

Run the guarded apply command again to prove idempotency by legacy ID.

```bash
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml exec -T backend \
  python -m app.scripts.r4_appointment_core_promotion_apply \
    --dryrun-report-json /tmp/appointment_promotion_dryrun_report.json \
    --output-json /tmp/appointment_core_promotion_apply_rerun.json \
    --confirm SCRATCH_APPLY \
  | tee "$RUN_DIR/appointment_core_promotion_apply_rerun.stdout"
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml cp backend:/tmp/appointment_core_promotion_apply_rerun.json "$RUN_DIR/appointment_core_promotion_apply_rerun.json"
```

Confirm scratch-only final counts.

```bash
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml exec -T db sh -lc '
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "select count(*) from r4_appointments;"
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "select count(*) from appointments;"
' | tee "$RUN_DIR/final_scratch_counts.txt"
```

## Cleanup

Preserve `$RUN_DIR` artefacts. Clean up only this scratch Compose project when
the transcript has been recorded and inspected.

```bash
test "$COMPOSE_PROJECT_NAME" = "$SCRATCH_PROJECT"
docker compose --env-file .env -f docker-compose.yml -f docker-compose.r4.yml down -v
```
