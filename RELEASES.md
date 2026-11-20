# Versioning and release policy

There is no verified application GitHub release or root application license at the time this file was created. This local pilot is pre-stable; do not claim it is a production-ready or public open-source release. Third-party license notices are not an application license.

Use SemVer when releases begin:
- **PATCH** for compatible bug/security fixes.
- **MINOR** for backward-compatible creator-facing functionality.
- **MAJOR** for incompatible API, data, authentication or workflow changes.

A PR merge alone does not require a release. A meaningful, tested milestone with verified compatibility, migration/rollback guidance, and user-visible notes does. Before tagging: ensure required CI and container build pass; test the LAN workflow and backups; check schema migrations and saved-volume restore; validate badges/license disclosures; update SPRINTS.md and BACKLOG.md; record defects and limitations.

## Unreleased
- Consolidated creator link outcome explanations and product-identifier hints.
- In review: content-aware automated triage and exact-link shared review flow (PR #14).
- In review: accessibility improvements (PR #15).
- Under development: central standards adoption and dependency/CI alignment.

No release has been created by this documentation change.

- Unreleased security hardening: incomplete invitation/reset/MFA flows now return an explicit unavailable response instead of promising protection or generating unusable credentials; account status enforcement tightened.

- Unreleased dependency repair: lock Gunicorn 27.0.1 to match the accepted 27.x requirement; verify WSGI startup and HTTP behavior before local promotion.

- Unreleased (pending review): optional filtered CSV action queue, deduplicated by exact original + tested URL while preserving affiliate parameters and source coverage. No product guarantees.

- Unreleased (in review): transparent unique-link review progress and duplicate-appearance workload counts, explicitly not a measured time-saving claim.
