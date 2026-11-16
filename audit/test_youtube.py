import json
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase, SimpleTestCase, override_settings, Client
from django.contrib.auth.models import User
from django.utils import timezone
from .youtube import parse_channel, load_channel, api, YouTubeError
from .models import Customer, Project, Source, Link, YouTubePreview, Scan
from .youtube_views import purge_expired

CHANNEL = "UC" + "a" * 22
VIDEO = "a" * 11
URL = "https://www.youtube.com/@madmallardsadventures"
PAYLOAD = {"channel_id":CHANNEL,"channel_url":URL,"channel_title":"Synthetic channel",
           "videos":[{"id":VIDEO,"title":"Gear","description":"Product https://example.com?tag=Exact%2BId&ref=A+B","published":"2026-11-01T10:00:00Z","url":"https://www.youtube.com/watch?v="+VIDEO}],"next_page":"older"}

class YouTubeURLTests(SimpleTestCase):
    def test_share_url_is_normalized(self):
        selector, canonical = parse_channel("https://youtube.com/@madmallardsadventures?si=UpH1yjsYQaQfp2VL")
        self.assertEqual(selector,{"forHandle":"@madmallardsadventures"})
        self.assertEqual(canonical,URL)
    def test_channel_id_and_bare_handle(self):
        self.assertEqual(parse_channel("https://youtube.com/channel/"+CHANNEL)[0],{"id":CHANNEL})
        self.assertEqual(parse_channel("@madmallardsadventures")[1],URL)
    def test_unsafe_and_non_channel_urls_rejected(self):
        for value in ["http://127.0.0.1/@creator","https://youtube.com.evil.test/@creator","https://user:pass@youtube.com/@creator","https://youtube.com:8042/@creator","https://youtube.com/watch?v="+VIDEO,"file:///etc/passwd","https://youtu.be/"+VIDEO]:
            with self.assertRaises(YouTubeError,msg=value): parse_channel(value)
    @patch("audit.youtube.fetch")
    def test_key_is_header_only_and_redirects_disabled(self,fetch):
        fetch.return_value=(200,"",[],b'{"items":[]}')
        api("channels","synthetic-key",part="snippet",forHandle="@creator")
        self.assertNotIn("synthetic-key",fetch.call_args.args[0])
        self.assertEqual(fetch.call_args.kwargs["request_headers"],{"X-Goog-Api-Key":"synthetic-key"})
        self.assertFalse(fetch.call_args.kwargs["follow_redirects"])
    @patch("audit.youtube.fetch",side_effect=ValueError("transport leaked SECRET"))
    def test_transport_error_redacts_credentials(self,fetch):
        with self.assertRaises(YouTubeError) as error: api("channels","SECRET",part="snippet")
        self.assertNotIn("SECRET",str(error.exception))
    @patch("audit.youtube.api")
    def test_official_endpoints_and_channel_ownership(self,api_mock):
        api_mock.side_effect=[
            {"items":[{"id":CHANNEL,"snippet":{"title":"Channel"},"contentDetails":{"relatedPlaylists":{"uploads":"UUuploads"}}}]},
            {"items":[{"contentDetails":{"videoId":VIDEO}},{"contentDetails":{"videoId":"b"*11}}],"nextPageToken":"next"},
            {"items":[{"id":VIDEO,"snippet":{"channelId":CHANNEL,"title":"Gear","description":"Exact %2B"},"status":{"privacyStatus":"public"}},{"id":"b"*11,"snippet":{"channelId":"other","title":"Not this channel","description":"no"},"status":{"privacyStatus":"public"}}]}
        ]
        data=load_channel(URL,"key")
        self.assertEqual([v["id"] for v in data["videos"]],[VIDEO])
        self.assertEqual(data["videos"][0]["description"],"Exact %2B")
        self.assertEqual([c.args[0] for c in api_mock.call_args_list],["channels","playlistItems","videos"])
    def test_missing_key_explains_setup(self):
        with self.assertRaisesMessage(YouTubeError,"API key"): api("channels","",part="snippet")

