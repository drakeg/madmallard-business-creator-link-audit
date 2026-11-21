#!/usr/bin/env bash
# Ephemeral, offline-data browser acceptance in a CI runner; never use on an existing DB.
set -euo pipefail
if [[ "${CI:-}" != "true" || -z "${RUNNER_TEMP:-}" ]]; then
  echo "This browser acceptance runner is CI-only and requires RUNNER_TEMP" >&2
  exit 2
fi
command -v node >/dev/null
command -v python >/dev/null
command -v gunicorn >/dev/null
BROWSER=""
for candidate in google-chrome google-chrome-stable chromium chromium-browser; do
  if command -v "$candidate" >/dev/null 2>&1; then
    BROWSER="$(command -v "$candidate")"
    break
  fi
done
if [[ -z "$BROWSER" ]]; then
  echo "A local Chrome/Chromium installation is required on the CI runner" >&2
  exit 2
fi
workdir="$(mktemp -d "$RUNNER_TEMP/creator-browser-ci-XXXXXX")"
chmod 700 "$workdir"
server_pid=""
cleanup() {
  if [[ -n "$server_pid" ]]; then
    kill "$server_pid" >/dev/null 2>&1 || true
    wait "$server_pid" >/dev/null 2>&1 || true
  fi
  rm -rf -- "$workdir"
}
trap cleanup EXIT
export DB_PATH="$workdir/browser.sqlite3"
export ADMIN_USERNAME="ci-synthetic-admin"
export SECRET_KEY="$(python -c 'import secrets;print(secrets.token_urlsafe(48))')"
export ADMIN_PASSWORD="$(python -c 'import secrets;print(secrets.token_urlsafe(36))')"
export ALLOWED_HOSTS="localhost,127.0.0.1"
export AUDIT_ALLOW_SYNTHETIC_FIXTURES=1
export COOKIE_SECURE=false
python - "$workdir/credentials.env" <<'PY'
import os,sys
from pathlib import Path
p=Path(sys.argv[1])
p.write_text("ADMIN_USERNAME="+os.environ["ADMIN_USERNAME"]+"\nADMIN_PASSWORD="+os.environ["ADMIN_PASSWORD"]+"\n")
os.chmod(p,0o600)
PY
python manage.py migrate --noinput >/dev/null
python manage.py bootstrap >/dev/null
gunicorn config.wsgi:application --bind 127.0.0.1:8046 --workers 1 --threads 2 --timeout 60 --no-control-socket >"$workdir/server.log" 2>&1 &
server_pid=$!
ready="false"
for attempt in $(seq 1 40); do
  if curl --fail --silent --max-time 2 http://127.0.0.1:8046/health/ >/dev/null; then
    ready="true"
    break
  fi
  sleep .5
done
if [[ "$ready" != true ]]; then
  echo "CI browser server failed to become healthy:" >&2
  tail -35 "$workdir/server.log" >&2
  exit 1
fi
export AUDIT_BASE_URL="http://127.0.0.1:8046"
export AUDIT_CREDENTIALS_FILE="$workdir/credentials.env"
export AUDIT_FIXTURE_FILE="$workdir/fixture.json"
export CHROME_PATH="$BROWSER"
# First exercise the empty admin workspace before inserting any customer rows.
unset AUDIT_FIXTURE_FILE
if ! node scripts/browser_smoke.mjs; then
  echo "CI empty-workspace browser acceptance failed:" >&2
  tail -35 "$workdir/server.log" >&2
  exit 1
fi
# Only this newly created disposable database may receive synthetic scan data.
python manage.py seed_synthetic_browser_fixture --confirm-synthetic-only > "$workdir/fixture.json"
export AUDIT_FIXTURE_FILE="$workdir/fixture.json"
if ! node scripts/browser_smoke.mjs; then
  echo "CI Chrome acceptance failed; local app server log:" >&2
  tail -35 "$workdir/server.log" >&2
  exit 1
fi
