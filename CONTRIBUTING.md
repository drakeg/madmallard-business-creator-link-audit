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
