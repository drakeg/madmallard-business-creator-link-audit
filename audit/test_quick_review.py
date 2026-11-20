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

    def test_shared_review_requires_preview_and_confirmation(self):
        self.client.force_login(self.owner)
        first = Result.objects.get(scan=self.scan, link=self.links[0])
        url = f"/reports/{self.scan.pk}/unique/{first.pk}/"
        preview = self.client.post(url, {
            "manual_status": "needs_owner",
            "notes": "Creator needs to confirm the named item.",
            "replacement": "",
        })
        self.assertEqual(preview.status_code, 200)
        token = preview.context["token"]
        denied = self.client.post(url, {"action": "apply", "token": token})
        self.assertEqual(denied.status_code, 400)
        self.assertEqual(Link.objects.filter(manual_status="unreviewed").count(), 2)
        applied = self.client.post(url, {
            "action": "apply", "token": token, "confirm": "on",
        })
        self.assertEqual(applied.status_code, 302)
        self.assertEqual(Link.objects.filter(manual_status="needs_owner").count(), 2)
        self.assertEqual(Result.objects.filter(scan=self.scan, manual_status="needs_owner").count(), 2)

    def test_shared_review_does_not_cross_to_different_affiliate_url(self):
        self.links[1].url = "https://example.com/item?tag=other"
        self.links[1].save(update_fields=["url"])
        second = Result.objects.get(scan=self.scan, link=self.links[1])
        second.tested_url = self.links[1].url
        second.save(update_fields=["tested_url"])
        first = Result.objects.get(scan=self.scan, link=self.links[0])
        self.client.force_login(self.owner)
        url = f"/reports/{self.scan.pk}/unique/{first.pk}/"
        preview = self.client.post(url, {
            "manual_status": "needs_owner", "notes": "Check destination.", "replacement": "",
        })
        self.assertEqual(preview.status_code, 200)
        applied = self.client.post(url, {
            "action": "apply", "token": preview.context["token"], "confirm": "on",
        })
        self.assertEqual(applied.status_code, 302)
        self.links[0].refresh_from_db()
        self.links[1].refresh_from_db()
        self.assertEqual(self.links[0].manual_status, "needs_owner")
        self.assertEqual(self.links[1].manual_status, "unreviewed")

    def test_action_export_has_one_row_per_unique_url(self):
        import csv
        from io import StringIO

        self.client.force_login(self.owner)
        response=self.client.get(f"/reports/{self.scan.pk}/summary/export/")
        self.assertEqual(response.status_code,200)
        self.assertIn("text/csv",response["Content-Type"])
        rows=list(csv.DictReader(StringIO(response.content.decode("utf-8"))))
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["occurrences"],"2")
        self.assertEqual(rows[0]["original_url_exact"],"https://example.com/item")
        self.assertEqual(rows[0]["review_bucket"],"reachable")
        self.assertIn("Video A",rows[0]["affected_sources"])
        self.assertIn("Video B",rows[0]["affected_sources"])
        self.assertEqual(rows[0]["recommended_creator_action"],"Page reached")

    def test_action_export_filter_and_customer_isolation(self):
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(f"/reports/{self.scan.pk}/summary/export/").status_code,404)
        self.client.force_login(self.owner)
        filtered=self.client.get(f"/reports/{self.scan.pk}/summary/export/?show=attention")
        self.assertEqual(filtered.status_code,200)
        self.assertEqual(len(filtered.content.decode().splitlines()),1)
        self.assertEqual(self.client.get(f"/reports/{self.scan.pk}/summary/export/?show=invalid").status_code,400)

    def test_action_export_preserves_affiliate_tags_and_escapes_formulas(self):
        import csv
        from io import StringIO

        self.links[1].url="https://example.com/item?tag=other-account"
        self.links[1].save(update_fields=["url"])
        second=Result.objects.get(scan=self.scan,link=self.links[1])
        second.tested_url=self.links[1].url
        second.notes="=HYPERLINK(\"https://untrusted.example\")"
        second.save(update_fields=["tested_url","notes"])
        self.client.force_login(self.owner)
        response=self.client.get(f"/reports/{self.scan.pk}/summary/export/")
        rows=list(csv.DictReader(StringIO(response.content.decode())))
        self.assertEqual(len(rows),2)
        self.assertEqual(
            {row["original_url_exact"] for row in rows},
            {"https://example.com/item","https://example.com/item?tag=other-account"},
        )
        notes=[row["manual_notes"] for row in rows if row["manual_notes"]]
        self.assertEqual(notes,['\'=HYPERLINK("https://untrusted.example")'])
        self.assertEqual(Result.objects.filter(scan=self.scan).count(),2)

    def test_action_export_link_is_exposed_in_review_page(self):
        self.client.force_login(self.owner)
        response=self.client.get(f"/reports/{self.scan.pk}/summary/")
        self.assertContains(response,"Download action list (CSV)")
        self.assertContains(response,f"/reports/{self.scan.pk}/summary/export/")
