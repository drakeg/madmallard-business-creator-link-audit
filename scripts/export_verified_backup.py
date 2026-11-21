#!/usr/bin/env python3
"""Export and verify an atomic, read-only snapshot from a running Creator Link Audit container.

Writes outside the Docker volume to an explicitly chosen host directory.
Never overwrites files, stops containers, modifies live SQLite, or deletes backups.
"""
import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from audit.backup import inspect_database, read_only

DEFAULT_CONTAINER = "madmallard-creator-audit-preview-web"


def run_command(argv, timeout=120):
    return subprocess.run(argv, check=True, text=True, capture_output=True, timeout=timeout).stdout


def parse_metadata(output):
    data = json.loads(output.strip())
    path = data.get("path")
    if not isinstance(path, str) or not path.startswith("/data/backups/"):
        raise ValueError("Backup must be inside the container's /data/backups directory")
    name = Path(path).name
    if not (name.startswith("audit-") and name.endswith(".sqlite3") and name == path.split("/")[-1]):
        raise ValueError("Unexpected backup filename")
    if data.get("integrity") != "ok" or not isinstance(data.get("sha256"), str):
        raise ValueError("Container backup did not report verified integrity and SHA256")
    if len(data["sha256"]) != 64:
        raise ValueError("Invalid backup checksum")
    return data


def verify_host_copy(path, metadata):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Exported backup is not a regular file")
    if path.stat().st_size != metadata["bytes"]:
        raise ValueError("Backup size differs from container snapshot")
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
    digest = checksum.hexdigest()
    if digest != metadata["sha256"]:
        raise ValueError("SHA256 mismatch; exported backup is not identical")
    with closing(read_only(path)) as source:
        rows = inspect_database(source)
    if rows != metadata["rows"]:
        raise ValueError("SQLite row counts differ from source")
    # Actually restore into an ephemeral file, check on-disk consistency and FK integrity.
    with tempfile.TemporaryDirectory(prefix="creator-restore-") as tmp:
        restored = Path(tmp) / "restored.sqlite3"
        with closing(read_only(path)) as source:
            with closing(sqlite3.connect(restored)) as output:
                source.backup(output)
                output.commit()
        with closing(read_only(restored)) as check:
            if inspect_database(check) != rows:
                raise ValueError("Restored SQLite snapshot does not match")
    return {"integrity": "ok", "restore": "passed", "sha256": digest, "rows": rows}


def export_backup(destination_dir, container=DEFAULT_CONTAINER, command=run_command):
    if not container or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-" for ch in container):
        raise ValueError("Invalid Docker container name")
    directory = Path(destination_dir).expanduser().absolute()
    if directory.is_symlink():
        raise ValueError("Backup directory must not be a symlink")
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not directory.is_dir():
        raise ValueError("Backup destination must be a directory")
    # Avoid relaxing existing operator-set permissions; reject world/group access.
    if directory.stat().st_mode & 0o077:
        raise PermissionError("Backup directory must be private (chmod 700)")
    metadata = parse_metadata(command(["docker", "exec", container, "python", "manage.py", "backup_database"]))
    destination = directory / Path(metadata["path"]).name
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Backup exists; refusing overwrite: {destination}")
    fd, temporary = tempfile.mkstemp(prefix=".creator-copy-", suffix=".sqlite3", dir=directory)
    os.close(fd)
    temp_path = Path(temporary)
    try:
        command(["docker", "cp", f'{container}:{metadata["path"]}', str(temp_path)])
        temp_path.chmod(0o600)
        verification = verify_host_copy(temp_path, metadata)
        # Atomic no-replace hardlink: fails if the destination appears during copy.
        os.link(temp_path, destination)
        return {"destination": str(destination), "bytes": destination.stat().st_size,
                "container": container, "verification": verification,
                "note": "Host export is off-volume; off-device only if destination is external/NAS"}
    finally:
        temp_path.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", required=True, help="Private host folder (or mounted external/NAS location)")
    parser.add_argument("--container", default=DEFAULT_CONTAINER)
    args = parser.parse_args()
    try:
        print(json.dumps(export_backup(args.destination, args.container), sort_keys=True))
    except (OSError, ValueError, sqlite3.Error, subprocess.SubprocessError) as exc:
        print(f"Backup export failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
