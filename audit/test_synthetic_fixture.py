"""Guardrails for synthetic browser fixture seeding."""
import os
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from .models import Customer, Link, Project, Result, Scan, Source


class SyntheticBrowserFixtureTests(TestCase):
    def test_requires_confirmation_and_explicit_qa_environment(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(CommandError):
                call_command("seed_synthetic_browser_fixture", "--confirm-synthetic-only")
        self.assertEqual(Customer.objects.count(), 0)

    def test_fixture_only_seeds_empty_database_without_external_network(self):
        with patch.dict(os.environ, {"AUDIT_ALLOW_SYNTHETIC_FIXTURES":"1"}):
            call_command("seed_synthetic_browser_fixture", "--confirm-synthetic-only", verbosity=0)
            self.assertEqual(Customer.objects.count(),1)
            self.assertEqual(Project.objects.count(),1)
            self.assertEqual(Source.objects.count(),3)
            self.assertEqual(Link.objects.count(),3)
            self.assertEqual(Scan.objects.count(),1)
            self.assertEqual(Result.objects.count(),3)
            self.assertEqual(Scan.objects.first().state,"complete")
            self.assertEqual(Result.objects.values("tested_url").distinct().count(),2)
            with self.assertRaises(CommandError):
                call_command("seed_synthetic_browser_fixture", "--confirm-synthetic-only")
            self.assertEqual(Scan.objects.count(),1)

    def test_does_not_seed_existing_customer_records(self):
        Customer.objects.create(name="Actual customer fixture")
        with patch.dict(os.environ, {"AUDIT_ALLOW_SYNTHETIC_FIXTURES":"1"}):
            with self.assertRaises(CommandError):
                call_command("seed_synthetic_browser_fixture", "--confirm-synthetic-only")
        self.assertEqual(Project.objects.count(),0)
