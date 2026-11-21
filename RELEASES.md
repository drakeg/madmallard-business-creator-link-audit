# Versioning and release policy

There is no verified application GitHub release or root application license at the time this file was created. This local pilot is pre-stable; do not claim it is a production-ready or public open-source release. Third-party license notices are not an application license.

Use SemVer when releases begin:
- **PATCH** for compatible bug/security fixes.
- **MINOR** for backward-compatible creator-facing functionality.
- **MAJOR** for incompatible API, data, authentication or workflow changes.

A PR merge alone does not require a release. A meaningful, tested milestone with verified compatibility, migration/rollback guidance, and user-visible notes does. Before tagging: ensure required CI and container build pass; test the LAN workflow and backups; check schema migrations and saved-volume restore; validate badges/license disclosures; update SPRINTS.md and BACKLOG.md; record defects and limitations.

## Unreleased — verified local pilot
- Read-only content-aware link inspection, explicit product-ID and missing-page signals, unique-link prioritization, exact-link shared reviews with confirmation (PR #14).
- Discount-code evidence register, accessibility improvements and browser-template compilation checks (PR #15); live visual/mobile accessibility QA outstanding.
- Central repository standards and accurate dynamic badges (PR #16); Django 5.2 LTS dependency lock consistency (PR #17).
- Incomplete invitation, password reset and MFA workflows explicitly unavailable; account disable enforced (PR #19). No production MFA or self-service recovery claims.
- Gunicorn 27.0.1 lock and verified Docker build (PR #20).
- Tenant-scoped, filtered, injection-safe unique-link action CSV with source/evidence context (PR #21).
- Duplicate occurrence and manual decision counts on Quick Review (PR #22). No measured time-saving claims.
- Renovate pinned to safe Django 5.2 LTS line until a tested major migration; obsolete Django 6 upgrade PR closed (PR #23).

**Local verification:** GitHub CI green on merged main; isolated Docker tests for review features and full application; trusted-LAN preview on port 8043 with image matching merged main; preview backup and restore verified. No full real-browser accessibility or customer pilot validation claimed.

No application release or public open-source license has been created.

- Unreleased (in review): host-side SQLite backup export with no-overwrite semantics, content integrity comparison, restore check, and non-destructive recovery instructions.

- Unreleased (in review): real-browser accessibility fix for heading contrast, semantic landmarks/cards, and reusable LAN smoke tests for desktop/mobile/print/keyboard.

- Unreleased: suppress Gunicorn 27 optional control-socket errors in read-only Docker runtime (no change to HTTP service).

- Unreleased (in review): isolated synthetic creator-report browser acceptance fixture and read-only Chrome checks for linked project, distinct affiliate IDs, action CSV and printable report.

- Unreleased (in review): network-isolated queued-scan/worker integration regressions covering unique-link deduplication, error handling and export/customer scoping.

- Unreleased (in review): automatic PR-time Chrome synthetic creator-workflow checks using random, ephemeral local-only credentials and database.

- Unreleased (in review): actionable first-run customer organization guidance, no dead-end project form, and valid account administration card markup.

- Unreleased (in review): bounded retry and diagnostics for intermittent headless Chrome startup on GitHub runners, without weakening browser assertions or sandbox.

- Unreleased (in review): administrator-assisted one-hour account recovery links using Django single-use tokens, CSRF-protected staff-only issuance, superuser guardrails, documented private delivery and no emailed reset claims.
