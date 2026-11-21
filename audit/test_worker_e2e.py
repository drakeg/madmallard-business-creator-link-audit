"""Exercise source→queued scan→real worker→review/export using offline HTTP stubs."""
import csv
import io
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from .models import Customer, Link, Project, Result, Scan, Source


class StopWorkerLoop(Exception):
    pass


class WorkerEndToEndTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("synthetic-owner", password="not-used-in-tests")
        self.other = User.objects.create_user("other-customer", password="not-used-in-tests")
        customer = Customer.objects.create(name="Synthetic worker customer")
        customer.members.add(self.owner)
        self.project = Project.objects.create(customer=customer, name="Simulated worker project")
        self.a = "https://example.com/gear?tag=synthetic-owner"
        self.b = "https://example.com/gear?tag=synthetic-other"
        for title, url in (("Video A",self.a),("Video B",self.a),("Video C",self.b)):
            source = Source.objects.create(project=self.project,title=title,content=f"Gear: {url}")
            Link.objects.create(source=source,url=url)

    def run_worker_to_empty_queue(self, check):
        from .management.commands.worker import Command
        with patch("audit.management.commands.worker.check",side_effect=check) as check_mock, patch(
            "audit.management.commands.worker.time.sleep", side_effect=StopWorkerLoop
        ):
            with self.assertRaises(StopWorkerLoop):
                Command().handle()
        return check_mock

    @staticmethod
    def simulated_response(url):
        if url.endswith("synthetic-other"):
            return {
                "category":"broken","status":404,"final_url":url,
                "chain":[{"url":url,"status":404,"location":""}],
                "reason":"Simulated 404 for offline QA",
            }
        return {
            "category":"destination_review","status":200,"final_url":url,
            "chain":[{"url":url,"status":200,"location":""}],
            "reason":"Simulated page reached; not verified",
            "content_evidence":{"outcome":"page_reached","title":"Synthetic item"},
        }

    def test_queued_scan_worker_deduplicates_and_exports_without_network(self):
        self.client.force_login(self.owner)
        response=self.client.post(f"/projects/{self.project.pk}/scan/")
        scan=Scan.objects.get(project=self.project)
        self.assertEqual(response.status_code,302)
        self.assertEqual(scan.state,"queued")
        check_mock=self.run_worker_to_empty_queue(self.simulated_response)
        scan.refresh_from_db()
        self.assertEqual(scan.state,"complete")
        self.assertEqual(scan.progress,2)
        self.assertEqual(scan.total,2)
        self.assertEqual(Result.objects.filter(scan=scan).count(),3)
        self.assertEqual(check_mock.call_count,2)
        self.assertEqual({call.args[0] for call in check_mock.call_args_list},{self.a,self.b})
        self.assertEqual(Result.objects.filter(scan=scan,category="broken").count(),1)
        self.assertEqual(Result.objects.filter(scan=scan,category="destination_review").count(),2)
        review=self.client.get(f"/reports/{scan.pk}/summary/")
        self.assertEqual(review.status_code,200)
        self.assertEqual(review.context["unique_count"],2)
        self.assertEqual(review.context["occurrences"],3)
        export=self.client.get(f"/reports/{scan.pk}/summary/export/")
        rows=list(csv.DictReader(io.StringIO(export.content.decode("utf8"))))
        self.assertEqual(len(rows),2)
        self.assertEqual({row["original_url_exact"] for row in rows},{self.a,self.b})
        self.assertEqual(sorted(int(row["occurrences"]) for row in rows),[1,2])
        printable=self.client.get(f"/reports/{scan.pk}/export/?format=html")
        self.assertEqual(printable.status_code,200)
        self.assertContains(printable,"Print / save PDF")
        # A separate customer must see neither the grouped report nor the export.
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(f"/reports/{scan.pk}/summary/").status_code,404)
        self.assertEqual(self.client.get(f"/reports/{scan.pk}/summary/export/").status_code,404)

    def test_worker_failure_is_explicit_and_preserves_original_source(self):
        self.client.force_login(self.owner)
        self.client.post(f"/projects/{self.project.pk}/scan/")
        scan=Scan.objects.get(project=self.project)
        source_before=list(Source.objects.filter(project=self.project).values_list("content",flat=True))

        def offline_failure(_url):
            raise RuntimeError("Simulated checker failure")

        check_mock=self.run_worker_to_empty_queue(offline_failure)
        scan.refresh_from_db()
        self.assertEqual(scan.state,"failed")
        self.assertIn("Simulated checker failure",scan.error)
        self.assertGreaterEqual(check_mock.call_count,1)
        self.assertEqual(list(Source.objects.filter(project=self.project).values_list("content",flat=True)),source_before)
        self.assertFalse(Result.objects.filter(scan=scan).exists())
