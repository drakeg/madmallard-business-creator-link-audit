# Practical backlog

## MVP acceptance (implemented; verification evidence in TESTING.md)
- Independent username/password auth, admin/customer provisioning and profile/password edits.
- Customer organizations and server-scoped project/read/write/review/export/delete operations.
- Paste, CSV/Markdown/HTML, explicitly authorized public-page input; source-link provenance.
- Lychee local dump extraction and restricted pinned-IP HTTP/redirect checking.
- Immutable scan evidence, queue/progress, categories, exact affiliate query parts.
- Manual reviews with evidence notes, proposed URLs and explicit approved retest comparison.
- Dashboard/history filters, review dialogs, detailed CSV/standalone printable HTML.
- Confirmed individual/bulk history deletion, persistent data, committed migrations.
- Isolated local Compose, configurable ports/limits; undeployed cloud skeletons and notices.

## Local follow-up completed
- Manual consistent SQLite backup and isolated restore-verification commands. Thirty tests passed;
  real snapshot integrity, table counts, restored sign-in and report access verified on the Mac.
  Live data was not overwritten. Backups stay local; no schedules created.

## Next: before accepting production customer data
P1: End-to-end real-browser accessibility/mobile audit and cross-browser printable report QA.
P1: Off-device backup, actual replacement-stack recovery exercise and documented RPO/RTO; data retention/export policy.
P1: Invitations/reset, MFA, account disable/membership edit and admin action audit trail.
P1: Stronger global/per-IP throttles, whole-job deadline, DNS timeout and egress firewall tests.
P1: PostgreSQL migration, durable job leasing and graceful restart recovery before scaling.
P1: Validate ECS/EKS manifests against actual target versions and security policies, without
    deploying until separately authorized. Full image SBOM/OS+Rust dependency license audit.
P2: Source revision model so corrected descriptions can stay in the same project with full history.
P2: Explicit discount-code entities and per-code evidence; review counting by unique commercial URL.
P2: More robust Markdown reference/autolink extraction and customer-facing clean report templates.
Implemented: public YouTube channel URL import through official list APIs, key setup,
  per-user/project previews, selected-description import, pagination and retention/deletion.
  Live channel import requires an app-specific API key; private-video OAuth remains future work.
P2: Validate $149 demand through owner-approved pilot activity; outreach is not authorized here.

## Local usability fix
- YouTube load results now appear before setup, with a visible count and selection controls.
  Returning to a project restores its current user-scoped preview; success redirects to
  results and empty/error/loading states are explicit. Regression tests included.

- Dedicated Loaded videos / Imported descriptions pages and prominent project return
  links now separate import stages from scan reports. Lists survive navigation for 29 days;
  saved-page links and safe bookmark login returns are covered by regression tests.

- Import resilience: bounded supplemental extraction, explicit fallback warnings, rollback
  regression tests, safe error references and production-mode error logging. Exact root
  cause of the historical unreproduced 500 remains unknown; future references are logged.
