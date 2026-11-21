# Creator Link Audit — Prioritized backlog

| Priority | Item | Sprint | State / acceptance |
| --- | --- | --- | --- |
| P0 | Maintain green main CI and consistent Django 5.2 LTS manifest/lock | 2 | Completed in PRs #14, #16 and #17; ongoing validation in CI |
| P0 | Integrate PR #15 accessibility and explicit discount-code reviews | 2 | Merged with green CI; visual/mobile browser QA remains P1 |
| P0 | Merge PR #14 scoped auto-triage and shared unique-link reviews | 1 | Completed and verified in main |
| P0 | Adopt docs/badges/central validation and LAN Compose defaults | 2 | Completed in PR #16; ongoing maintenance required |
| P1 | Verify invitation/MFA/reset/admin features and safe migration path | 2 | Unverified; no production-user claims |
| P1 | Secure host snapshot export and external-device recovery | 2 | Operator-controlled host export with SHA256/isolated restore is in review; actual external-device/whole-stack restore still outstanding |
| P1 | Browser/mobile/keyboard/print accessibility | 2 | Open; no visual QA claim until executed |
| P1 | Unique-link review workload indicators | 3 | Implemented in PR #22; actual time-savings measurement requires pilot evidence |
| P1 | Creator-facing concise actionable report | 3 | One-click grouped CSV action list in PR #21, merged; full evidence report retained |
| P1 | First authorized creator/agency demo and $149 pilot hypothesis test | 3 | No customer validation yet |
| P2 | Versioned source edits and reversible suggested corrections | 4 | Planned |
| P2 | Durable worker recovery and PostgreSQL scale decision | 4 | Demand-dependent |
| P2 | Select application-level open-source license | 4 | Owner authorization needed; no license assumed |

See [docs/BACKLOG.md](docs/BACKLOG.md) for historical delivered work and unresolved technical tasks. Work through P0 issues first; after each PR merge, continue with the next ready task.

## Sprint 2 security discovery
- Self-service invitation, password reset and MFA interfaces existed without working delivery or second-factor verification; explicitly unavailable until secure implementations and end-to-end tests exist.
- Account status changes must synchronize the Django active-user flag; manual membership changes must never manufacture usernames or email addresses.
- Follow-up: implement secure single-use invitation flow, verified recovery delivery, enforced TOTP at login, repeated membership history, audit-event correctness and complete browser/admin templates before paid customer use.

- Completed P0: PR #20 aligned Gunicorn 27.0.1 lock with its manifest and passed Docker/CI tests; future dependency PRs must update both files.

## Sprint 3 — action queue export (implemented)
- One-click, tenant-scoped CSV with **one row per exact original + tested URL**, affected source titles, evidence summary, suggested creator action, manual status/notes, original affiliate parameters, and review URL.
- Filter the export by the same attention/review bucket shown on the page; preserve original affiliate URLs and apply CSV injection escaping to fields. No external publication or state changes.
- Success criterion: a creator can hand off a compact actionable list without manually copying duplicates; record measured usage only after a real pilot.

- Sprint 3 follow-up: show transparent counts of duplicate appearances consolidated and unique-link groups with any recorded manual decision. Do not claim measured time saved, final review completion, or customer results without evidence.
- Dependency housekeeping: Renovate can suggest patch/minor releases within the verified Django 5.2 LTS line; major Django 6 must have an independent planned migration and pinned lock update. Keep locked dependency and declared constraints consistent in PRs.

## Next authorized priorities
- Complete the LAN web/browser keyboard, mobile, focus, print and export workflow acceptance tests on realistic non-sensitive fixtures.
- Add off-device encrypted backup/retention instructions and a documented restore exercise, with no automatic deletion of existing data.
- Trial the no-publication action export with a consenting creator and measure actual reviews avoided, time and willingness to pay. No prior demand validation is assumed; product coding continues regardless.

