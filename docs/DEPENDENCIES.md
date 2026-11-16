# Dependency review — November 16, 2026

Checked the live upstream GitHub release, README, release-tag license files and Cargo
manifests before integrating Lychee. Latest stable observed: `lychee-v0.24.2`.
Sources:
- https://github.com/lycheeverse/lychee/releases/tag/lychee-v0.24.2
- https://github.com/lycheeverse/lychee/blob/lychee-v0.24.2/LICENSE-MIT
- https://github.com/lycheeverse/lychee/blob/lychee-v0.24.2/LICENSE-APACHE
- https://github.com/lycheeverse/lychee/blob/master/lychee-bin/Cargo.toml
- https://github.com/lycheeverse/lychee/blob/lychee-v0.24.2/lychee.example.toml

Capabilities verified from upstream: asynchronous URL checking, Markdown/HTML inputs,
local local link dumping, redirects, retries, timeouts, concurrency and structured reports.
Its CLI is MIT OR Apache-2.0; elect MIT, retain notices and credit. Commercial use is allowed
under those terms; no paid API is required. It does not prove affiliate attribution or code validity.

Current source manifest reports Rust edition 2024 and minimum Rust 1.89.0. This image does
not compile Rust: it uses the matching upstream musl Linux release for arm64/amd64, verifies
its SHA256 against the upstream release checksum, and requires CA certificates for HTTPS.
The Python app invokes it only with a local source file and `--dump`; outbound
network checks use the app’s pinned-IP transport for consistent redirect safety/evidence.
The binary's `--version`, real local dump extraction and the container build are integration
checks; mocked unit tests alone do not establish those capabilities.

Python dependencies resolved from PyPI on the Mac into `requirements.lock`: Django 5.2.19
(current patch in the supported LTS line), urllib3 2.8.0, Gunicorn 25.3.0, asgiref 3.13.0,
sqlparse 0.6.1 and packaging 26.3. Package metadata and installed license texts were inspected
and saved. These are permissive BSD/MIT/Apache terms, with notice requirements; see notices.
No other project’s authentication implementation or private package was copied.

Complete image security scanning, a complete image SBOM, Rust-transitive/OS license inventory,
image signing and automated update policy remain production gates. Version resolution and
unit tests are not a claim that every dependency is vulnerability-free.