@override_settings(YOUTUBE_API_KEY="")
class YouTubeWorkflowTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user("owner",password="a-long-test-password")
        self.other=User.objects.create_user("other",password="another-long-password")
        customer=Customer.objects.create(name="Owner");customer.members.add(self.user)
        self.project=Project.objects.create(customer=customer,name="Channel audit")
        self.client.force_login(self.user)
        self.path=f"/projects/{self.project.pk}/youtube/"
    def preview(self):
        return YouTubePreview.objects.create(project=self.project,user=self.user,payload=PAYLOAD,expires_at=timezone.now()+timedelta(minutes=30))
    def test_setup_page_and_missing_key(self):
        self.assertContains(self.client.get(self.path),"YouTube Data API key")
        response=self.client.post(self.path,{"action":"browse","channel_url":URL})
        self.assertContains(response,"API key")
        self.assertEqual(Source.objects.count(),0)
    @patch("audit.youtube_views.load_channel",return_value=PAYLOAD)
    def test_browse_does_not_persist_key(self,load):
        response=self.client.post(self.path,{"action":"browse","channel_url":URL,"api_key":"SECRET-KEY"})
        self.assertEqual(response.status_code,200)
        self.assertNotContains(response,"SECRET-KEY")
        self.assertNotIn("SECRET-KEY",json.dumps(YouTubePreview.objects.get().payload))
        self.assertNotIn("SECRET-KEY",json.dumps(dict(self.client.session)))
    @patch("audit.youtube_views.extract",return_value=["https://example.com?tag=Exact%2BId&ref=A+B"])
    def test_import_keeps_provenance_and_deduplicates(self,extract):
        preview=self.preview()
        data={"action":"import","preview":str(preview.pk),"videos":[VIDEO],"authorized":"on"}
        response=self.client.post(self.path,data)
        self.assertEqual(response.status_code,302)
        source=self.project.sources.get()
        self.assertEqual(source.youtube_video_id,VIDEO)
        self.assertEqual(source.original_url,"https://www.youtube.com/watch?v="+VIDEO)
        self.assertEqual(source.content,PAYLOAD["videos"][0]["description"])
        self.assertGreater(source.api_expires_at,timezone.now())
        self.assertEqual(source.links.get().affiliate_parameters,"tag=Exact%2BId&ref=A+B")
        self.client.post(self.path,data)
        self.assertEqual(self.project.sources.count(),1)
    def test_cross_customer_preview_and_import_blocked(self):
        preview=self.preview()
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.path).status_code,404)
        self.assertEqual(self.client.post(self.path,{"action":"import","preview":preview.pk,"videos":[VIDEO],"authorized":"on"}).status_code,404)
    def test_same_customer_different_user_cannot_use_preview(self):
        self.project.customer.members.add(self.other)
        preview=self.preview();self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.path+"?preview="+str(preview.pk)).status_code,404)
    def test_unknown_video_requires_real_preview_selection(self):
        preview=self.preview()
        response=self.client.post(self.path,{"action":"import","preview":preview.pk,"videos":["b"*11],"authorized":"on"})
        self.assertContains(response,"not in this channel")
        self.assertEqual(Source.objects.count(),0)
    def test_permission_required(self):
        preview=self.preview()
        self.client.post(self.path,{"action":"import","preview":preview.pk,"videos":[VIDEO]})
        self.assertEqual(Source.objects.count(),0)
    def test_expired_previews_and_api_sources_purged_but_owner_sources_remain(self):
        preview=self.preview();preview.expires_at=timezone.now()-timedelta(seconds=1);preview.save()
        Source.objects.create(project=self.project,title="API old",content="old",youtube_video_id=VIDEO,api_expires_at=timezone.now()-timedelta(seconds=1))
        Source.objects.create(project=self.project,title="Pasted source",content="keep")
        purge_expired()
        self.assertFalse(YouTubePreview.objects.exists())
        self.assertEqual(list(Source.objects.values_list("title",flat=True)),["Pasted source"])
    def test_scan_locked_project_rejects_api_import(self):
        preview=self.preview();Scan.objects.create(project=self.project,state="complete")
        self.client.post(self.path,{"action":"import","preview":preview.pk,"videos":[VIDEO],"authorized":"on"})
        self.assertEqual(Source.objects.count(),0)
    def test_local_youtube_deletion_requires_confirmation(self):
        source=Source.objects.create(project=self.project,title="API",content="data",youtube_video_id=VIDEO)
        keep=Source.objects.create(project=self.project,title="Manual",content="keep")
        path=self.path+"delete/"
        self.client.post(path,{})
        self.assertTrue(Source.objects.filter(pk=source.pk).exists())
        self.client.post(path,{"confirm":"DELETE"})
        self.assertFalse(Source.objects.filter(pk=source.pk).exists())
        self.assertTrue(Source.objects.filter(pk=keep.pk).exists())
    def test_malformed_preview_is_404_not_server_error(self):
        self.assertEqual(self.client.post(self.path,{"action":"import","preview":"bad"}).status_code,404)
    def test_youtube_post_requires_csrf(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.user)
        self.assertEqual(client.post(self.path,{"action":"browse","channel_url":URL}).status_code,403)

    @override_settings(MAX_SOURCES=1)
    @patch("audit.youtube_views.extract",return_value=["https://example.com"])
    def test_import_source_limit_is_atomic(self,extract):
        Source.objects.create(project=self.project,title="Existing",content="keep")
        preview=self.preview()
        response=self.client.post(self.path,{"action":"import","preview":preview.pk,"videos":[VIDEO],"authorized":"on"})
        self.assertContains(response,"source limit exceeded")
        self.assertEqual(self.project.sources.count(),1)
    @override_settings(MAX_LINKS=1)
    @patch("audit.youtube_views.extract",return_value=["https://example.com/a","https://example.com/b"])
    def test_import_unique_link_limit_is_atomic(self,extract):
        preview=self.preview()
        response=self.client.post(self.path,{"action":"import","preview":preview.pk,"videos":[VIDEO],"authorized":"on"})
        self.assertContains(response,"100-unique-link")
        self.assertEqual(self.project.sources.count(),0)
    @patch("audit.youtube_views.load_channel",return_value=PAYLOAD)
    def test_older_page_uses_scoped_server_token(self,load):
        preview=self.preview()
        response=self.client.post(self.path,{"action":"browse","channel_url":URL,"page":preview.pk,"api_key":"synthetic-key","page_token":"forged"})
        self.assertEqual(response.status_code,200)
        self.assertEqual(load.call_args.args[2],"older")
