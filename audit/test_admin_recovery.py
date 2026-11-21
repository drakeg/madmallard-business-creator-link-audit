"""Manual, single-use Django password recovery, without an email-provider claim."""
from datetime import datetime, timedelta
from urllib.parse import urlsplit
from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.test import Client, TestCase
from django.urls import reverse

from .models import AdminActionLog, Customer


class AdminIssuedPasswordRecoveryTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("admin", "admin@example.test", "old-admin-password")
        self.staff = User.objects.create_user("helper", "helper@example.test", "old-staff-password", is_staff=True)
        self.creator = User.objects.create_user("creator", "creator@example.test", "old-creator-password")
        self.customer = Customer.objects.create(name="Test Creator")
        self.customer.members.add(self.creator)
        self.url = reverse("issue_password_recovery",args=[self.creator.pk])

    def issue(self, user=None):
        self.client.force_login(user or self.admin)
        response=self.client.post(self.url)
        self.assertEqual(response.status_code,200)
        self.assertContains(response,"No email was sent")
        self.assertEqual(response["Cache-Control"].split(",")[0],"max-age=0")
        self.assertEqual(response["Referrer-Policy"],"no-referrer")
        return urlsplit(response.context["recovery_link"]).path

    def test_admin_link_resets_password_once_without_email_or_model_token(self):
        path=self.issue()
        self.assertEqual(AdminActionLog.objects.filter(action_type="password_reset_requested", target_user=self.creator).count(),1)
        self.assertEqual(self.creator.is_active,True)
        self.client.logout()
        redirect=self.client.get(path)
        self.assertEqual(redirect.status_code,302)
        form_path=redirect["Location"]
        self.assertIn("set-password",form_path)
        self.assertContains(self.client.get(form_path),"Choose a new password")
        done=self.client.post(form_path,{"new_password1":"strong-new-recovery-password","new_password2":"strong-new-recovery-password"})
        self.assertRedirects(done, reverse("recover_password_complete"))
        self.creator.refresh_from_db()
        self.assertTrue(self.creator.check_password("strong-new-recovery-password"))
        self.assertFalse(self.creator.check_password("old-creator-password"))
        self.assertContains(self.client.get(path),"invalid, expired or already used")
        self.client.logout()
        self.assertTrue(self.client.login(username="creator",password="strong-new-recovery-password"))
        log=AdminActionLog.objects.get(action_type="password_reset_requested",target_user=self.creator)
        self.assertNotIn(path,log.details)

    def test_only_authenticated_staff_can_issue_and_only_superuser_for_staff(self):
        self.assertEqual(self.client.post(self.url).status_code,302)
        self.client.force_login(self.creator)
        self.assertEqual(self.client.post(self.url).status_code,403)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.post(self.url).status_code,200)
        self.assertEqual(self.client.post(reverse("issue_password_recovery",args=[self.admin.pk])).status_code,403)
        self.assertEqual(self.client.post(reverse("issue_password_recovery",args=[self.staff.pk])).status_code,403)
        self.assertEqual(AdminActionLog.objects.filter(action_type="password_reset_requested").count(),1)

    def test_issuance_requires_post_and_csrf_and_cannot_target_disabled_account(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.url).status_code,405)
        self.creator.is_active=False
        self.creator.save(update_fields=["is_active"])
        self.assertEqual(self.client.post(self.url).status_code,400)
        self.assertEqual(AdminActionLog.objects.count(),0)

        csrf_client=Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.admin)
        csrf_client.get("/accounts/")
        self.assertEqual(csrf_client.post(reverse("issue_password_recovery",args=[self.staff.pk])).status_code,403)

    def test_expired_token_cannot_open_reset_form(self):
        path=self.issue()
        with patch.object(default_token_generator,"_now",return_value=datetime.now()+timedelta(hours=2)):
            result=self.client.get(path,follow=True)
        self.assertContains(result,"invalid, expired or already used")

    def test_self_service_email_reset_remains_explicitly_unavailable(self):
        response=self.client.get(reverse("request_password_reset"))
        self.assertEqual(response.status_code,503)
        self.assertContains(response,"not available",status_code=503)
