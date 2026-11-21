import json
import hashlib
import os
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from audit.backup import REQUIRED_TABLES
from export_verified_backup import export_backup, parse_metadata, verify_host_copy


class VerifiedHostBackupTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.original = self.root / "live.sqlite3"
        self.snapshot = self.root / "source.sqlite3"
        with sqlite3.connect(self.original) as db:
            for table in REQUIRED_TABLES:
                db.execute(f'CREATE TABLE "{table}" (id INTEGER PRIMARY KEY, value TEXT)')
            db.execute("INSERT INTO auth_user VALUES (1, 'test-password-hash')")
            db.commit()
        with sqlite3.connect(self.original) as source:
            with sqlite3.connect(self.snapshot) as dest:
                source.backup(dest)
        self.metadata = {
            "path": "/data/backups/audit-synthetic.sqlite3",
            "integrity": "ok",
            "bytes": self.snapshot.stat().st_size,
            "sha256": hashlib.sha256(self.snapshot.read_bytes()).hexdigest(),
            "rows": {table: (1 if table == "auth_user" else 0) for table in REQUIRED_TABLES},
        }
        self.destination = self.root / "exports"

    def fake_docker(self, args):
        if args[1] == "exec":
            return json.dumps(self.metadata)
        if args[1] == "cp":
            shutil.copyfile(self.snapshot, args[-1])
            return ""
        raise AssertionError(args)

    def test_export_verifies_restores_and_never_changes_live_database(self):
        before = self.original.read_bytes()
        result = export_backup(self.destination, command=self.fake_docker)
        path = Path(result["destination"])
        self.assertEqual(path.read_bytes(), self.snapshot.read_bytes())
        self.assertEqual(self.original.read_bytes(), before)
        self.assertEqual(result["verification"]["restore"], "passed")
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_existing_export_is_never_overwritten(self):
        export_backup(self.destination, command=self.fake_docker)
        with self.assertRaises(FileExistsError):
            export_backup(self.destination, command=self.fake_docker)
        self.assertEqual(len(list(self.destination.glob("*.sqlite3"))), 1)

    def test_corrupted_copy_is_rejected_and_temporary_file_removed(self):
        def corrupted(args):
            if args[1] == "exec":
                return json.dumps(self.metadata)
            if args[1] == "cp":
                Path(args[-1]).write_bytes(b"malformed")
                return ""
        with self.assertRaises(ValueError):
            export_backup(self.destination, command=corrupted)
        self.assertEqual(list(self.destination.iterdir()), [])

    def test_rejects_untrusted_metadata_and_open_folder(self):
        with self.assertRaises(ValueError):
            parse_metadata(json.dumps({**self.metadata, "path": "/etc/shadow"}))
        self.destination.mkdir(mode=0o755)
        os.chmod(self.destination, 0o755)
        with self.assertRaises(PermissionError):
            export_backup(self.destination, command=self.fake_docker)

    def test_sha256_and_restore_detect_tampering(self):
        self.snapshot.write_bytes(self.snapshot.read_bytes() + b"tampering")
        with self.assertRaises(ValueError):
            verify_host_copy(self.snapshot, self.metadata)


if __name__ == "__main__":
    unittest.main()
