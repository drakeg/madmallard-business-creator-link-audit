import tempfile
import unittest
from pathlib import Path
from validate_repository import check, DOCUMENTS

class StandardsTests(unittest.TestCase):
    def test_actual_repository(self):
        self.assertEqual(check(), [])
    def test_missing_docs_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertIn("Missing README.md", check(Path(directory)))
    def test_static_badge_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name in DOCUMENTS: (root / name).write_text("# Example\n")
            (root / "README.md").write_text("# Example\n\n<!-- madmallard-badges:start -->\n[![CI](https://github.com/example/repo/actions/workflows/test.yml/badge.svg)](https://github.com/example/repo/actions/workflows/test.yml) ![fake](https://img.shields.io/badge/build-passing)\n<!-- madmallard-badges:end -->\n")
            self.assertIn("Static success badge detected", check(root))

if __name__ == "__main__": unittest.main()
