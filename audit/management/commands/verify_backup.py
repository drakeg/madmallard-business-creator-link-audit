import json
import sqlite3
from django.core.management.base import BaseCommand, CommandError
from audit.backup import verify_restore

class Command(BaseCommand):
    help = "Restore a backup into a temporary database and verify it; never replace live data."
    def add_arguments(self, parser):
        parser.add_argument("--input", required=True, help="Local SQLite backup path")
    def handle(self, *args, **options):
        try:
            evidence = verify_restore(options["input"])
        except (OSError, ValueError, TimeoutError, sqlite3.Error) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(evidence, sort_keys=True))
