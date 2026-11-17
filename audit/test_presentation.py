from types import SimpleNamespace
from django.test import SimpleTestCase,TestCase
from django.contrib.auth.models import User
from .presentation import explain,affiliate_query
from .models import Customer,Project,Source,Link,Scan,Result

FINAL="https://www.amazon.com/dp/B000000001?th=1&linkCode=sl2&tag=creator-demo-20&linkId=abc&ref_=as_li_ss_tl"

class ExplanationTests(SimpleTestCase):
    def result(self,status=200,category="destination_review",final=FINAL):
        return SimpleNamespace(status=status,category=category,final_url=final,link=SimpleNamespace(url="https://amzn.to/example"),chain=[{"url":"https://amzn.to/example","status":301,"location":final},{"url":final,"status":status,"location":""}])

    def test_shortlink_redirect_and_success_are_distinct(self):
        data=explain(self.result())
        self.assertEqual(data["redirect_count"],1)
        self.assertEqual(data["final_status"],"HTTP 200")
        self.assertIn("No HTTP failure",data["assessment"])
        self.assertIn("redirect is not itself a broken link",data["redirect_text"])
        self.assertIn("Permanent redirect",data["steps"][0]["meaning"])
        self.assertEqual(data["product_code"],"B000000001")

    def test_final_affiliate_parameters_are_found_behind_shortlink(self):
        data=explain(self.result())
        self.assertEqual(data["original_parameters"],"")
        self.assertEqual(data["final_parameters"],"linkCode=sl2&tag=creator-demo-20&linkId=abc&ref_=as_li_ss_tl")
        self.assertIn("does not prove",data["action"])

    def test_affiliate_encodings_duplicates_and_case_are_preserved(self):
        self.assertEqual(affiliate_query("https://example.com?tag=Ab%2BC&tag=Second+Tag&linkCode=SL2&other=x"),"tag=Ab%2BC&tag=Second+Tag&linkCode=SL2")

    def test_redirect_to_generic_homepage_prompts_targeted_review(self):
        data=explain(self.result(final="https://www.amazon.com/"))
        self.assertIn("Generic homepage",data["headline"])
        self.assertEqual(data["tone"],"http_review")
        self.assertIn("not a specific product",data["assessment"])
        self.assertEqual(data["final_status"],"HTTP 200")

    def test_redirect_to_product_and_same_host_root_are_not_flagged(self):
        self.assertNotIn("Generic homepage",explain(self.result())["headline"])
        same=self.result(final="https://amzn.to/")
        self.assertNotIn("Generic homepage",explain(same)["headline"])

    def test_homepage_warning_is_overridden_by_manual_mismatch(self):
        result=self.result(final="https://www.amazon.com/")
        result.manual_status="wrong_destination"
        self.assertIn("Wrong destination reported",explain(result)["headline"])

    def test_redirect_to_404_is_missing_page(self):
        data=explain(self.result(404,"broken"))
        self.assertIn("Missing page",data["headline"])
        self.assertEqual(data["safe_final_url"],"")

    def test_access_denial_is_not_classified_as_missing(self):
        data=explain(self.result(403,"access_blocked"))
        self.assertIn("inconclusive",data["headline"])
        self.assertNotIn("Missing page",data["headline"])

    def test_no_response_and_unsafe_links_are_not_clickable(self):
        for status,category,url in [(None,"timeout",""),(None,"unsafe_blocked","http://127.0.0.1"),(200,"destination_review","javascript:alert(1)")]:
            self.assertEqual(explain(self.result(status,category,url))["safe_final_url"],"")

class ResultPageExplanationTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user("viewer",password="test-password-long")
        c=Customer.objects.create(name="Creator");c.members.add(self.user)
        self.project=Project.objects.create(customer=c,name="Audit")
        source=Source.objects.create(project=self.project,title="Video",content="Example description")
        link=Link.objects.create(source=source,url="https://amzn.to/example")
        self.scan=Scan.objects.create(project=self.project,state="complete")
        self.result=Result.objects.create(scan=self.scan,link=link,tested_url=link.url,status=200,category="destination_review",final_url=FINAL,chain=[{"url":link.url,"status":301,"location":FINAL},{"url":FINAL,"status":200,"location":""}])
        self.client.force_login(self.user)

    def test_review_leads_with_outcome_and_final_tag(self):
        response=self.client.get(f"/results/{self.result.pk}/review/")
        self.assertContains(response,"No HTTP failure detected")
        self.assertContains(response,"HTTP 200")
        self.assertContains(response,"Permanent redirect")
        self.assertContains(response,"tag=creator-demo-20")
        self.assertContains(response,"commission tracking works")
        self.result.refresh_from_db()
        self.assertEqual(self.result.manual_status,"unreviewed")

    def test_report_print_and_csv_include_explanations(self):
        report=self.client.get(f"/reports/{self.scan.pk}/")
        self.assertContains(report,"Destination responded")
        self.assertContains(report,"tag=creator-demo-20")
        printable=self.client.get(f"/reports/{self.scan.pk}/export/?format=html")
        self.assertContains(printable,"Recommended action")
        csv=b"".join(self.client.get(f"/reports/{self.scan.pk}/export/").streaming_content).decode()
        self.assertIn("final_destination_affiliate_parameters",csv)
        self.assertIn("tag=creator-demo-20",csv)

    def test_manual_wrong_destination_overrides_success_headline_only(self):
        self.result.manual_status="wrong_destination"
        self.result.notes="Owner reports Amazon homepage instead of the intended item."
        self.result.save()
        response=self.client.get(f"/results/{self.result.pk}/review/")
        self.assertContains(response,"Wrong destination reported")
        self.assertContains(response,"Amazon homepage")
        self.assertContains(response,"HTTP 200")
        self.result.refresh_from_db()
        self.assertEqual(self.result.category,"destination_review")
        self.assertEqual(self.result.status,200)

    def test_wrong_destination_requires_evidence(self):
        response=self.client.post(f"/results/{self.result.pk}/review/",{"manual_status":"wrong_destination","notes":"","replacement":""})
        self.assertContains(response,"Record the evidence")
        self.result.refresh_from_db()
        self.assertEqual(self.result.manual_status,"unreviewed")

    def test_owner_can_record_wrong_destination_without_editing_url(self):
        response=self.client.post(f"/results/{self.result.pk}/review/",{"manual_status":"wrong_destination","notes":"Owner browser opened the homepage rather than the listed product.","replacement":""})
        self.assertEqual(response.status_code,302)
        self.result.refresh_from_db()
        self.assertEqual(self.result.manual_status,"wrong_destination")
        self.assertEqual(self.result.link.url,"https://amzn.to/example")
        self.assertEqual(self.result.status,200)
        self.assertContains(self.client.get(f"/reports/{self.scan.pk}/?review=wrong_destination"),"wrong-destination report")
