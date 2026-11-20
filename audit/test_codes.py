import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from .codes import code_tokens, register_owner_source_codes
from .models import Customer, DiscountCode, Link, Project, Result, Scan, Source


class CodeTokenTests(TestCase):
    def test_exact_tokens_are_kept_and_prose_is_not_invented(self):
        values = code_tokens("MALLARD10\nmallard10\nRV-20%\nRV10 - 10% off\n  SPRING_25  \n")
        self.assertEqual(values, ["MALLARD10", "RV10", "SPRING_25"])

    def test_api_derived_codes_are_not_automatically_registered(self):
        user = User.objects.create_user("owner", password="test-password-long")
        customer = Customer.objects.create(name="Creator")
        customer.members.add(user)
        project = Project.objects.create(customer=customer, name="Imports")
        source = Source.objects.create(
            project=project, title="Video", content="Use YOUTUBE10",
            codes="YOUTUBE10", youtube_video_id="abc12345678",
        )
        self.assertEqual(register_owner_source_codes(project, [source]), 0)
        self.assertFalse(DiscountCode.objects.filter(project=project).exists())


class DiscountCodeWorkflowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("reviewer", password="test-password-long")
        self.other = User.objects.create_user("other", password="other-password-long")
        customer = Customer.objects.create(name="Creator")
        customer.members.add(self.user)
        other_customer = Customer.objects.create(name="Other")
        other_customer.members.add(self.other)
        self.project = Project.objects.create(customer=customer, name="RV links")
        self.other_project = Project.objects.create(customer=other_customer, name="Other links")
        self.source = Source.objects.create(project=self.project, title="Gear video", content="Use MALLARD10")
        self.other_source = Source.objects.create(project=self.other_project, title="Private", content="Secret")
        self.scan = Scan.objects.create(project=self.project, state="complete")
        self.client.force_login(self.user)

    def test_owner_source_import_registers_exact_codes_case_insensitively(self):
        # A completed scan locks sources; test the import on a fresh engagement.
        new_project = Project.objects.create(customer=self.project.customer, name="New import")
        with patch("audit.views.extract", return_value=["https://example.com/product?tag=Creator%2BId"]):
            response = self.client.post(f"/projects/{new_project.pk}/", {
                "title": "Gear list",
                "content": "Save with MALLARD10",
                "discount_codes": "MALLARD10\nMALLARD10 - 10% off",
                "authorized": "on",
            })
        self.assertEqual(response.status_code, 302)
        record = DiscountCode.objects.get(project=new_project, code="MALLARD10")
        self.assertEqual(record.status, "unverified")
        self.assertEqual(record.sources.count(), 1)
        self.assertFalse(DiscountCode.objects.filter(code__startswith="MALLARD10 -").exists())

    def test_manual_registration_is_scoped_case_insensitive_and_validated(self):
        response = self.client.post(f"/projects/{self.project.pk}/codes/add/", {
            "code": "SPRING-25", "merchant_url": "https://shop.example/item", "source": self.source.pk,
        })
        self.assertEqual(response.status_code, 302)
        record = DiscountCode.objects.get(project=self.project)
        self.assertEqual(record.code, "SPRING-25")
        self.assertEqual(record.sources.get(), self.source)

        self.client.post(f"/projects/{self.project.pk}/codes/add/", {"code": "spring-25"})
        self.assertEqual(DiscountCode.objects.filter(project=self.project).count(), 1)

        self.client.post(f"/projects/{self.project.pk}/codes/add/", {"code": "TWO WORDS"})
        self.assertEqual(DiscountCode.objects.filter(project=self.project).count(), 1)

        self.client.post(f"/projects/{self.project.pk}/codes/add/", {"code": "FOREIGN", "source": self.other_source.pk})
        self.assertFalse(DiscountCode.objects.filter(code="FOREIGN").exists())

        self.client.post(f"/projects/{self.other_project.pk}/codes/add/", {"code": "NOPE"})
        self.assertFalse(DiscountCode.objects.filter(project=self.other_project).exists())

    def test_code_review_requires_evidence_and_records_reviewer(self):
        record = DiscountCode.objects.create(project=self.project, code="MALLARD10")
        response = self.client.post(f"/codes/{record.pk}/", {
            "status": "verified", "merchant_url": "https://shop.example/checkout", "evidence": "",
        })
        self.assertContains(response, "Record what you checked")
        record.refresh_from_db()
        self.assertEqual(record.status, "unverified")
        self.assertEqual(record.reviewed_by, "")

        response = self.client.post(f"/codes/{record.pk}/", {
            "status": "verified",
            "merchant_url": "https://shop.example/checkout",
            "evidence": "Entered the code on the merchant checkout on 2026-11-17; discount applied before payment; did not complete purchase.",
        })
        self.assertEqual(response.status_code, 302)
        record.refresh_from_db()
        self.assertEqual(record.status, "verified")
        self.assertEqual(record.reviewed_by, "reviewer")
        self.assertIsNotNone(record.reviewed_at)
        self.assertIn("did not complete purchase", record.evidence)

        self.client.post(f"/codes/{record.pk}/", {"status": "unverified", "evidence": record.evidence})
        record.refresh_from_db()
        self.assertEqual(record.status, "unverified")
        self.assertEqual(record.reviewed_by, "")
        self.assertIsNone(record.reviewed_at)
        self.assertIn("did not complete purchase", record.evidence)

    def test_code_review_cannot_cross_customers(self):
        record = DiscountCode.objects.create(project=self.other_project, code="PRIVATE10")
        self.assertEqual(self.client.get(f"/codes/{record.pk}/").status_code, 404)
        self.assertEqual(self.client.post(f"/codes/{record.pk}/", {"status": "verified", "evidence": "forged"}).status_code, 404)
        record.refresh_from_db()
        self.assertEqual(record.status, "unverified")

    def test_report_print_and_csv_include_code_evidence_and_unique_url_counts(self):
        record = DiscountCode.objects.create(
            project=self.project, code="MALLARD10", merchant_url="https://shop.example/item",
            status="verified", evidence="Merchant checkout applied 10% before payment.",
            reviewed_by="reviewer", reviewed_at="2026-11-17T12:00:00Z",
        )
        record.sources.add(self.source)
        link = Link.objects.create(source=self.source, url="https://shop.example/item?tag=Creator%2BId")
        Result.objects.create(scan=self.scan, link=link, tested_url=link.url, category="destination_review", status=200)

        report = self.client.get(f"/reports/{self.scan.pk}/")
        self.assertContains(report, "Discount code register")
        self.assertContains(report, "MALLARD10")
        self.assertContains(report, "Working — manually verified")
        self.assertContains(report, "Merchant checkout applied 10% before payment.")
        self.assertContains(report, "1 distinct commercial URLs")
        self.assertContains(report, "No checkout or code entry was performed by this app.")
        self.assertContains(report, "https://shop.example/item?tag=Creator%2BId")

        printable = self.client.get(f"/reports/{self.scan.pk}/export/?format=html")
        self.assertContains(printable, "Manual discount-code evidence for this project")
        self.assertContains(printable, "Merchant checkout applied 10% before payment.")

        csv_text = b"".join(self.client.get(f"/reports/{self.scan.pk}/export/").streaming_content).decode()
        self.assertIn("discount_code_register_json", csv_text)
        self.assertIn("MALLARD10", csv_text)
        self.assertIn("Merchant checkout applied 10% before payment.", csv_text)

    def test_unverified_code_is_not_described_as_working(self):
        record = DiscountCode.objects.create(project=self.project, code="MALLARD10")
        link = Link.objects.create(source=self.source, url="https://shop.example/item")
        Result.objects.create(scan=self.scan, link=link, tested_url=link.url, category="broken", status=404)
        report = self.client.get(f"/reports/{self.scan.pk}/")
        self.assertContains(report, "Unverified")
        self.assertNotContains(report, "Working — manually verified")
        self.assertEqual(record.status, "unverified")

    def test_review_budget_counts_unique_commercial_urls_not_repeated_links(self):
        for index in range(10):
            Link.objects.create(
                source=self.source, url=f"https://shop.example/{index}",
                manual_status="destination_verified",
            )
        repeated = Link.objects.create(source=self.source, url="https://shop.example/0")
        repeated_result = Result.objects.create(scan=self.scan, link=repeated, category="destination_review", status=200)
        response = self.client.post(f"/results/{repeated_result.pk}/review/", {
            "manual_status": "destination_verified", "notes": "Checked the same product again.",
        })
        self.assertEqual(response.status_code, 302)
        repeated.refresh_from_db()
        self.assertEqual(repeated.manual_status, "destination_verified")

        new_link = Link.objects.create(source=self.source, url="https://shop.example/new")
        new_result = Result.objects.create(scan=self.scan, link=new_link, category="destination_review", status=200)
        response = self.client.post(f"/results/{new_result.pk}/review/", {
            "manual_status": "destination_verified", "notes": "New destination.",
        })
        self.assertContains(response, "10 distinct commercial URLs")
        new_link.refresh_from_db()
        self.assertEqual(new_link.manual_status, "unreviewed")

    def test_zero_result_export_still_has_register_json(self):
        DiscountCode.objects.create(project=self.project, code="MALLARD10")
        text = b"".join(self.client.get(f"/reports/{self.scan.pk}/export/").streaming_content).decode()
        header = text.splitlines()[0]
        self.assertTrue(header.endswith("discount_code_register_json"))
