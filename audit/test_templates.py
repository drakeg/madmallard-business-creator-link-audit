"""Prevent incomplete Django templates from breaking creator review workflows."""
from pathlib import Path

from django.conf import settings
from django.template.loader import get_template
from django.test import SimpleTestCase


class TemplateIntegrityTests(SimpleTestCase):
    def test_every_page_template_compiles(self):
        root = Path(settings.BASE_DIR) / "audit" / "templates" / "audit"
        templates = sorted(root.glob("*.html"))
        self.assertTrue(templates, "No application templates found")
        for path in templates:
            with self.subTest(template=path.name):
                get_template("audit/" + path.name)
