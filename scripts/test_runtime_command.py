"""Keep the Gunicorn runtime compatible with the read-only Compose filesystem."""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class RuntimeCommandTests(unittest.TestCase):
    def test_gunicorn_control_socket_disabled_without_relaxing_container_hardening(self):
        dockerfile=(ROOT/"Dockerfile").read_text()
        compose=(ROOT/"compose.yml").read_text()
        self.assertIn("gunicorn config.wsgi:application",dockerfile)
        self.assertIn("--no-control-socket",dockerfile)
        self.assertIn("read_only: true",compose)
        self.assertIn("cap_drop: [ALL]",compose)
        self.assertIn("no-new-privileges:true",compose)

if __name__ == "__main__":
    unittest.main()
