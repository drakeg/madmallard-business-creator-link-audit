# Verification record

## Executed on the connected Mac, November 16, 2026
- Docker Desktop arm64 Python 3.13 environment: initial 17 tests passed, then all 24 expanded Django tests passed inside the running application image.
- Tests cover cross-customer reads/writes/reviews/CSV/HTML exports/deletion; dashboard isolation;
  customer privilege boundaries; CSRF rejection; profile role protection; login lockout;
  escaped HTML, exact affiliate values, CSV ingestion, dump-only Lychee command selection;
  source locking and retest approval; required manual-verification notes.
- Network tests simulate public/private/mixed DNS, DNS-pinned TLS host connections,
  HTTP classifications/timeouts and a redirect to metadata blocked before a second connection.
  These use mocked DNS/transport; they are not live requests to private or metadata endpoints.

Final live-service and image checks are recorded below after execution. Not yet claimed:
real-browser/mobile/accessibility testing, AWS/EKS deployment, distributed load, production
backup restoration, full dependency vulnerability/SBOM review, affiliate attribution or actual
discount validity. No real creator accounts or YouTube access were used.

## Executed live-service checks
- Docker image built successfully on the Mac (arm64); Lychee reports 0.24.2. Release
  asset checksum verification passed during build. Real local-file dump succeeded in
  a container with networking disabled.
- Web health check passed, Gunicorn served the login page, and the persistent worker ran.
  Published mapping: 127.0.0.1:8042 → 8000, so access is Mac-only.
- `scripts/live_smoke.py` used actual HTTP, cookies and CSRF through the running service:
  administrator sign-in; customer/project creation; pasted source import; initial queue/worker
  completion; public HTTP success; metadata URL blocked; detailed 3-row CSV; printable HTML;
  saved manual review; approved retest with baseline comparison. Synthetic project is labeled
  clearly and retained for the owner to test. No private endpoint was contacted.
- `manage.py check` and migration drift check passed. `check --deploy` reported four expected
  local-HTTP warnings: no HSTS/HTTPS redirect and secure session/CSRF cookies disabled.
  They remain production configuration gates; local HTTP would not work with forced HTTPS.
- `pip-audit -r requirements.lock` reported **No known vulnerabilities found** on this date.
  This covers Python requirements against its advisory data, not Debian or Rust binary contents.

## Checks still planned
Actual browser click/keyboard/mobile/print rendering and an accessibility scan have not been
performed. Rendered HTML responses and form workflows passed HTTP/Django tests; visual and
cross-browser quality is not asserted as tested. No AWS/Kubernetes deployment or validation,
production load/recovery, full image SBOM, Rust/OS vulnerability inventory, backup/restore,
real commercial destination validation, discount verification or affiliate attribution tests
have been performed. Unit network cases are controlled simulations, not unsafe network probes.

## Local backup follow-up — November 16, 2026
- All 30 tests passed in the updated image, including the previous customer isolation and
  network-safety tests plus snapshot consistency, preserved source data/password hashes,
  mode-600 output, existing/live destination refusal, missing source, incomplete schema and
  corrupt backup handling. Migration drift check passed.
- Real operator backup_database and verify_backup commands passed against the local database.
  SQLite integrity/foreign keys and required-table row counts passed after temporary restore.
- A separate Django process used the restored temporary database to authenticate the existing
  administrator and open a saved report. The live database was never replaced.
- A mode-600 host copy was saved under ignored backups/. No backup data or credentials are
  committed; no schedules, off-device storage or cloud resources were created.
- Full replacement-volume recovery, disk-loss recovery and RPO/RTO remain untested. Prior
  browser/mobile visual QA limitations still apply.
