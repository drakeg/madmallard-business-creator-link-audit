# Security and supported environments

This application handles creator content, accounts and commercial links. Do not post live credentials, private customer data or vulnerability details in public issues. Contact the repository maintainer privately for responsible disclosure. No guaranteed production support/version line is established; the current local pilot is the only actively tested target.

- Restrict test HTTP endpoints to a trusted private LAN and host firewall; never port-forward to the internet. Use TLS, secure cookies and production-grade auth for external access.
- Do not disable private/reserved IP checks, DNS pinning, redirects validation, request bounds or tenant authorization to make a link pass.
- Keep original source text, affiliate IDs and query values unchanged. Proposed replacements require explicit owner review.
- Secret files stay outside Git and images; account creation and YouTube imports must never expose keys in logs.
- Use locked, supported dependencies; test runtime upgrades and validate software supply-chain/licensing before a paid or public deployment.
- Back up persistent SQLite safely before migrations, verify a restored copy, and document rollback.
- Manual browser checks and affiliate attribution remain necessary for ambiguous cases. Never automatically submit forms, publish descriptions or purchase products.
