"""Local operator-only SQLite snapshots and isolated restore verification."""
import hashlib
import os
import sqlite3
import tempfile
import time
from contextlib import closing
from pathlib import Path

REQUIRED_TABLES = (
    "django_migrations", "auth_user", "audit_customer",
    "audit_customer_members", "audit_project", "audit_source",
    "audit_link", "audit_scan", "audit_result",
)

def read_only(path):
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise ValueError("Database file does not exist")
    return sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5)

def inspect_database(connection):
    integrity = connection.execute("PRAGMA integrity_check").fetchall()
    if integrity != [("ok",)]:
        raise ValueError("SQLite integrity check failed")
    tables = {r[0] for r in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    if not set(REQUIRED_TABLES).issubset(tables):
        raise ValueError("Not a complete Creator Link Audit database")
    if connection.execute("PRAGMA foreign_key_check").fetchone():
        raise ValueError("Foreign-key validation failed")
    # Table names are a fixed allowlist, never operator/customer input.
    return {name: connection.execute(
        f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
        for name in REQUIRED_TABLES}

def copy_snapshot(source, destination):
    deadline = time.monotonic() + 30
    def progress(status, remaining, total):
        if time.monotonic() > deadline:
            raise TimeoutError("Snapshot exceeded the 30-second copy deadline")
    source.backup(destination, pages=128, progress=progress, sleep=0.05)

def create_backup(source, destination):
    source = Path(source).expanduser().resolve()
    destination = Path(destination).expanduser().absolute()
    if source == destination.resolve():
        raise ValueError("Backup destination must differ from the live database")
    if not source.is_file():
        raise ValueError("Live database does not exist")
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Never overwrite an existing backup, symlink or live file.
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    try:
        with closing(read_only(source)) as live:
            with closing(sqlite3.connect(destination)) as snapshot:
                copy_snapshot(live, snapshot)
                snapshot.commit()
                rows = inspect_database(snapshot)
        with destination.open("rb") as backup_file:
            digest = hashlib.file_digest(backup_file, "sha256").hexdigest()
        return {"path": str(destination), "bytes": destination.stat().st_size,
                "sha256": digest, "integrity": "ok", "rows": rows}
    except BaseException:
        destination.unlink(missing_ok=True)
        raise

def verify_restore(backup):
    # Restore into a new temporary database, never into the live volume.
    with tempfile.TemporaryDirectory(prefix="creator-audit-restore-") as directory:
        restored_path = Path(directory) / "restored.sqlite3"
        with closing(read_only(backup)) as original:
            before = inspect_database(original)
            with closing(sqlite3.connect(restored_path)) as restored:
                copy_snapshot(original, restored)
                restored.commit()
                after = inspect_database(restored)
                if before != after:
                    raise ValueError("Restored database row counts differ")
        # Reopen from disk: this checks the persisted restore, not just the writer.
        with closing(read_only(restored_path)) as restored:
            if inspect_database(restored) != before:
                raise ValueError("Persisted restore differs from backup")
        return {"restore": "passed", "integrity": "ok", "rows": before,
                "live_database_modified": False}
