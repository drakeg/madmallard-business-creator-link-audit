"""Django 5.2 logout requires POST; a navigation anchor must not lead to 405."""
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse


class LogoutWorkflowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("sample", password="sample-strong-password")

    def test_authenticated_header_has_post_logout_form_with_csrf(self):
        self.client.force_login(self.user)
        html=self.client.get("/").content.decode()
        self.assertIn('method="post" action="/logout/"',html)
        self.assertIn('name="csrfmiddlewaretoken"',html)
        self.assertNotIn('href="/logout/"',html)

    def test_signed_in_user_can_log_out_and_cannot_access_dashboard(self):
        self.client.force_login(self.user)
        response=self.client.post(reverse("logout"))
        self.assertRedirects(response, reverse("login"))
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertRedirects(self.client.get("/"), "/login/?next=/")

    def test_logout_rejects_get_and_cross_site_post(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("logout")).status_code,405)
        self.assertIn("_auth_user_id", self.client.session)
        strict=Client(enforce_csrf_checks=True)
        strict.force_login(self.user)
        self.assertEqual(strict.post(reverse("logout")).status_code,403)
        self.assertIn("_auth_user_id",strict.session)
