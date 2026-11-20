import tempfile
import unittest
from pathlib import Path
from check_lockfile import inconsistencies

class LockfileTests(unittest.TestCase):
    def test_current_lock_satisfies_manifest(self):
        self.assertEqual(inconsistencies(), [])
    def test_incompatible_lock_fails(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "requirements.txt").write_text("Django>=6.1,<6.2\n")
            (root / "requirements.lock").write_text("Django==5.2.19\n")
            self.assertTrue(inconsistencies(root))
    def test_missing_lock_pin_fails(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "requirements.txt").write_text("Django>=5.2,<5.3\n")
            (root / "requirements.lock").write_text("urllib3==2.8.0\n")
            self.assertTrue(inconsistencies(root))

if __name__ == "__main__":
    unittest.main()
