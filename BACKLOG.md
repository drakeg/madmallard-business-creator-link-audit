# Creator Link Audit — Prioritized backlog

| Priority | Item | Sprint | State / acceptance |
| --- | --- | --- | --- |
| P0 | Maintain green main CI and consistent Django 5.2 LTS manifest/lock | 2 | Completed in PRs #14, #16 and #17; ongoing validation in CI |
| P0 | Integrate PR #15 accessibility and explicit discount-code reviews | 2 | In review; confirm merged CI, tenant isolation and browser workflows |
| P0 | Merge PR #14 scoped auto-triage and shared unique-link reviews | 1 | Completed and verified in main |
| P0 | Adopt docs/badges/central validation and LAN Compose defaults | 2 | Completed in PR #16; ongoing maintenance required |
| P1 | Verify invitation/MFA/reset/admin features and safe migration path | 2 | Unverified; no production-user claims |
| P1 | Tested off-device backup and replacement-stack restoration | 2 | Open; recover and reopen scan report |
| P1 | Browser/mobile/keyboard/print accessibility | 2 | Open; no visual QA claim until executed |
| P1 | Unique-link review analytics with measured actions/time | 3 | Planned; consent-based metrics |
| P1 | Creator-facing concise actionable report | 3 | Planned; no fabricated product claims |
| P1 | First authorized creator/agency demo and $149 pilot hypothesis test | 3 | No customer validation yet |
| P2 | Versioned source edits and reversible suggested corrections | 4 | Planned |
| P2 | Durable worker recovery and PostgreSQL scale decision | 4 | Demand-dependent |
| P2 | Select application-level open-source license | 4 | Owner authorization needed; no license assumed |

See [docs/BACKLOG.md](docs/BACKLOG.md) for historical delivered work and unresolved technical tasks. Work through P0 issues first; after each PR merge, continue with the next ready task.

## Sprint 2 security discovery
- Self-service invitation, password reset and MFA interfaces existed without working delivery or second-factor verification; explicitly unavailable until secure implementations and end-to-end tests exist.
- Account status changes must synchronize the Django active-user flag; manual membership changes must never manufacture usernames or email addresses.
- Follow-up: implement secure single-use invitation flow, verified recovery delivery, enforced TOTP at login, repeated membership history, audit-event correctness and complete browser/admin templates before paid customer use.
