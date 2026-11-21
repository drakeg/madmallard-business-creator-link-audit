"""First organization and project onboarding without dead-end controls."""
from django.contrib.auth.models import User
from django.test import TestCase

from .models import Customer, Project


class EmptyWorkspaceOnboardingTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("admin", "admin@example.test", "long-test-password")

    def test_empty_admin_dashboard_guides_first_organization(self):
        self.client.force_login(self.admin)
        response=self.client.get("/")
        self.assertEqual(response.status_code,200)
        self.assertContains(response,"Create a customer organization first")
        self.assertNotContains(response,'id="customer-select"')
        self.assertNotContains(response,'action="/projects/new/"')
        self.assertEqual(Project.objects.count(),0)

    def test_nonstaff_without_membership_receives_admin_guidance(self):
        user=User.objects.create_user("creator",password="long-test-password")
        self.client.force_login(user)
        response=self.client.get("/")
        self.assertContains(response,"Ask an administrator to add your account")
        self.assertNotContains(response,"Create a customer organization first")
        self.assertNotContains(response,'id="customer-select"')

    def test_first_customer_restores_project_creation_form(self):
        self.client.force_login(self.admin)
        customer=Customer.objects.create(name="New Test Client")
        response=self.client.get("/")
        self.assertContains(response,'id="customer-select"')
        self.assertContains(response,"New Test Client")
        self.assertNotContains(response,"Create a customer organization first")
        created=self.client.post("/projects/new/",{"customer":customer.pk,"name":"Pilot One"})
        self.assertEqual(created.status_code,302)
        self.assertEqual(Project.objects.count(),1)

    def test_accounts_page_uses_semantically_nested_sections(self):
        self.client.force_login(self.admin)
        response=self.client.get("/accounts/")
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'<section class="card" aria-labelledby="orgs-heading">',html=False)
        self.assertContains(response,"Create organization")
