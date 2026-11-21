"""Explicit, isolated-QA-only deterministic completed scan. Never runs network scans."""
import json
import os

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from audit.models import Customer, Link, Project, Result, Scan, Source

SOURCE_NAME = "SYNTHETIC Browser QA — no customer content"
SAME = "https://example.com/camping-chair?tag=synthetic-creator"
OTHER = "https://example.com/camping-chair?tag=synthetic-other"


class Command(BaseCommand):
    help = "Seed synthetic completed audit in an otherwise-empty isolated QA volume."

    def add_arguments(self, parser):
        parser.add_argument("--confirm-synthetic-only", action="store_true")

    def handle(self, *args, **options):
        if not options["confirm_synthetic_only"] or os.environ.get("AUDIT_ALLOW_SYNTHETIC_FIXTURES") != "1":
            raise CommandError("Synthetic fixture disabled: explicit confirmation and QA env required")
        # A second safety guard: never add fixtures alongside an existing customer/project.
        with transaction.atomic():
            if Customer.objects.exists() or Project.objects.exists() or Scan.objects.exists() or Source.objects.exists():
                raise CommandError("Refusing to seed nonempty application database")
            customer = Customer.objects.create(name=SOURCE_NAME)
            project = Project.objects.create(customer=customer, name="Synthetic action-export workflow")
            examples = (
                ("Synthetic Video A", SAME, "Camping chair link one — "+SAME),
                ("Synthetic Video B", SAME, "Repeated chair link — "+SAME),
                ("Synthetic Video C", OTHER, "Different affiliate ID — "+OTHER),
            )
            links = []
            for title, url, content in examples:
                source = Source.objects.create(project=project, title=title, content=content)
                links.append(Link.objects.create(source=source, url=url))
            scan = Scan.objects.create(
                project=project, state="complete", progress=2, total=2,
                targets={str(link.pk): link.url for link in links},
                finished=timezone.now(),
            )
            for link in links:
                Result.objects.create(
                    scan=scan, link=link, tested_url=link.url,
                    final_url=link.url, category="destination_review", status=200,
                    content_evidence={"outcome":"page_reached","title":"Synthetic sample product"},
                )
        self.stdout.write(json.dumps({
            "synthetic":True,
            "project_path":f"/projects/{project.pk}/",
            "review_path":f"/reports/{scan.pk}/summary/",
            "print_path":f"/reports/{scan.pk}/export/?format=html",
            "csv_path":f"/reports/{scan.pk}/summary/export/",
            "expected_unique":2,
            "expected_occurrences":3,
        }, sort_keys=True))
