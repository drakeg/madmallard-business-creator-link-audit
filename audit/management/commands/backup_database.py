import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from audit.backup import create_backup

class Command(BaseCommand):
    help = "Create a consistent local SQLite backup; never overwrite an existing file."
    def add_arguments(self, parser):
        parser.add_argument("--output", help="New snapshot path (default: database-directory/backups/timestamp.sqlite3)")
    def handle(self, *args, **options):
        config = settings.DATABASES["default"]
        if config["ENGINE"] != "django.db.backends.sqlite3":
            raise CommandError("This command supports SQLite only")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        output = options["output"] or str(Path(config["NAME"]).parent / "backups" / f"audit-{stamp}.sqlite3")
        try:
            evidence = create_backup(config["NAME"], output)
        except (OSError, ValueError, TimeoutError, sqlite3.Error) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(evidence, sort_keys=True))
