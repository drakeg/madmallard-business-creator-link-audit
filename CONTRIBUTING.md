# Contributing to Creator Link Audit

Follow [AGENTS.md](AGENTS.md), the [sprint plan](SPRINTS.md), [backlog](BACKLOG.md), and [security rules](SECURITY.md). This repository remains independent from other Mad Mallard applications. Contributions should target creator time saved, correctness, safety or pilot validation.

Use review branches and PRs with the changed behavior, issue/sprint, tests run, remaining risks, migration/rollback instructions and screenshots for UI changes. Prioritize urgent CI/security fixes; otherwise assign work to the current sprint.

## Local validation
From the repository root, using the app's isolated test Compose stack:
```sh
docker compose config
docker compose exec web python manage.py check
docker compose exec web python manage.py makemigrations --check --dry-run
docker compose exec web python manage.py test audit -v 2
```
When practical, test with a separate ephemeral test database and disable external network access. Never run test fixture migrations against the persistent customer/test database by accident. Preserve `.env`, credentials and named volumes. Avoid `docker compose down -v`.

Run the central toolkit's `scripts/audit.py --check` and `scripts/badges.py --mode check` against this checkout after updating README technologies, workflows, licenses or releases. Do not duplicate badge markers or claim passing status with static shields.

**Ready:** a scoped creator pain point, acceptance criterion, impact, risks and test plan. **Done:** code and documentation updated, safety preserved, verified tests and CI pass, data migrations and rollback documented, and PR reviewed under repository protections. For breaking changes document version impact in RELEASES.md.


## Real-browser LAN smoke test

With Node.js 22+, Chrome installed on the Mac, and a **separate trusted-LAN test stack** (do not test with real customer records):

```sh
AUDIT_BASE_URL=http://LAN-IP:8045 AUDIT_CREDENTIALS_FILE="$HOME/.config/madmallard-creator-audit-preview/access.env" node scripts/browser_smoke.mjs
```

The test creates and deletes an isolated Chrome profile; checks contrast, horizontal overflow, main landmarks, form CSRF markup, keyboard navigation to the skip link, authenticated desktop/mobile views and print layout. It only navigates pages and signs in. It does not mutate creator data or print passwords. Set `CHROME_PATH` to the local Chrome executable if needed. Do not expose Chrome's ephemeral debugging port to the LAN.

## Synthetic creator workflow browser QA (isolated database only)

Run the fixture on a **new, empty named Docker volume** and a separate test server port.
Use the existing browser smoke script with `AUDIT_FIXTURE_FILE` pointing to the JSON
emitted by `manage.py seed_synthetic_browser_fixture --confirm-synthetic-only`.
This fixture requires `AUDIT_ALLOW_SYNTHETIC_FIXTURES=1` in the isolated environment
and refuses any database containing a customer, project, source, or scan.
It creates three synthetic link uses with two distinct affiliate parameters and
a completed **simulated** scan; no public requests, real scan jobs, customer input,
third-party content, or writes to the main preview are involved.

The expanded browser smoke covers the signed-in project, unique-link review,
CSV action export, affiliate parameter isolation, and the printable audit report.
It never clicks buttons that write data. Do not run the fixture command against
port 8042, port 8043, or an existing customer database. Prefer a new disposable
volume for each run, preserve it for inspection until the QA is complete, and
remove it only after the operator confirms it contains no needed records.

## Worker integration test without public network

The `audit.test_worker_e2e` tests use Django's real scan queue and worker
command but stub outbound link checks. The suite requires no public network
and does not exercise merchant content or attribution. To reproduce in a
development container, run `python manage.py test audit.test_worker_e2e`.
Do not run the production worker against a test database shared with real creators.

## Continuous browser acceptance
The GitHub Test MVP workflow runs `scripts/run_ci_browser_smoke.sh` in an ephemeral, isolated runner. It requires `CI=true`, a private `RUNNER_TEMP` directory, installed Chrome, Python/Gunicorn and Node 22. It generates a throwaway administrator password and SQLite database, seeds synthetic scan records, serves localhost only, runs the same browser checks as local LAN QA, then removes temporary files. Run it only on a disposable CI runner, never against a populated customer database.

The CI browser runner also checks the first-run state **before** adding the synthetic customer, ensuring a new admin is guided to create their first organization and never sees an unusable empty project form. Afterward it seeds the disposable fixture and repeats browser acceptance with a populated project.

The Chrome smoke retries browser startup up to twice using separate temporary profiles on slow CI machines and reports Chrome stderr on an unrecoverable startup failure. A successful startup never suppresses page, authorization or accessibility assertions. Do not solve a sandbox error by disabling Chrome's security model.

## Administrator-assisted recovery
Administrators can issue one-hour Django password recovery links from the existing account directory. This is **manual delivery**, not an email feature. Issuance is audited (not the secret token), POST/CSRF-protected and restricted: only superusers can issue links for staff accounts. Links stop working after the target password changes. Never log, paste in public tickets or send them over untrusted connections; the current LAN HTTP pilot requires HTTPS before public/customer deployment. Email reset and MFA remain disabled. Test with `python manage.py test audit.test_admin_recovery`.

## Off-device recovery
See `docs/DISASTER_RECOVERY.md` for an encrypted external-storage export, offline
container restore rehearsal and a non-destructive replacement-stack plan. The
rehearsal script requires an existing private backup file and locally installed
matching Docker image. It does not require network access or expose ports.

GitHub CI additionally runs `scripts/run_ci_restore_rehearsal.sh` after building the application image. It generates an empty synthetic migrated SQLite database under the temporary runner directory, passes the offline Docker recovery script, then removes the data. It requires `CI=true` and must never be run on live customer data.
