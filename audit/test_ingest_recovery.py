import subprocess
import time
from unittest.mock import Mock,patch
from django.test import SimpleTestCase
from .ingest import extract

URL="https://example.com/product?tag=Exact%2BId&ref=A+B"

class ExtractionRecoveryTests(SimpleTestCase):
    @patch("audit.ingest.subprocess.run",side_effect=subprocess.TimeoutExpired("lychee",5))
    def test_timeout_keeps_exact_urls_and_reports_fallback(self,run):
        notices=[]
        self.assertEqual(extract("Gear "+URL,notices=notices),[URL])
        self.assertIn("built-in URL parser",notices[0])
        self.assertLessEqual(run.call_args.kwargs["timeout"],5)

    @patch("audit.ingest.subprocess.run",side_effect=FileNotFoundError("lychee"))
    def test_missing_helper_does_not_drop_links(self,run):
        notices=[]
        self.assertEqual(extract(URL,notices=notices),[URL])
        self.assertEqual(len(notices),1)

    @patch("audit.ingest.subprocess.run",return_value=Mock(returncode=1))
    def test_nonzero_helper_exit_is_visible_and_preserves_urls(self,run):
        notices=[]
        self.assertEqual(extract(URL,notices=notices),[URL])
        self.assertTrue(notices)

    @patch("audit.ingest.subprocess.run")
    def test_expired_batch_budget_skips_helper(self,run):
        notices=[]
        self.assertEqual(extract(URL,deadline=time.monotonic()-1,notices=notices),[URL])
        run.assert_not_called()
        self.assertTrue(notices)

    @patch("audit.ingest.subprocess.run",side_effect=subprocess.TimeoutExpired("lychee",5))
    def test_batch_warning_is_not_repeated_for_every_source(self,run):
        notices=[]
        extract(URL,notices=notices)
        extract(URL,notices=notices)
        self.assertEqual(len(notices),1)

    @patch("audit.ingest.Anchors.feed",side_effect=AssertionError("malformed"))
    @patch("audit.ingest.subprocess.run",return_value=Mock(returncode=0,stdout=URL))
    def test_malformed_markup_still_retains_literal_http_urls(self,run,feed):
        notices=[]
        self.assertEqual(extract(URL,notices=notices),[URL])
        self.assertIn("malformed",notices[0])
