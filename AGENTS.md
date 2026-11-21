# Creator Link Audit working agreement
Keep changes on review branches. Do not commit customer data or secrets.
Read README.md and docs/BACKLOG.md. Preserve customer scoping on every object lookup,
write and export. All outbound connections must use audit.network; never add an
unrestricted fetch or a Lychee network mode. Keep original URLs and query values intact.
Do not publish changes, submit forms, invent codes, access accounts, spend money or deploy
cloud resources. Local Docker is authorized. Keep executed tests distinct from planned checks.
No delegation requirement. Document any production-readiness gaps honestly.

## Repository standards and continuous development
Follow drakeg/madmallard-repository-standards where compatible with the stricter local security requirements above. Maintain root SPRINTS.md, BACKLOG.md, CONTRIBUTING.md, RELEASES.md and SECURITY.md; retain docs/BACKLOG.md as historical detail. Use prioritized Sprint acceptance criteria and independent reviewable PRs. Do not invent paid demand, test outcomes, licenses or deployment status.

Badge maintenance: run central scripts/audit.py --check and scripts/badges.py --mode check (using the central repo checkout) whenever dependencies, supported platforms, workflows or releases change. Place badges directly below the root README H1, keep dynamic CI/activity indicators, verify version claims from lockfiles, and do not duplicate markers.

Development loop: Build → Deploy → Test → Fix → Redeploy → Continue within the authorized session. Prefer isolated Docker Compose stacks, LAN-accessible local test ports, preserved named volumes, targeted database backups before migration, and real workflow tests. Never expose local test HTTP outside the trusted LAN. Keep original URLs and affiliate tags immutable, and never automatically publish or rewrite creator content.

## Automated dependency updates
Renovate must not silently switch the project from Django 5.2 LTS to Django 6. A Django major upgrade needs explicit scope, new lockfile, migration compatibility work, security review, full CI and LAN/browser validation. For all Renovate PRs that change requirements.txt, update requirements.lock together before expecting the required lockfile check to pass. Keep CI's comparison fail-closed; don't suppress failures or assume PR readiness.

## Gunicorn 27 container safety
The application runs with a read-only root filesystem, so disable Gunicorn's optional local control socket by using `--no-control-socket` in its Docker command. This keeps serving HTTP without writing to the application user's home directory. Re-test the actual read-only container startup after any Gunicorn upgrade; do not remove `read_only`, `cap_drop`, or `no-new-privileges` to silence a control-server warning.

## Recovery rehearsal safety
Backup copies contain customer content and credentials. Keep local exports private
(mode 0600), use encrypted independent storage for real off-device backups, and
run `scripts/rehearse_offline_restore.py` in a network-disabled disposable
container. Never replace or wipe live volumes, open a recovery container to the
internet, publish an audit database, or auto-delete backups. See
`docs/DISASTER_RECOVERY.md`; distinguish a rehearsed SQLite/Django check from
a timed replacement-stack RTO/RPO.
