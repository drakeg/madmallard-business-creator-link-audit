import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from django.test import SimpleTestCase
from audit.backup import REQUIRED_TABLES, create_backup, verify_restore

class BackupTests(SimpleTestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.source = Path(self.folder.name) / "live.sqlite3"
        self.output = Path(self.folder.name) / "backups" / "snapshot.sqlite3"
        with closing(sqlite3.connect(self.source)) as db:
            for table in REQUIRED_TABLES:
                db.execute(f'CREATE TABLE "{table}" (id INTEGER PRIMARY KEY, value TEXT)')
            db.execute("INSERT INTO auth_user VALUES (1, 'synthetic-password-hash')")
            db.execute("INSERT INTO audit_source VALUES (1, 'Original source')")
            db.commit()

    def test_snapshot_and_isolated_restore_preserve_rows(self):
        evidence = create_backup(self.source, self.output)
        self.assertEqual(evidence["rows"]["auth_user"], 1)
        self.assertEqual(evidence["integrity"], "ok")
        self.assertEqual(os.stat(self.output).st_mode & 0o777, 0o600)
        self.assertEqual(verify_restore(self.output)["restore"], "passed")
        with closing(sqlite3.connect(self.source)) as db:
            db.execute("UPDATE audit_source SET value='Later edit'")
            db.commit()
        with closing(sqlite3.connect(self.output)) as db:
            self.assertEqual(db.execute("SELECT value FROM audit_source").fetchone()[0], "Original source")
            self.assertEqual(db.execute("SELECT value FROM auth_user").fetchone()[0], "synthetic-password-hash")

    def test_existing_destination_is_preserved(self):
        self.output.parent.mkdir()
        self.output.write_text("keep-existing")
        with self.assertRaises(FileExistsError):
            create_backup(self.source, self.output)
        self.assertEqual(self.output.read_text(), "keep-existing")

    def test_live_database_cannot_be_destination(self):
        with self.assertRaises(ValueError):
            create_backup(self.source, self.source)
        self.assertTrue(self.source.exists())

    def test_missing_source_does_not_create_empty_database(self):
        missing = Path(self.folder.name) / "missing.sqlite3"
        with self.assertRaises(ValueError):
            create_backup(missing, self.output)
        self.assertFalse(missing.exists())
        self.assertFalse(self.output.exists())

    def test_incomplete_database_is_rejected_and_partial_backup_removed(self):
        with closing(sqlite3.connect(self.source)) as db:
            db.execute("DROP TABLE audit_result"); db.commit()
        with self.assertRaises(ValueError):
            create_backup(self.source, self.output)
        self.assertFalse(self.output.exists())

    def test_corrupt_backup_is_rejected_without_changing_source(self):
        self.output.parent.mkdir()
        self.output.write_bytes(b"not a SQLite database")
        original = self.source.read_bytes()
        with self.assertRaises(sqlite3.DatabaseError):
            verify_restore(self.output)
        self.assertEqual(self.source.read_bytes(), original)
