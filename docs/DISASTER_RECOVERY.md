# Creator Link Audit — off-device backup and recovery rehearsal

This is an **operator-controlled** process for the independent SQLite deployment.
It does not authorize publishing the database, deleting old backups or overwriting
a running data volume. A backup contains password hashes, source content,
merchant links and other customer information: protect it accordingly.

## Copy to a physically independent location

1. Attach an **encrypted, unlocked external disk** (prefer APFS Encrypted on
   macOS) or a secured, access-controlled encrypted NAS share. Confirm its real
   mounted path and free space with `df -h "/Volumes/YourEncryptedDrive"`.
   FileVault protection of the Mac's internal disk alone is **not** an off-device backup.
2. Create a private folder on that mount, for example:
   `mkdir -m 700 "/Volumes/YourEncryptedDrive/CreatorAuditBackups"`.
   Confirm ownership and mode. Do not export to a publicly shared folder.
3. From the repository checkout (with Docker running), export a *new* snapshot:
   ```sh
   python3 scripts/export_verified_backup.py \
     --container madmallard-creator-audit-preview-web \
     --destination "/Volumes/YourEncryptedDrive/CreatorAuditBackups"
   ```
   This command creates a new file, verifies integrity and SHA-256, and does
   an isolated SQLite restore. It refuses to overwrite any existing export.
4. Safely eject and store the encrypted disk separately from the Mac, or verify
   the encrypted NAS has independent storage and a separate failure domain.
   Never assume a host folder under `~/Backups` is off-device.

## Verify recoverability from the exported file

Use the exact reported SHA-256 digest and an **already installed matching image**.
The script requires the exported backup file to be mode 0600. No ports are exposed.

```sh
python3 scripts/rehearse_offline_restore.py \
  --backup "/Volumes/YourEncryptedDrive/CreatorAuditBackups/audit-YYYYMMDDTHHMMSSffffffZ.sqlite3" \
  --image "madmallard-creator-link-audit:bcb95e7" \
  --sha256 "SHA256_FROM_EXPORT"
```

CI also runs `scripts/run_ci_restore_rehearsal.sh` after the image build using an
ephemeral migrated SQLite fixture and the same script; it does not contain
customer data or substitute for testing a real external-disk restore.

The rehearsal verifies the supplied backup locally and then starts a disposable
**network-disabled, read-only, capability-dropped Docker container**, copies the
backup to writable temporary storage, and runs the real Django system,
migration-state and database integrity checks. It cannot start the worker,
publish a port or touch the production named volume. The original backup
remains on the host and is streamed as bytes; it is never bind-mounted. A failed migration check means the backup and chosen
image may not be compatible—use the image matching the snapshot or investigate
in a second isolated environment rather than migrating production.

Record the printed elapsed time and result after each recovery exercise.
This is a technical **rehearsal duration**, not a measured full disaster-recovery
RTO. Restore time, credentials, DNS, LAN firewall and connected services must
also be tested before asserting operational RTO.

## Actual replacement stack (manual, consequential action)

If the Mac fails, use a fresh machine and the matching repository/image and
an independent, explicitly named **new Docker volume**. Copy the known-good
database into that volume while all destination application services are stopped,
verify ownership and migrations, and only then start the replacement stack with
new local environment secrets. Do **not** mount or overwrite the original
`madmallard-creator-audit-preview-data` volume; preserve the old state
until the replacement has been verified and the operator approves cutover.
Do not start the replacement on a public interface or connect external integrations
until access controls and credentials have been reviewed.

The exact cutover and validated recovery time remain outstanding. Do not
claim off-device protection without a verified encrypted external mount,
or claim the original password can be restored from a plaintext backup:
only the stored password hash is recoverable.

## Retention and objectives

- Suggested initial hypothesis: **daily** backup plus **before upgrades**,
  with at least one encrypted copy on a separate device. No schedule has been
  created and the storage location and retention period require operator choice.
- Recovery point objective (RPO): **not verified** until actual backup frequency
  and maximum tolerated data loss are agreed and measured.
- Recovery time objective (RTO): **not verified** until full replacement stack
  recovery has been timed. Do not substitute the offline rehearsal duration.
- Confirm restorability regularly on a separate machine. Never automatically
  delete snapshots or retention history without an approved policy.
- Backups containing creator content may be regulated by customer agreements;
  agree on retention and deletion before a paid pilot.
