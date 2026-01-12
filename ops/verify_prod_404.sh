#!/usr/bin/env bash
set -euo pipefail

ROOT="$HOME/dental-pms"
cd "$ROOT"

PORT="${PORT:-3110}"
ADMIN_EMAIL="${ADMIN_EMAIL:-}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-}"

if [ -z "$ADMIN_EMAIL" ] && [ -f .env ]; then
  ADMIN_EMAIL=$(grep -E '^ADMIN_EMAIL=' .env | cut -d= -f2- || true)
fi
if [ -z "$ADMIN_PASSWORD" ] && [ -f .env ]; then
  ADMIN_PASSWORD=$(grep -E '^ADMIN_PASSWORD=' .env | cut -d= -f2- || true)
fi
if [ -z "$ADMIN_EMAIL" ] || [ -z "$ADMIN_PASSWORD" ]; then
  echo "Missing ADMIN_EMAIL/ADMIN_PASSWORD for prod 404 verification."
  exit 1
fi

echo "Running production 404 verification inside a frontend container..."
docker compose run --rm --no-deps -e ADMIN_EMAIL -e ADMIN_PASSWORD frontend bash -lc "
set -euo pipefail

PORT=\"${PORT}\"
LOG_FILE=/tmp/next3110.log
PID_FILE=/tmp/next3110.pid
STATUS_JS=/tmp/next_http_status.js
READY_JS=/tmp/next_http_ready.js
LOGIN_JS=/tmp/next_login_token.js

cat > \"\$STATUS_JS\" <<'JS'
const http = require(\"http\");
const url = process.argv[2];
const token = process.argv[3];
const headers = token
  ? {
      Cookie: \"dental_pms_token=\" + encodeURIComponent(token),
      Authorization: \"Bearer \" + token,
    }
  : {};
http.get(url, { headers }, (res) => {
  res.resume();
  console.log(res.statusCode || 0);
}).on(\"error\", () => process.exit(2));
JS

cat > \"\$READY_JS\" <<'JS'
const http = require(\"http\");
const url = process.argv[2];
const token = process.argv[3];
const headers = token
  ? {
      Cookie: \"dental_pms_token=\" + encodeURIComponent(token),
      Authorization: \"Bearer \" + token,
    }
  : {};
http.get(url, { headers }, (res) => {
  res.resume();
  process.exit(res.statusCode ? 0 : 1);
}).on(\"error\", () => process.exit(1));
JS

cat > \"\$LOGIN_JS\" <<'JS'
const http = require(\"http\");
const email = process.argv[2];
const password = process.argv[3];
const payload = JSON.stringify({ email, password });
const req = http.request(
  {
    hostname: \"backend\",
    port: 8000,
    path: \"/auth/login\",
    method: \"POST\",
    headers: {
      \"Content-Type\": \"application/json\",
      \"Content-Length\": Buffer.byteLength(payload),
    },
  },
  (res) => {
    let body = \"\";
    res.on(\"data\", (chunk) => (body += chunk));
    res.on(\"end\", () => {
      if (res.statusCode !== 200) {
        process.exit(2);
      }
      try {
        const data = JSON.parse(body || \"{}\");
        const token = data.access_token || data.accessToken || \"\";
        if (!token) process.exit(3);
        process.stdout.write(token);
      } catch {
        process.exit(4);
      }
    });
  }
);
req.on(\"error\", () => process.exit(5));
req.write(payload);
req.end();
JS

status_code() {
  node \"\$STATUS_JS\" \"\$1\" \"\$2\"
}

ready_check() {
  node \"\$READY_JS\" \"\$1\" \"\$2\"
}

cleanup() {
  if [ -f \"\$PID_FILE\" ]; then
    pid=\$(cat \"\$PID_FILE\" 2>/dev/null || true)
    if [ -n \"\$pid\" ] && kill -0 \"\$pid\" 2>/dev/null; then
      kill \"\$pid\" >/dev/null 2>&1 || true
      wait \"\$pid\" 2>/dev/null || true
    fi
  fi
}

dump_log_and_exit() {
  echo \"--- next start log (tail) ---\"
  tail -200 \"\$LOG_FILE\" || true
  exit 1
}

trap cleanup EXIT

echo \"Building frontend for production...\"
NODE_ENV=production npm run build

TOKEN=\$(node \"\$LOGIN_JS\" \"\$ADMIN_EMAIL\" \"\$ADMIN_PASSWORD\" || true)
if [ -z \"\$TOKEN\" ]; then
  echo \"Failed to obtain auth token for prod 404 checks.\"
  dump_log_and_exit
fi

echo \"Starting production server on port \$PORT...\"
NODE_ENV=production PORT=\"\$PORT\" npm run start >\"\$LOG_FILE\" 2>&1 &
echo \"\$!\" > \"\$PID_FILE\"

for i in \$(seq 1 30); do
  if ready_check \"http://127.0.0.1:\$PORT/\" \"\$TOKEN\"; then
    ready=1
    break
  fi
  if ! kill -0 \"\$(cat \"\$PID_FILE\")\" 2>/dev/null; then
    echo \"Server process exited before readiness.\"
    dump_log_and_exit
  fi
  sleep 0.2
done

if [ \"\${ready:-0}\" != \"1\" ]; then
  echo \"Server not ready after wait.\"
  dump_log_and_exit
fi

status_ok=\$(status_code \"http://127.0.0.1:\$PORT/patients/5\" \"\$TOKEN\") || dump_log_and_exit
status_missing=\$(status_code \"http://127.0.0.1:\$PORT/patients/99999999\" \"\$TOKEN\") || dump_log_and_exit
status_missing_clinical=\$(status_code \"http://127.0.0.1:\$PORT/patients/99999999/clinical\" \"\$TOKEN\") || dump_log_and_exit

echo \"HTTP /patients/5 -> \$status_ok\"
echo \"HTTP /patients/99999999 -> \$status_missing\"
echo \"HTTP /patients/99999999/clinical -> \$status_missing_clinical\"

if [ \"\$status_ok\" != \"200\" ]; then
  echo \"Expected 200 for /patients/5\"
  dump_log_and_exit
fi
if [ \"\$status_missing\" != \"404\" ]; then
  echo \"Expected 404 for /patients/99999999\"
  dump_log_and_exit
fi
if [ \"\$status_missing_clinical\" != \"404\" ]; then
  echo \"Expected 404 for /patients/99999999/clinical\"
  dump_log_and_exit
fi
"
