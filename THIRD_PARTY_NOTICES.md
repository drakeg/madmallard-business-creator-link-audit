# Third-party notices

This proprietary application is © 2026 Mad Mallard Solutions. No open-source grant
for the application itself is implied. Third-party components retain their own terms.

## Lychee
Lychee 0.24.2, copyright (c) 2022 The lychee maintainers.
https://github.com/lycheeverse/lychee — dual Apache-2.0 OR MIT. This distribution elects
the MIT option. Full unmodified MIT and Apache license texts are included under
`third_party/lychee/`; the user interface credits Lychee in every page footer.

MIT permits use, modification, distribution, sublicensing and sale, with the copyright
and permission notice retained. It provides no warranty. No proprietary edition, API
subscription, account or commercial-use purchase is required for this CLI integration.

## Python packages
License texts copied from the actual installed distributions are preserved under
`third_party/python/`. See `docs/dependency-metadata.json` for exact version/license evidence.
- Django / asgiref: BSD-3-Clause.
- urllib3 / Gunicorn: MIT.
- sqlparse: BSD (see included LICENSE).
- packaging: Apache-2.0 OR BSD-2-Clause; elect BSD-2-Clause for this distribution.

These permissive terms permit commercial use, subject to their notices and disclaimers.
No paid Python dependencies or APIs are used. Python and Debian base-image license/copyright
files remain in the container. A complete Rust transitive and OS redistribution SBOM/license
review remains a pre-production task; this is not a blanket legal clearance of every binary
component. Do not remove the upstream notices when redistributing images.
