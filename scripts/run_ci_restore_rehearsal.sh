#!/usr/bin/env bash
# This runs only on a disposable CI runner, never an operator's existing database.
set -euo pipefail
if [[ "${CI:-}" != "true" || -z "${RUNNER_TEMP:-}" ]]; then
  echo "CI restore rehearsal requires CI=true and RUNNER_TEMP" >&2
  exit 2
fi
umask 077
workdir="$(mktemp -d "$RUNNER_TEMP/creator-restore-ci-XXXXXX")"
trap 'rm -rf -- "$workdir"' EXIT
export DB_PATH="$workdir/fixture.sqlite3"
export SECRET_KEY="ci-recovery-test-only-long-unguessable-not-for-users"
python manage.py migrate --noinput >/dev/null
chmod 600 "$DB_PATH"
python scripts/rehearse_offline_restore.py --backup "$DB_PATH" --image audit:test
