#!/usr/bin/env bash
set -euo pipefail

ROOT="$HOME/dental-pms"
cd "$ROOT"

if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi

APP_ENV="${APP_ENV:-}"
ALLOW_DEV_SEED="${ALLOW_DEV_SEED:-0}"
if [ "$APP_ENV" != "development" ] && [ "$ALLOW_DEV_SEED" != "1" ]; then
  echo "Refusing to seed recalls: set APP_ENV=development or ALLOW_DEV_SEED=1"
  exit 1
fi

DB_USER=$(docker compose exec -T db sh -lc 'echo ${POSTGRES_USER:-}')
DB_NAME=$(docker compose exec -T db sh -lc 'echo ${POSTGRES_DB:-}')
if [ -z "$DB_USER" ] || [ -z "$DB_NAME" ]; then
  echo "Unable to determine POSTGRES_USER/POSTGRES_DB from db container" >&2
  exit 1
fi

cat <<'SQL' | docker compose exec -T db sh -lc "psql -U \"$DB_USER\" -d \"$DB_NAME\""
\set ON_ERROR_STOP on

-- Clear previous seeded data
DELETE FROM patient_recall_communications
WHERE recall_id IN (
  SELECT id FROM patient_recalls WHERE notes LIKE 'seed:%'
);
DELETE FROM patient_recalls WHERE notes LIKE 'seed:%';

WITH admin AS (
  SELECT id AS user_id FROM users ORDER BY id LIMIT 1
), seed_patients AS (
  SELECT id AS patient_id, row_number() OVER (ORDER BY id DESC) AS rn
  FROM patients
  WHERE deleted_at IS NULL
  ORDER BY id DESC
  LIMIT 10
)
INSERT INTO patient_recalls (
  patient_id,
  kind,
  due_date,
  status,
  notes,
  completed_at,
  created_by_user_id,
  updated_by_user_id
)
SELECT
  sp.patient_id,
  CASE (sp.rn % 5)
    WHEN 1 THEN 'exam'
    WHEN 2 THEN 'hygiene'
    WHEN 3 THEN 'perio'
    WHEN 4 THEN 'implant'
    ELSE 'custom'
  END::patient_recall_kind,
  (CURRENT_DATE + ((sp.rn - 3) * 7))::date,
  CASE (sp.rn % 4)
    WHEN 1 THEN 'upcoming'
    WHEN 2 THEN 'due'
    WHEN 3 THEN 'overdue'
    ELSE 'completed'
  END::patient_recall_status,
  'seed: recall ' || sp.rn,
  CASE WHEN (sp.rn % 4) = 0 THEN NOW() ELSE NULL END,
  admin.user_id,
  admin.user_id
FROM seed_patients sp
CROSS JOIN admin;

WITH admin AS (
  SELECT id AS user_id FROM users ORDER BY id LIMIT 1
), seeded AS (
  SELECT id AS recall_id, patient_id, row_number() OVER (ORDER BY id) AS rn
  FROM patient_recalls
  WHERE notes LIKE 'seed:%'
)
INSERT INTO patient_recall_communications (
  patient_id,
  recall_id,
  channel,
  direction,
  status,
  notes,
  other_detail,
  outcome,
  contacted_at,
  created_by_user_id
)
SELECT
  s.patient_id,
  s.recall_id,
  CASE WHEN gs.n = 1 THEN 'phone'
       WHEN (s.rn % 3) = 0 THEN 'email'
       WHEN (s.rn % 3) = 1 THEN 'sms'
       ELSE 'other'
  END::patient_recall_comm_channel,
  'outbound'::patient_recall_comm_direction,
  'sent'::patient_recall_comm_status,
  'seed: comm ' || gs.n,
  CASE WHEN gs.n = 2 AND (s.rn % 3) = 2 THEN 'WhatsApp' ELSE NULL END,
  CASE WHEN gs.n = 1 THEN 'left voicemail' ELSE NULL END,
  NOW() - ((s.rn + gs.n) * INTERVAL '2 days'),
  admin.user_id
FROM seeded s
CROSS JOIN admin
CROSS JOIN generate_series(1, 2) AS gs(n);

SELECT
  (SELECT COUNT(*) FROM patient_recalls WHERE notes LIKE 'seed:%') AS seeded_recalls,
  (SELECT COUNT(*) FROM patient_recall_communications WHERE notes LIKE 'seed:%') AS seeded_comms;
SQL

echo "Seeded dev recalls and communications."
