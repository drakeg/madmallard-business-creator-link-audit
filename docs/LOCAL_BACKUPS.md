# Local database backups

These are manual operator commands for this standalone local app. No schedules or cloud
storage are created. SQLite's backup API produces a consistent snapshot while the app runs;
a raw copy of an actively written SQLite file is not an equivalent backup.

```sh
docker compose exec web python manage.py backup_database
```

The command prints JSON with the new snapshot path, SHA256, size, integrity status and
row counts. Default path: `/data/backups/audit-TIMESTAMP.sqlite3` in this app's volume.
An optional `--output /data/backups/my-pilot.sqlite3` selects a new filename. Existing files
and the live database cannot be overwritten. Backup files are created with mode 600.

Verify a snapshot by using its printed path:

```sh
docker compose exec web python manage.py verify_backup --input /data/backups/audit-TIMESTAMP.sqlite3
```

Verification restores it into a new temporary database, checks SQLite integrity, foreign
keys and required application tables, compares row counts, then reopens the restored file.
The temporary restore is removed afterward. Live data is never replaced by this command.
It does not modify scan state or run the scan worker against the restored copy.

Keep an additional local host copy if needed:

```sh
mkdir -p backups
chmod 700 backups
docker compose cp web:/data/backups/audit-TIMESTAMP.sqlite3 backups/audit-TIMESTAMP.sqlite3
chmod 600 backups/audit-TIMESTAMP.sqlite3
```

`backups/`, SQLite files and `.env` are excluded from Git and the image context. Backups
contain account password hashes, submitted content and report history. Preserve your
existing `.env` separately; the database snapshot does not contain SECRET_KEY or plaintext
bootstrap passwords. Copying to the same Mac does not protect against losing the Mac/disk.

The CLI intentionally offers no live overwrite/restore operation. For an actual recovery,
first verify the backup, preserve the current live database, stop only this app's web/worker,
and restore into a separate volume or test stack. Validate sign-in, customer scoping and
reports there before switching the live stack. Replacements are an explicit recovery action.

Evidence and remaining limits are in TESTING.md. These commands are not an automated retention,
encryption, off-device backup or disaster-recovery service; no recovery-time target is claimed.
