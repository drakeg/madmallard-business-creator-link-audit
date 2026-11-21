from django.urls import path
from django.contrib.auth.views import LogoutView, PasswordResetConfirmView, PasswordResetCompleteView
from django.urls import reverse_lazy
from audit import views, youtube_views, quick_views

urlpatterns=[
    path('projects/<int:pk>/codes/add/',views.add_discount_code,name='add_discount_code'),
    path('codes/<int:pk>/',views.discount_code,name='discount_code'),
    path('reports/<int:pk>/summary/',quick_views.quick_report,name='quick_report'),
    path('reports/<int:pk>/summary/export/',quick_views.export_unique_actions,name='export_unique_actions'),
    path('reports/<int:pk>/inspect/',quick_views.inspect_destinations,name='inspect_destinations'),
    path('reports/<int:pk>/unique/<int:result_id>/',quick_views.review_unique,name='review_unique'),

    # YouTube channel import (unchanged)
    path('projects/<int:pk>/youtube/results/',youtube_views.channel_results,name='youtube_results'),
    path('projects/<int:pk>/youtube/imported/',youtube_views.imported_descriptions,name='youtube_imported'),
    path('projects/<int:pk>/youtube/',youtube_views.channel_import,name='youtube_import'),
    path('projects/<int:pk>/youtube/delete/',youtube_views.delete_youtube,name='delete_youtube'),

    # Dashboard and main views (unchanged)
    path('',views.dashboard,name='dashboard'),
    path('health/',views.health),

    # Authentication (unchanged + new password reset)
    path('login/',views.login_view,name='login'),
    path('logout/',LogoutView.as_view(),name='logout'),
    path('password-reset-request/',views.request_password_reset,name='request_password_reset'),
    path('accounts/<int:user_id>/recovery-link/',views.issue_password_recovery,name='issue_password_recovery'),
    path('recover/<uidb64>/<token>/',PasswordResetConfirmView.as_view(
        template_name='audit/recovery_confirm.html',
        success_url=reverse_lazy('recover_password_complete')),name='recover_password'),
    path('recover/complete/',PasswordResetCompleteView.as_view(
        template_name='audit/recovery_complete.html'),name='recover_password_complete'),

    # Account invitations and management (NEW - P1 backlog item)
    path('accounts/invitations/<int:customer_id>/',views.send_invitation,name='send_invitation'),
    path('accounts/invitations/<int:customer_id>/resend/<uuid:token>/',views.resend_invitation,name='resend_invitation'),
    path('accounts/invitations/<int:customer_id>/revoke/<uuid:token>/',views.revoke_invitation,name='revoke_invitation'),

    # Accept invitation (NEW)
    path('accept-invite/<uuid:token>/',views.accept_invitation,name='accept_invitation'),

    # MFA setup (NEW - P1 backlog item)
    path('mfa/setup/',views.setup_mfa,name='setup_mfa'),
    path('mfa/disable/',views.disable_mfa,name='disable_mfa'),

    # Account status management (NEW - P1 backlog item)
    path('accounts/status/<int:user_id>/',views.manage_account_status,name='manage_account_status'),
    path('accounts/disable/<int:user_id>/<str:reason>/',views.disable_account,name='disable_account'),

    # Membership management (NEW - P1 backlog item)
    path('accounts/membership/<int:customer_id>/',views.manage_membership,name='manage_membership'),
    path('accounts/add-member/<int:customer_id>/',views.add_member,name='add_member'),
    path('accounts/remove-member/<int:customer_id>/<int:user_id>/',views.remove_member,name='remove_member'),

    # Admin actions audit trail (NEW - P1 backlog item)
    path('admin/logs/',views.admin_actions_log,name='admin_actions_log'),
    path('admin/logs/export/',views.export_admin_logs,name='export_admin_logs'),

    # Profile and accounts (unchanged)
    path('profile/',views.profile,name='profile'),
    path('accounts/',views.accounts,name='accounts'),

    # Project management (unchanged)
    path('projects/new/',views.create_project,name='create_project'),
    path('projects/<int:pk>/',views.project,name='project'),
    path('projects/<int:pk>/scan/',views.start_scan,name='start_scan'),
    path('projects/<int:pk>/delete/',views.delete_history,name='delete_history'),

    # Reports and reviews (unchanged)
    path('reports/<int:pk>/',views.report,name='report'),
    path('reports/<int:pk>/export/',views.export,name='export'),
    path('results/<int:pk>/review/',views.review,name='review'),
]
