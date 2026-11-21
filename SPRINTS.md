# Creator Link Audit — Sprint plan

**Vision:** Give creators and small agencies a safe way to find monetization links needing attention, with the fewest manual actions possible. Independent repository and Docker stack.

## Sprint 0 — Local MVP (completed)
- [x] Independent login, organizations, scoped projects, source imports and initial scanning
- [x] Restricted DNS-pinned HTTP checking, Lychee offline extraction and exact affiliate parameters
- [x] Reports, CSV/print outputs, reviews and owner-approved retest
- [x] Local Compose with persistent SQLite and isolated backup verification
**Acceptance:** Core HTTP workflows and isolation tests passed in original MVP PRs; full production and browser QA remains outstanding.

## Sprint 1 — Better evidence and workflow (implemented; browser QA ongoing; synthetic project/report/CSV acceptance added in review)
- [x] Public YouTube description loading/import, saved previews and error recovery (merged)
- [x] Explain redirects and suspected wrong landing pages (merged)
- [x] Detect explicit Amazon product ID redirection mismatch (merged)
- [x] PR #14: Content-aware heuristics, unique-link prioritization and shared preview-confirm review; merged and CI verified
- [x] PR #15: Accessibility templates, discount-code register and migration integration merged with CI; browser visual validation remains in Sprint 2
**Acceptance:** Creator can view one ranked unique-link review queue; original affiliate URLs are never silently rewritten; full test suite, migration checks and LAN smoke pass.

## Sprint 2 — Reliability, security and standards (current parallel sprint)
- [x] Resolve default-branch CI failure (green main checks after PR #14/#16)
- [x] Align Django 5.2 LTS manifest and locked version (PR #17; CI verified)
- [x] Adopt central standards with verified badges, root Agile documents, Security and release policy (PR #16)
- [ ] Complete secure invitation/recovery/MFA delivery and admin browser QA. PR #19 blocks unsupported flows; authentication status and migrations are tested.
- [x] Consistent preview SQLite backup + disposable restore verified before 8043 upgrades; verified host export implementation in review, off-device backup remains P1 backlog
- [ ] Real browser mobile, keyboard, accessibility and print smoke tests (headless Chrome implementation in review; print report still needs representative scan fixture)
**Acceptance:** CI green on merged main, reproducible locked container build and documented rollback; no regression in project/customer isolation; application usable over trusted LAN.

## Sprint 3 — Time-saving pilot (current)
- [x] Group repeated exact original + tested URLs and prioritize evidence-backed actions (PR #14)
- [x] One-click tenant-scoped CSV action queue (PR #21, merged and tested)
- [x] Transparent repeated-appearance and manual-decision counts (PR #22); actual time savings and usefulness still require consent-based pilot measurement
- [ ] Trial with consenting creator or agency; collect willingness-to-pay feedback
**Acceptance:** Pilot can ingest authorized source descriptions, identify likely issues, and produce a readable action report with low repeated manual work.

## Sprint 4 — Production-readiness decision (planned)
- [ ] Choose appropriate app-level open-source license after owner decision; check dependencies
- [ ] Invitation/reset/MFA end-to-end security, documented retention and recovery
- [ ] Durable scan leasing and database scale plan if pilot demand warrants it
- [ ] Document hosting, pricing and support model before a public paid offering

After each sprint, record verified completion here, update BACKLOG.md, test evidence, and release notes; start the next ready backlog item rather than waiting at a sprint boundary.
