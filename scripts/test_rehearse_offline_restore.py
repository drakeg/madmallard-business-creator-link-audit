"""Offline portability guardrails without a Docker dependency."""
import hashlib
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess

from audit.backup import REQUIRED_TABLES
from rehearse_offline_restore import rehearse, verify_backup_input


class RecoveryRehearsalTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.dir = Path(temp.name)
        self.backup = self.dir / "audit-test.sqlite3"
        with sqlite3.connect(self.backup) as db:
            for table in REQUIRED_TABLES:
                db.execute(f'CREATE TABLE "{table}" (id INTEGER PRIMARY KEY)')
            db.execute("INSERT INTO auth_user VALUES (1)")
        self.backup.chmod(0o600)

    def test_readonly_input_and_isolated_docker_no_network_or_ports(self):
        before = self.backup.read_bytes()
        calls = []

        def fake_run(args, **kwargs):
            calls.append(args)
            return CompletedProcess(args, 0, stdout="RESTORED_APPLICATION_OK\n" if args[1] == "run" else '{"Id":"abc"}', stderr="")

        result = rehearse(self.backup, "audit:verified", command=fake_run)
        args = calls[1]
        self.assertEqual(calls[0][:3], ["docker", "image", "inspect"])
        self.assertIn("--network", args)
        self.assertEqual(args[args.index("--network")+1], "none")
        self.assertIn("--read-only", args)
        self.assertIn("--cap-drop", args)
        self.assertNotIn("-p", args)
        self.assertNotIn("--publish", args)
        self.assertIn(f"type=bind,src={self.backup},dst=/recovery/source.sqlite3,readonly", args)
        self.assertEqual(result["live_data_modified"], False)
        self.assertEqual(before, self.backup.read_bytes())

    def test_rejects_tampering_without_running_docker(self):
        with self.assertRaises(ValueError):
            rehearse(self.backup, "audit:verified", expected_sha256="0"*64, command=lambda *a, **k: self.fail("unexpected Docker"))
        self.assertEqual(verify_backup_input(self.backup)[1], hashlib.sha256(self.backup.read_bytes()).hexdigest())

    def test_symlink_and_world_readable_backup_rejected(self):
        link = self.dir / "symbolic.sqlite3"
        link.symlink_to(self.backup)
        with self.assertRaises(ValueError):
            verify_backup_input(link)
        self.backup.chmod(0o644)
        with self.assertRaises(PermissionError):
            verify_backup_input(self.backup)

    def test_invalid_image_and_incomplete_database_rejected(self):
        with self.assertRaises(ValueError):
            rehearse(self.backup, "not allowed image")
        self.backup.write_bytes(b"not a backup")
        with self.assertRaises(sqlite3.DatabaseError):
            verify_backup_input(self.backup)

    def test_no_false_success_without_django_confirmation(self):
        def fake_run(args, **kwargs):
            return CompletedProcess(args, 0, stdout="{}" if args[1] == "image" else "startup logs only", stderr="")
        with self.assertRaises(ValueError):
            rehearse(self.backup, "audit:verified", command=fake_run)


if __name__ == "__main__":
    unittest.main()
