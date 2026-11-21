#!/usr/bin/env python3
"""Verify a portable Creator Link Audit backup inside a disposable, network-disabled Docker container.

Never connects to, overwrites, restarts, or mounts the live application volume.
Does not expose a port or print customer/account records. Requires a locally
available matching application image. The input backup is mounted read-only.
"""
import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
import time
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from audit.backup import inspect_database, read_only

SAFE_IMAGE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/:@-]{0,199}$")

# The SQLite copy is the *only* database the Django process ever opens.
# Docker has no host backup mount, network access or host port.
CONTAINER_CHECK = """
set -eu
cat > /tmp/restored.sqlite3
printf '%s  /tmp/restored.sqlite3\\n' "$EXPECTED_SHA256" | sha256sum -c - >/dev/null
python manage.py check >/dev/null
python manage.py makemigrations --check --dry-run >/dev/null
python manage.py migrate --check --noinput >/dev/null
python -c 'import os,sqlite3; c=sqlite3.connect(os.environ["DB_PATH"]); assert c.execute("PRAGMA integrity_check").fetchone()==("ok",); assert c.execute("PRAGMA foreign_key_check").fetchone() is None; print("RESTORED_APPLICATION_OK")'
"""


def digest_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_backup_input(backup, expected_sha256=None):
    path = Path(backup).expanduser().absolute()
    if path.is_symlink() or not path.is_file():
        raise ValueError("Backup must be an existing regular file, not a symlink")
    if path.stat().st_mode & 0o077:
        raise PermissionError("Backup must not be group/world readable (chmod 600)")
    if not path.stat().st_size:
        raise ValueError("Backup is empty")
    digest = digest_file(path)
    if expected_sha256 is not None:
        if not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):
            raise ValueError("Expected checksum must be 64 hex characters")
        if digest != expected_sha256.lower():
            raise ValueError("Backup SHA256 does not match expected checksum")
    with closing(read_only(path)) as db:
        counts = inspect_database(db)
    return path, digest, counts


def rehearse(backup, image, expected_sha256=None, command=subprocess.run):
    if not SAFE_IMAGE.fullmatch(image) or ".." in image:
        raise ValueError("Invalid Docker image reference")
    started = time.monotonic()
    path, digest, counts = verify_backup_input(backup, expected_sha256)
    args = [
        "docker", "run", "--rm", "-i",
        "--network", "none", "--read-only",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=128m",
        "--security-opt", "no-new-privileges",
        "--cap-drop", "ALL", "--pids-limit", "128", "--memory", "512m",
        "--env", "DB_PATH=/tmp/restored.sqlite3",
        "--env", "SECRET_KEY=offline-restore-verification-only-no-login",
        "--env", f"EXPECTED_SHA256={digest}",
        "--workdir", "/app", image, "sh", "-ec", CONTAINER_CHECK,
    ]
    # The chosen image must already exist locally; no network or image pull.
    image_check = command(
        ["docker", "image", "inspect", image], check=True,
        capture_output=True, text=True, timeout=120,
    )
    if not image_check.stdout.strip():
        raise ValueError("Docker image inspection returned no image metadata")
    # Stream file bytes to the unprivileged container; Linux runners cannot
    # necessarily bind-mount a mode-0600 file owned by a different UID.
    # No data is materialized in shell arguments or env variables.
    with path.open("rb") as stream:
        try:
            result = command(args, stdin=stream, check=True, capture_output=True, text=True, timeout=180)
        except subprocess.CalledProcessError as exc:
            # Keep diagnostic output bounded and do not print backup contents.
            detail = (exc.stderr or "")[-1200:]
            raise ValueError("Offline Django restore failed: " + detail) from exc
    if "RESTORED_APPLICATION_OK" not in result.stdout:
        raise ValueError("Isolated Django recovery did not confirm success")
    return {
        "result": "passed",
        "backup": str(path),
        "sha256": digest,
        "bytes": path.stat().st_size,
        "row_counts": counts,
        "application_image": image,
        "isolated_django_checks": "passed",
        "network_access": "disabled",
        "published_ports": 0,
        "live_data_modified": False,
        "elapsed_seconds": round(time.monotonic() - started, 2),
        "note": "Recovery rehearsal only; off-device storage and real RTO/RPO not established",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", required=True, help="Existing private exported SQLite backup")
    parser.add_argument("--image", required=True, help="Already-installed matching application image")
    parser.add_argument("--sha256", help="Optional expected checksum obtained separately")
    args = parser.parse_args()
    try:
        print(json.dumps(rehearse(args.backup, args.image, args.sha256), sort_keys=True))
        return 0
    except (OSError, ValueError, PermissionError, sqlite3.Error, subprocess.SubprocessError) as exc:
        print(f"Recovery rehearsal failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
