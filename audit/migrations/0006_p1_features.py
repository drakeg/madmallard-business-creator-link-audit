# Generated migration for P1 features: invitations, MFA, account management, admin audit trail
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('audit', '0005_discountcode'),
        ('auth', '0012_alter_user_first_name_max_length'),  # Latest auth migration
    ]

    operations = [
        # AccountInvitation model
        migrations.CreateModel(
            name='AccountInvitation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=False, serialize=False)),
                ('token', models.UUIDField(default=django.db.models.deletion.CASCADE, editable=False, primary_key=True, serialize=False)),
                ('email', models.EmailField(max_length=254)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('accepted', 'Accepted'), ('expired', 'Expired'), ('revoked', 'Revoked')], default='pending', max_length=16)),
                ('invited_by', models.CharField(blank=True, max_length=150)),
                ('invited_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField(db_index=True)),
                ('accepted_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'ordering': ['-invited_at'],
                'constraints': [models.UniqueConstraint(fields=['customer', 'email'], name='unique_customer_email')],
            },
        ),
        
        # AccountResetToken model
        migrations.CreateModel(
            name='AccountResetToken',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=False, serialize=False)),
                ('token', models.UUIDField(default=django.db.models.deletion.CASCADE, editable=False, primary_key=True, serialize=False)),
                ('email', models.EmailField(max_length=254)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('completed', 'Completed'), ('expired', 'Expired')], default='pending', max_length=16)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField(db_index=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        
        # AdminActionLog model
        migrations.CreateModel(
            name='AdminActionLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=False, serialize=False)),
                ('action_type', models.CharField(choices=[('user_created', 'User Created'), ('user_disabled', 'User Disabled'), ('membership_added', 'Membership Added'), ('membership_removed', 'Membership Removed'), ('invitation_sent', 'Invitation Sent'), ('password_reset_requested', 'Password Reset Requested'), ('role_changed', 'Role Changed'), ('data_exported', 'Data Exported'), ('settings_changed', 'Settings Changed')], max_length=32)),
                ('details', models.TextField()),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.CharField(blank=True, max_length=500)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('performed_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='admin_actions', to=settings.AUTH_USER_MODEL)),
                ('target_customer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='audit.customer')),
                ('target_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='target_admin_actions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'indexes': [models.Index(fields=['action_type', 'created_at'])],
                'ordering': ['-created_at'],
            },
        ),
        
        # UserMFA model
        migrations.CreateModel(
            name='UserMFA',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=False, serialize=False)),
                ('enabled', models.BooleanField(default=False)),
                ('secret_key', models.CharField(blank=True, max_length=128)),
                ('backup_codes', models.JSONField(blank=True, default=list)),
                ('last_verified_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='mfa', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        
        # AccountStatus model
        migrations.CreateModel(
            name='AccountStatus',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=False, serialize=False)),
                ('status', models.CharField(choices=[('active', 'Active'), ('disabled', 'Disabled - pending review'), ('suspended', 'Suspended - policy violation'), ('locked', 'Locked - too many failed attempts')], default='active', max_length=16)),
                ('disabled_reason', models.TextField(blank=True)),
                ('locked_until', models.DateTimeField(blank=True, null=True)),
                ('flagged_by_admin', models.BooleanField(default=False)),
                ('flagged_at', models.DateTimeField(blank=True, null=True)),
                ('flagged_by', models.CharField(blank=True, max_length=150)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='account_status', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-flagged_at'],
            },
        ),
        
        # CustomerMembership model
        migrations.CreateModel(
            name='CustomerMembership',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=False, serialize=False)),
                ('action', models.CharField(choices=[('added', 'Added'), ('removed', 'Removed')], max_length=32)),
                ('details', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='membership_history', to='audit.customer')),
                ('performed_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='membership_changes', to=settings.AUTH_USER_MODEL)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
                'unique_together': {('customer', 'user')},
            },
        ),
        
        # Add foreign key from AccountInvitation to Customer
        migrations.AddField(
            model_name='accountinvitation',
            name='customer',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='invitations', to='audit.customer'),
        ),
    ]

<EOF>