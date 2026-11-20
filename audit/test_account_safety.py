from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from .models import Customer,AccountResetToken,UserMFA,AccountInvitation,AdminActionLog


class AccountSafetyTests(TestCase):
    def setUp(self):
        self.admin=User.objects.create_superuser("operator","operator@example.test","test-password-long")
        self.member=User.objects.create_user("member","member@example.test","test-password-long")
        self.customer=Customer.objects.create(name="Example Client")
        self.customer.members.add(self.member)

    def test_unimplemented_recovery_is_explicit_and_creates_no_tokens(self):
        for method in ("get","post"):
            response=getattr(self.client,method)(reverse("request_password_reset"),{"email":"member@example.test"})
            self.assertEqual(response.status_code,503)
        self.assertEqual(AccountResetToken.objects.count(),0)

    def test_mfa_cannot_be_claimed_or_enabled_without_login_enforcement(self):
        self.client.force_login(self.member)
        response=self.client.post(reverse("setup_mfa"),{"totp_secret":"abcdefghijklmnop"})
        self.assertEqual(response.status_code,503)
        self.assertFalse(UserMFA.objects.filter(user=self.member,enabled=True).exists())

    def test_invitation_not_falsely_sent_or_created(self):
        self.client.force_login(self.admin)
        url=reverse("send_invitation",args=[self.customer.pk])
        response=self.client.post(url,{"email":"new@example.test"})
        self.assertEqual(response.status_code,503)
        self.assertEqual(AccountInvitation.objects.count(),0)

    def test_account_status_blocks_password_login(self):
        self.client.force_login(self.admin)
        url=reverse("manage_account_status",args=[self.member.pk])
        response=self.client.post(url,{"status":"disabled","disabled_reason":"Admin testing"})
        self.assertEqual(response.status_code,302)
        self.member.refresh_from_db()
        self.assertFalse(self.member.is_active)
        self.client.logout()
        response=self.client.post("/login/",{"username":"member","password":"test-password-long"})
        self.assertEqual(response.status_code,200)
        self.assertNotIn("_auth_user_id",self.client.session)

    def test_admin_cannot_disable_self(self):
        self.client.force_login(self.admin)
        response=self.client.post(reverse("manage_account_status",args=[self.admin.pk]),{"status":"disabled"})
        self.assertEqual(response.status_code,200)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_member_add_never_creates_fake_account(self):
        self.client.force_login(self.admin)
        response=self.client.post(reverse("add_member",args=[self.customer.pk]),{"username":"not-a-user"})
        self.assertEqual(response.status_code,302)
        self.assertFalse(User.objects.filter(username="not-a-user").exists())
        self.assertFalse(AdminActionLog.objects.filter(action_type="membership_added").exists())

    def test_invitation_revoke_is_customer_scoped(self):
        other=Customer.objects.create(name="Other")
        invitation=AccountInvitation.objects.create(customer=other,email="other@example.test",expires_at="2030-01-01T00:00:00Z")
        self.client.force_login(self.admin)
        response=self.client.post(reverse("revoke_invitation",args=[self.customer.pk,invitation.token]))
        self.assertEqual(response.status_code,404)
        invitation.refresh_from_db()
        self.assertEqual(invitation.status,"pending")
