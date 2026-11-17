"""Regression coverage for conservative review triage and exact-link grouping."""
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase

from .content_checks import inspect_content
from .models import Customer, Link, Project, Result, Scan, Source
from .quick_review import grouped_results


class ContentEvidenceTests(SimpleTestCase):
    ORIGINAL = "https://www.amazon.com/dp/B000000001"

    def test_page_product_identifier_matches(self):
        html = b'<html><head><title>Example camping item</title></head><body><input id="ASIN" value="B000000001"></body></html>'
        evidence = inspect_content(self.ORIGINAL, self.ORIGINAL, html)
        self.assertEqual(evidence["outcome"], "product_match")

    def test_http_success_with_missing_page_title_is_not_validated(self):
        evidence = inspect_content(self.ORIGINAL, self.ORIGINAL, b"<title>Product not found</title>")
        self.assertEqual(evidence["outcome"], "soft_missing")

    def test_page_product_identifier_mismatch_requires_review(self):
        html = b'<title>Other camping item</title><input id="ASIN" value="B000000002">'
        evidence = inspect_content(self.ORIGINAL, self.ORIGINAL, html)
        self.assertEqual(evidence["outcome"], "product_mismatch")

    def test_missing_html_does_not_count_as_successful_product_verification(self):
        evidence = inspect_content(self.ORIGINAL, self.ORIGINAL, b"")
        self.assertEqual(evidence["outcome"], "unavailable")


class UniqueLinkReviewTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner", password="test-password-long")
        self.outsider = User.objects.create_user("outsider", password="test-password-long")
        customer = Customer.objects.create(name="Example")
        customer.members.add(self.owner)
        self.project = Project.objects.create(customer=customer, name="Creator")
        self.source_a = Source.objects.create(project=self.project, title="Video A", content="Gear link: https://example.com/item")
        self.source_b = Source.objects.create(project=self.project, title="Video B", content="Gear link: https://example.com/item")
        self.links = [
            Link.objects.create(source=source, url="https://example.com/item")
            for source in (self.source_a, self.source_b)
        ]
        self.scan = Scan.objects.create(project=self.project, state="complete")
        for link in self.links:
            Result.objects.create(
                scan=self.scan, link=link, tested_url=link.url,
                category="destination_review", status=200, final_url=link.url,
                content_evidence={"outcome": "page_reached", "title": "Example"},
            )

    def test_duplicate_exact_urls_need_one_review_group(self):
        groups = grouped_results(self.scan)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["count"], 2)

    def test_groups_keep_distinct_affiliate_parameters_separate(self):
        self.links[1].url = "https://example.com/item?tag=another-creator"
        self.links[1].save(update_fields=["url"])
        second = Result.objects.get(link=self.links[1], scan=self.scan)
        second.tested_url = self.links[1].url
        second.save(update_fields=["tested_url"])
        self.assertEqual(len(grouped_results(self.scan)), 2)

    def test_scoped_quick_report_rejects_other_customer(self):
        self.client.force_login(self.outsider)
        response = self.client.get(f"/reports/{self.scan.pk}/summary/")
        self.assertEqual(response.status_code, 404)

    def test_quick_report_shows_one_unique_link_for_two_uses(self):
        self.client.force_login(self.owner)
        response = self.client.get(f"/reports/{self.scan.pk}/summary/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["unique_count"], 1)
        self.assertEqual(response.context["occurrences"], 2)
