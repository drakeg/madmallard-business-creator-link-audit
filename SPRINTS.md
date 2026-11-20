# Creator Link Audit — Sprint plan

**Vision:** Give creators and small agencies a safe way to find monetization links needing attention, with the fewest manual actions possible. Independent repository and Docker stack.

## Sprint 0 — Local MVP (completed)
- [x] Independent login, organizations, scoped projects, source imports and initial scanning
- [x] Restricted DNS-pinned HTTP checking, Lychee offline extraction and exact affiliate parameters
- [x] Reports, CSV/print outputs, reviews and owner-approved retest
- [x] Local Compose with persistent SQLite and isolated backup verification
**Acceptance:** Core HTTP workflows and isolation tests passed in original MVP PRs; full production and browser QA remains outstanding.

## Sprint 1 — Better evidence and workflow (in review)
- [x] Public YouTube description loading/import, saved previews and error recovery (merged)
- [x] Explain redirects and suspected wrong landing pages (merged)
- [x] Detect explicit Amazon product ID redirection mismatch (merged)
- [ ] PR #14: Content-aware heuristics, unique-link prioritization and shared preview-confirm review; merge only on passing checks
- [ ] PR #15: Accessibility, discount-code register and migration integration; verify merged CI and browser workflows
**Acceptance:** Creator can view one ranked unique-link review queue; original affiliate URLs are never silently rewritten; full test suite, migration checks and LAN smoke pass.

## Sprint 2 — Reliability, security and standards (current parallel sprint)
- [x] Resolve default-branch CI failure (green main checks after PR #14/#16)
- [x] Align Django 5.2 LTS manifest and locked version (PR #17; CI verified)
- [ ] Adopt central standards with verified badges, root Agile documents, Security and release policy
- [ ] Validate account invitation/MFA/administration behavior and migrations before customer data
- [ ] Confirm persistent backup and replacement-stack restore exercise
- [ ] Real browser mobile, keyboard, accessibility and print-report smoke tests
**Acceptance:** CI green on merged main, reproducible locked container build and documented rollback; no regression in project/customer isolation; application usable over trusted LAN.

## Sprint 3 — Time-saving pilot (next)
- [ ] Group common exact links across imported sources and offer evidence-driven action queue
- [ ] Add one-click scoped exports that highlight recommended creator action and evidence
- [ ] Measure unique URLs, repeated occurrences, review-time savings and export usefulness without inventing values
- [ ] Trial with consenting creator or agency; collect willingness-to-pay feedback
**Acceptance:** Pilot can ingest authorized source descriptions, identify likely issues, and produce a readable action report with low repeated manual work.

## Sprint 4 — Production-readiness decision (planned)
- [ ] Choose appropriate app-level open-source license after owner decision; check dependencies
- [ ] Invitation/reset/MFA end-to-end security, documented retention and recovery
- [ ] Durable scan leasing and database scale plan if pilot demand warrants it
- [ ] Document hosting, pricing and support model before a public paid offering

After each sprint, record verified completion here, update BACKLOG.md, test evidence, and release notes; start the next ready backlog item rather than waiting at a sprint boundary.
