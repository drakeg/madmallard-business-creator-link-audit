# Creator Link Audit — safe backup and recovery

This is an **operator-only** procedure for the SQLite-based pilot. The app has a named Docker data volume, and backups contain password hashes, private creator descriptions, audit history, and commercial links. Do not commit, upload, or expose them in a public web directory.

## Recommended workflow — verified, no downtime

On the **Mac running Docker**, from this repository checkout:

```bash
mkdir -p "$HOME/Backups/madmallard-creator-link-audit"
chmod 700 "$HOME/Backups/madmallard-creator-link-audit"
python3 scripts/export_verified_backup.py \
  --container madmallard-creator-audit-preview-web \
  --destination "$HOME/Backups/madmallard-creator-link-audit"
```

This starts the application's SQLite online-backup command inside the running container, copies the consistent snapshot into a private host directory, compares SHA256, byte count and database row counts, **restores a copy into a disposable SQLite database**, then atomically publishes the verified snapshot. Existing filenames are never overwritten, and no live container/database is changed. It prints a JSON result including the destination and verification status; the password or private data is never printed.

For the main local Docker Compose stack, use the actual web container name from `docker compose ps` with `--container NAME`. The script does not assume that Compose or the preview is the only stack running.

**Important distinction:** `~/Backups` is outside the Docker volume, but it is **not off-device** on the same Mac. To survive Mac hardware/disk loss, explicitly use a *trusted, mounted external disk or secured NAS*, e.g. `--destination /Volumes/SecureBackup/CreatorAudit`; verify the mount is present and protected. No cloud account, paid storage, encryption, external mount or recurring job is configured automatically. Choose encrypted storage when storing sensitive customer data on removable/shared media. Keep encryption keys separately.

## Confirm and test a saved snapshot

For every exported snapshot, the script already checks the hash and tests a disposable restore. Periodically verify the backup on its destination device, rather than only trusting the original source:

```bash
python3 - <<'PY'
from pathlib import Path
from audit.backup import verify_restore
backup = Path("/path/to/verified/audit-TIMESTAMP.sqlite3")
print(verify_restore(backup))
PY
```

The reported `restore: passed` uses a temporary database and **never restores over the live application**. This also verifies foreign keys, SQLite integrity and key table counts. Confirm the backup file is regular and protected with permissions `0600` and its parent directory `0700`.

## Recovery to an isolated replacement stack

1. Keep the original Docker volume untouched. Do **not** use `docker compose down -v`, `rm -rf audit-data`, or replace `/data/audit.sqlite3` under a running web/worker process.
2. Verify the archived snapshot independently with the command above. Record its SHA256 and age. Ensure the replacement app code/schema is compatible with the source.
3. Create a *new* Compose project name and **new named volume**. Stop its web/worker containers before copying the verified backup into its empty volume.
4. Install a copy of the snapshot as the *new replacement volume's* database with `0600` permissions and ownership for the container's nonroot application UID. Never overwrite an existing populated database. Mount only that replacement volume into the replacement web/worker. Run `manage.py migrate --noinput` on that isolated replacement, then run `manage.py check`.
5. Launch the replacement stack on a distinct, trusted-LAN port and verify sign-in, customer/project isolation, existing source and audit history, CSV/print reports and worker job behavior. Inspect results before any cutover.
6. Keep the original volume and a verified backup for rollback; switch users only after the replacement passes and an operator explicitly authorizes the cutover.

These are recovery **steps**, not a script that overwrites live data. No production recovery time guarantee is established. The available restoration checks prove the backed-up database is internally consistent, not that every browser workflow has been exercised on separate hardware.

## Retention and security

Choose and document a backup schedule based on acceptable data loss. Before migrations, deployments or destructive admin actions, create and verify a backup. Periodically rotate backups only under an operator-approved retention policy; the exporter deliberately **never deletes** backups. Limit access, avoid shared network paths without access controls, and test backups on a physically separate device when available.

Keep application secrets (`.env`, `SECRET_KEY`) secure and separate from the SQLite archive. A backup of the database alone may not preserve every integration secret required to reproduce the environment. This local pilot has no automatic disaster recovery or validated RPO/RTO SLA.
