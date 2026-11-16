# Mad Mallard Solutions — Creator Link Audit

A local, private MVP for reviewing RV/travel creators’ product, sponsor and affiliate
links in older descriptions and blog posts. The $149 pilot is a price hypothesis;
no paid demand has been validated. No outreach, paid APIs, schedules or cloud deployment.

## Run locally
Requires Docker Desktop with Compose. Clone this private repository, copy `.env.example`
to `.env`, set a random SECRET_KEY (32+ chars) and unique ADMIN_PASSWORD (16+ chars), then:

```sh
docker compose up -d --build
docker compose ps
```

Open http://localhost:8042. Default bind is **Mac-only** (`127.0.0.1`). Ports are configurable.
For LAN access deliberately set BIND_ADDRESS=0.0.0.0 and add the Mac’s LAN IP/hostname to
ALLOWED_HOSTS, then recreate this stack. Do not expose plain HTTP to the internet. Use TLS
and secure cookies for any hosted deployment. No existing applications or volumes need
be stopped. The dedicated named volume persists through container rebuilds. Do not use
`docker compose down -v` unless you intend to destroy all app data.

On the initial installed Mac, a mode-600 `local-access.txt` contains the login details.
It and `.env` are ignored by Git and excluded from the Docker build context. Changing
ADMIN_PASSWORD after bootstrap does not reset an existing user: use Profile → Change
password, or a deliberate `manage.py changepassword USER` operation.

## YouTube channel URLs

Use **Import from YouTube channel** inside a project to load public descriptions through
the official API. Public metadata needs an independent YouTube Data API v3 key; no Google
account sign-in or OAuth is used. See [setup, retention and limits](docs/YOUTUBE_IMPORT.md).

## Use the workbench
1. Sign in as the administrator. Create a customer organization and a customer account.
   Each customer belongs to its assigned organization; staff administrators see all.
2. Create a project. Paste content, upload UTF-8 Markdown/HTML, or CSV with `title,content`
   and optional `original_url,discount_codes`. One CSV row is one source. Select only one
   input method. Confirm ownership/permission. Public retrieval is opt-in, one text/HTML
   page per submission; no crawl, login, browser or access bypass is performed.
3. Queue the initial scan. A separate persistent worker checks deduplicated target URLs;
   every source-link association gets its own result. Progress auto-refreshes every five
   seconds. Original content/links become immutable after the first queued scan.
4. Filter by category, manual status, source or URL. Open a review dialog to record evidence,
   notes and a proposed replacement. A maximum of 10 distinct source-link reviews is
   included; editing a review does not consume another slot. Discount-code verification
   must name the code and evidence in notes. No checkout or form is submitted by the tool.
5. After the owner approves corrections, queue the one included retest. Explicitly opt in
   to checking saved proposed URLs; otherwise the original URLs are rechecked. Targets are
   snapshotted at enqueue time. Original URLs/affiliate IDs remain unchanged. Compare with
   the initial category/status; both attempts retain full HTTP evidence.
6. Download the detailed CSV or open Printable HTML to print/save PDF/download a standalone
   HTML report. Exports always contain the full scan, regardless of on-screen filters.
7. Select individual or multiple history entries, review the selection and type DELETE.
   Deletion removes scan results and their review snapshots, preserving sources and current
   link notes. Deleting a baseline removes its retest reference; deleting history resets
   the project’s scan-count allowance. This is a workbench limit, not billing enforcement.

## Interpretation
- **broken:** only HTTP 404/410, evidence at check time. Human confirmation is still useful.
- **access_blocked:** HTTP 401/403. Could be authentication or bot protection; not broken.
- **rate_limited / timeout / network_error / server_error:** inconclusive, keep separate.
- **destination_review:** a 2xx response; verify intended product and commercial terms.
- **unsafe_blocked:** request/redirect rejected before connecting to the unsafe destination.
- **http_review:** unexpected responses needing a human decision.

Never treat a successful HTTP response as proof of commission attribution, product identity,
stock or discount validity. Soft 404s, CAPTCHA pages that return 200, tracking in JavaScript,
geo restrictions, link expiry, canonical changes and product substitutions require manual
review. Suspected affiliate query parts are a heuristic, kept with exact encoded values,
order and duplicates; absence of detected parameters does not mean absence of affiliation.
HTML entities in hrefs are decoded to the actual navigable URL; raw source is retained.
Discount codes are owner-supplied and default to unverified. No codes are invented.

## Architecture & safety
Python 3.13 + current Django 5.2 LTS patch + urllib3 + Gunicorn; pinned in requirements.lock.
Independent Django auth (PBKDF2 passwords, CSRF, server sessions), no private auth copied from
other projects. Membership checks apply to project reads/writes, reports, reviews and exports.
SQLite schema migrations and a dedicated persistent volume; one worker. Scan queue is capped
at 10 outstanding jobs. Settings cap sources at 20, unique URLs at 100, concurrency at 10,
timeout at 30 seconds per hop and retries at 3 (defaults 4/10/1). Operator changes go in .env.

Public HTTP/HTTPS only, ports 80/443, no URL credentials or environment proxies. All DNS answers
must be public; each hop connects to the validated IP with the original TLS hostname and Host.
Private/reserved/loopback/link-local/metadata and translated IPv6 destinations are blocked,
including redirects. Redirect limit is eight. No private-network allowlist is enabled in this
MVP. Public retrieval is limited to 1 MB; no cookies, account headers, JavaScript, form submissions
or video downloads. Public DNS lookup duration depends on the container resolver; configured
socket timeouts are per hop and are not a hard whole-job deadline. Enforce infrastructure
egress limits before internet-facing deployment as defense in depth.

Lychee 0.24.2 is invoked in **local dump-only mode only** to process local source files.
The Python transport performs network checking so every redirect is independently validated
and pinned, with exact per-hop evidence. Lychee never fetches user-selected remote inputs here.
See [dependency review](docs/DEPENDENCIES.md) and [notices](THIRD_PARTY_NOTICES.md).

## Verify
```sh
docker compose exec web python manage.py check
docker compose exec web python manage.py makemigrations --check --dry-run
docker compose exec web python manage.py test audit -v 2
```
See [test evidence](docs/TESTING.md) for executed results and their limits, and
[backlog](docs/BACKLOG.md). [Cloud preparation](deploy/README.md) includes ECR/ECS and EKS
skeletons only: nothing deployed, no AWS account connection assumed.

## Operational limitations
Local pilot only: no password recovery/invitations, MFA, account suspension UI, organization
membership editor, billing, retention scheduler, malware scanning or production backup service.
Login throttling is persistent per IP+username; it is a baseline, not distributed abuse protection.
YouTube import is public metadata only; no scraping, link/affiliate ID replacement or publication.
Markdown/HTML extraction targets outbound HTTP(S) links, not every custom syntax; relative HTML
anchors need an original source URL. Large JavaScript-heavy pages are not rendered. A successful
public fetch is not a statement about reuse rights: only submit authorized sources.

Worker restarts mark running scans interrupted and retain partial evidence. You can delete an
interrupted history and rerun; this is not a distributed exactly-once queue. SQLite is appropriate
for this single-host pilot, not multi-replica cloud scaling. Back up with SQLite’s backup API (or
stop only this stack and copy the volume); use the operator commands in [local backup instructions](docs/LOCAL_BACKUPS.md).
