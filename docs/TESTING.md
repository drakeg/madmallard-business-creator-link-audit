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

## YouTube channel import follow-up — November 16, 2026
- All 52 tests passed in the updated Docker image, including official API request/URL
  normalization, header-only key handling, sanitized errors, user/project preview isolation,
  paging tokens, selected-description import, atomic limits, permission/CSRF checks, exact
  encoded affiliate values, duplicate prevention, source locking, expiry and confirmed deletion.
- Migration creation and drift checks passed; the existing local data was backed up before
  migration. The actual Mad Mallards Adventures project import page and missing-key setup
  flow returned successfully with the supplied handle prefilled.
- Running-image fixture workflow exercised preview/import with synthetic API metadata and
  actual Lychee extraction. It preserved description content, watch URL, video ID, expiry
  and exact query values. Only its temporary synthetic project was removed.
- No live YouTube channel catalogue was retrieved: this app has no API key configured.
  A real channel import/audit, live quota/error behavior and browser/mobile visual QA remain
  unverified. API fixtures must not be described as live YouTube validation. No Google
  account authorization, cloud deployment, new schedules or cross-app integration occurred.

## YouTube load-feedback fix — November 16, 2026
- Investigated the reported blank-feedback behavior: existing API-created local previews
  contained 50 Mad Mallards Adventures videos. The previous page rendered them below setup
  and did not restore a preview on a normal return to the project. No API key was retrieved.
- Added results-first rendering, explicit loaded/empty/error states, progress and validation
  notices, selection controls, success redirects anchored to results, and restoration of the
  newest unexpired preview scoped to the same user/project without new API requests.
- All 59 server/integration tests passed in the rebuilt image, including seven regressions
  for visible result order, safe redirects, refresh/return behavior, isolation, expiry,
  loading markup, empty results and failure feedback.
- No live API retry was needed: the user's existing preview was used for local verification.
  Actual browser execution/visual QA of the loading script remains unverified because the
  local-browser connector was unavailable. Server HTML/form behavior is separately tested.

- Actual LAN HTTP verification after redeploy: sign-in and ordinary GETs for projects 3
  and 5 restored each existing 50-video preview above the API-key form. No key was
  re-entered/retrieved and no YouTube API retry was made. Frontend script syntax passed
  Node --check; this is not a browser execution test.

## Dedicated results navigation follow-up — November 16, 2026
- Added separate loaded-video and imported-description pages, stable result URLs,
  project-top return links, saved-page history, and safe bookmarked-page login returns.
  Successful loading/importing redirects to the appropriate dedicated page.
- Saved lists are retained for 29 days from retrieval. Existing unexpired lists were
  migrated using their original 30-minute expiration to recover the retrieval timestamp.
  Late imports cannot extend API-derived data beyond the saved list's expiry.
- All 69 tests passed in the rebuilt image, covering result navigation, customer isolation,
  safe login redirects, correct post-import redirects, retention, expiry and prior checks.
  Migration drift check passed; live data was backed up before migration.
- Actual LAN HTTP checks passed for projects 3 and 5: project return links, dedicated
  50-video pages, imported-description pages, and login returning to bookmarked results.
  Existing video lists were preserved and their displayed expiry was verified.
- No API key was accessed and no additional YouTube API calls were required. Browser
  visual/click execution remains unverified; these were server and HTTP checks.

## Reported import HTTP 500 — November 16, 2026
- Confirmed an HTTP 500 in the live access log, but the old logging configuration had not
  retained its Django traceback. The original failure was not reproduced; the exact cause
  is therefore not established. All 50 stored descriptions extracted successfully during
  diagnosis, and a 20-video import succeeded in a disposable database copy before the fix.
- Added bounded helper execution and visible fallback extraction warnings, malformed-markup
  recovery, import failure references and server traceback logging with DEBUG disabled.
  Existing transaction/duplicate guards remain in place; keys/POST bodies are not logged.
- All 78 tests passed, including timeout/missing/nonzero helper recovery, batch-budget expiry,
  warning deduplication, malformed markup, rollback on database failure and safe unexpected
  error handling, plus the prior isolation/navigation/network/backup checks.
- After deployment, two independent disposable copies of the real local database completed
  CSRF-protected, URL-encoded imports of 20 stored video descriptions: normal extraction,
  and injected Lychee timeouts. Both reached the imported-description page; the timeout
  run showed its fallback warning and preserved URL data. Copies were removed afterward.
- Live source/report data remained unchanged; a backup was taken before deployment. No
  YouTube API calls or external writes were needed. This does not claim that the user's
  exact original selection/error was reproduced or that a real browser click was tested.
