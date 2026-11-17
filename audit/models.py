import uuid
from datetime import timedelta
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class AccountInvitation(models.Model):
    """Email invitation for new account creation."""
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('expired', 'Expired'),
        ('revoked', 'Revoked'),
    )
    
    customer = models.ForeignKey('Customer', on_delete=models.CASCADE, related_name='invitations')
    email = models.EmailField(max_length=254)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='pending')
    invited_by = models.CharField(max_length=150, blank=True)  # Admin username
    invited_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    token = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    class Meta:
        ordering = ['-invited_at']
        constraints = [models.UniqueConstraint(fields='customer', 'email', name='unique_customer_email')]
    
    def __str__(self):
        return f"Invitation to {self.email} for {self.customer.name}"
    
    @property
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    def accept_invitation(self, password):
        """Accept invitation and create account."""
        if self.status != 'pending' or self.is_expired:
            raise ValueError("Invitation not available")
        
        # Create user with provided password
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user, created = User.objects.get_or_create(username=self.email.split('@')[0], defaults={'email': self.email})
        if created:
            user.set_password(password)
        
        # Add to customer members
        self.customer.members.add(user)
        
        # Update invitation status
        self.status = 'accepted'
        self.accepted_at = timezone.now()
        self.save()
        
        return user


class AccountResetToken(models.Model):
    """Password reset token for account recovery."""
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('expired', 'Expired'),
    )
    
    email = models.EmailField(max_length=254)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='pending')
    token = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Reset token for {self.email}"
    
    @property
    def is_expired(self):
        return timezone.now() > self.expires_at


class AdminActionLog(models.Model):
    """Audit trail for administrative actions."""
    ACTION_TYPES = (
        ('user_created', 'User Created'),
        ('user_disabled', 'User Disabled'),
        ('membership_added', 'Membership Added'),
        ('membership_removed', 'Membership Removed'),
        ('invitation_sent', 'Invitation Sent'),
        ('password_reset_requested', 'Password Reset Requested'),
        ('role_changed', 'Role Changed'),
        ('data_exported', 'Data Exported'),
        ('settings_changed', 'Settings Changed'),
    )
    
    action_type = models.CharField(max_length=32, choices=ACTION_TYPES)
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='admin_actions')
    target_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='target_admin_actions')
    target_customer = models.ForeignKey('Customer', on_delete=models.SET_NULL, null=True, blank=True)
    details = models.TextField()
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['action_type', 'created_at'])]
    
    def __str__(self):
        return f"{self.action_type} by {self.performed_by.username}"


class UserMFA(models.Model):
    """Multi-Factor Authentication settings for users."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='mfa')
    enabled = models.BooleanField(default=False)
    secret_key = models.CharField(max_length=128, blank=True)  # TOTP secret
    backup_codes = models.JSONField(blank=True, default=list)  # One-time use backup codes
    last_verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"MFA for {self.user.username}"


class AccountStatus(models.Model):
    """Track account status and disable reasons."""
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('disabled', 'Disabled - pending review'),
        ('suspended', 'Suspended - policy violation'),
        ('locked', 'Locked - too many failed attempts'),
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='account_status')
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='active')
    disabled_reason = models.TextField(blank=True)
    locked_until = models.DateTimeField(null=True, blank=True)
    flagged_by_admin = models.BooleanField(default=False)
    flagged_at = models.DateTimeField(null=True, blank=True)
    flagged_by = models.CharField(max_length=150, blank=True)  # Admin username
    
    class Meta:
        ordering = ['-flagged_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.get_status_display()}"


class CustomerMembership(models.Model):
    """Track customer membership changes for audit."""
    customer = models.ForeignKey('Customer', on_delete=models.CASCADE, related_name='membership_history')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=32, choices=(
        ('added', 'Added'),
        ('removed', 'Removed'),
    ))
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='membership_changes')
    details = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['customer', 'user']
    
    def __str__(self):
        return f"{self.user.username} {'added' if self.action == 'added' else 'removed'} from {self.customer.name}"


class YouTubePreview(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    project=models.ForeignKey('Project',on_delete=models.CASCADE)
    user=models.ForeignKey(User,on_delete=models.CASCADE)
    payload=models.JSONField(default=dict)
    expires_at=models.DateTimeField(db_index=True)
<EOF>