## Backup implementation (Sprint 2 hardening)
- Added a no-overwrite host export command using the application's SQLite online snapshot and isolated restore verification. It deliberately never changes live data or cleans old files.
- A Mac host folder is off-volume **not** off-device; an external encrypted drive or secured NAS and a replacement-stack browser recovery exercise remain pending.

## Real-browser accessibility QA (Sprint 2, in review)
- Fixed headings that previously rendered white on light paper; Chrome confirmed the existing failure and corrected contrast at 11.23:1 on login/dashboard/profile.
- Corrected duplicate main landmark on login, malformed profile/dashboard card sections, and dead `/contact/` account-request link.
- Added no-dependency Chrome CDP smoke for desktop/mobile authenticated pages, skip-link keyboard access, print header CSS and overflow checks. Needs CI verification and representative scan/report browser fixture later.

## Gunicorn 27 read-only runtime compatibility
- Observed Gunicorn 27 attempting to create its optional control socket under non-writable /home/audit/.gunicorn in Docker. App HTTP remained responsive, but emitted an ERROR at startup. Dockerfile now disables this optional interface; the application server still runs with read-only root filesystem and drops all Linux capabilities.

## Sprint 3 — synthetic full-report browser acceptance

- In progress: explicit synthetic-only, empty-database fixture command for deterministic completed scan evidence, three source uses, two unique affiliate URLs and a private QA volume.
- Extend authenticated Chrome smoke to verify the project, Quick Review deduplication, CSV export preserving exact affiliate IDs, and printable evidence report, including mobile layout and print-header behavior.
- Still outstanding: automated scan-worker network tests with controlled local HTTP fixtures, real customer consent-based evaluation, full keyboard/screen-reader audit.

## Sprint 3 — worker/database integration regression

- In review: integration tests post a real scan request, run the actual persistent worker loop, stub only outbound HTTP (no internet), and assert one request per unique exact URL, correct result fanout across three sources, distinct affiliate IDs, report CSV/print and cross-customer 404s.
- Also verify unexpected checker failures are recorded as failed scans while preserving original content. This is a controlled network simulation, not a claim about real merchant availability or successful commission tracking.

## Sprint 3 — automated browser acceptance in CI
- Introduce an ephemeral local-only synthetic fixture server and Chrome run in GitHub Actions. Each run uses random test administrator credentials, a temporary SQLite database, and simulated completed scan evidence, so it cannot read or modify production creator data.
- Check sign-in, mobile dashboard/project/Quick Review, exact-affiliate-URL deduplication, CSV export, print layouts, contrast, landmarks and keyboard skip link on every PR.

## First-run organization onboarding — P1 UI refinement

- In review: show the exact first action when an administrator has no customer organization, instead of displaying an unusable Create Project form with an empty required select.
- Give customer users with no assigned organizations a clear administrator-contact instruction. Restore the project creation form immediately when membership/customer access exists.
- Correct previously malformed organization-admin card markup and add real desktop/mobile Chrome smoke coverage.

- Extend browser CI to verify the zero-organization state before the synthetic fixture is seeded, then repeat the populated project/report flow. No customer records outside the ephemeral runner.

## CI Chrome startup reliability
- In review: recent Renovate GitHub Actions runs showed intermittent `Chrome did not start its debugging endpoint` failures on Ubuntu runners while other runs passed. Add isolated startup retries with bounded wait and diagnostic Chrome stderr, retain browser sandbox, and never ignore content/contrast assertions.

## Sprint 2 — administrator-assisted account recovery (in review)
- Admins may issue an expiring, single-use-on-password-change reset link for an active account; no SMTP/email integration is claimed. Staff can only reset staff accounts when acting as a superuser. A new signed-out user can choose a new password using Django's validated SetPasswordForm.
- Record issuance in the existing admin action log without persisting the token; require POST/CSRF and no-store responses. Normal self-service email reset and MFA remain unavailable pending enforced delivery/second factor.
- This local pilot uses plaintext HTTP on a trusted LAN. **Require HTTPS before publicly sharing reset links or accepting production customers.**
