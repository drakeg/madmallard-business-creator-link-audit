import re
from django import forms
from django.contrib.auth.forms import UserCreationForm,PasswordChangeForm
from django.contrib.auth.models import User
from .models import DiscountCode,Source,Customer, AccountInvitation, AccountResetToken, AdminActionLog, UserMFA, AccountStatus, CustomerMembership


class SourceForm(forms.Form):
    title=forms.CharField(max_length=200,required=False)
    original_url=forms.URLField(required=False,label='Original source URL (optional)')
    content=forms.CharField(widget=forms.Textarea(attrs={'rows':7}),required=False,label='Description or blog content')
    discount_codes=forms.CharField(required=False,widget=forms.Textarea(attrs={'rows':2}),label='Discount codes mentioned (unverified; one per line)')
    file=forms.FileField(required=False,label='CSV, Markdown or HTML (UTF-8, max 1 MB)')
    retrieve=forms.BooleanField(required=False,label='Retrieve the public source URL instead of pasting content')
    authorized=forms.BooleanField(label='I own this content or have permission to submit it')


class AccountForm(UserCreationForm):
    customer=forms.ModelChoiceField(queryset=Customer.objects.all(),required=False,empty_label="Select a customer")
    administrator=forms.BooleanField(required=False)

    class Meta:
        model=User
        fields=['username','email','first_name','last_name','customer','administrator']


class ProfileForm(forms.ModelForm):
    class Meta:
        model=User
        fields=['first_name','last_name','email']


class ReviewForm(forms.Form):
    manual_status=forms.ChoiceField(choices=[('unreviewed','Unreviewed'),('wrong_destination','Wrong destination reported / incorrect product'),('needs_owner','Needs owner decision'),('destination_verified','Destination/product manually verified'),('discount_unverified','Discount code unverified'),('discount_verified','Discount code manually verified'),('replacement_proposed','Replacement proposed')])
    notes=forms.CharField(required=False,widget=forms.Textarea)
    replacement=forms.URLField(required=False,label='Proposed replacement URL (never published)')


class InvitationForm(forms.Form):
    """Form for sending account invitations."""
    email = forms.EmailField(max_length=254, required=True, label="Email address to invite")
    customer = forms.ModelChoiceField(queryset=Customer.objects.all(), required=True, empty_label="Select a customer")
    expires_in_days = forms.IntegerField(required=False, initial=7, min_value=1, max_value=365, label="Invitation expiry (days)")

    def clean_email(self):
        email = self.cleaned_data['email']
        # Check if invitation already exists for this customer and email
        existing = AccountInvitation.objects.filter(customer=self.instance.customer, email=email)
        if existing.exists():
            raise forms.ValidationError(f"An invitation has already been sent to {email} for this customer.")
        return email


class PasswordResetForm(forms.Form):
    """Form for requesting password reset."""
    email = forms.EmailField(max_length=254, required=True, label="Email address")

    def clean_email(self):
        email = self.cleaned_data['email']
        # Check if reset token already exists
        existing = AccountResetToken.objects.filter(email=email)
        if existing.exists():
            raise forms.ValidationError(f"A password reset request has already been made for {email}. Please check your email.")
        return email


class MFASetupForm(forms.Form):
    """Form for setting up MFA."""
    totp_secret = forms.CharField(max_length=128, required=True, label="TOTP Secret Key (from authenticator app)")

    def clean_totp_secret(self):
        secret = self.cleaned_data['totp_secret']
        if len(secret) < 16:
            raise forms.ValidationError("Invalid TOTP secret. Please verify your setup.")
        return secret


class MFABackupCodesForm(forms.Form):
    """Form for generating backup codes."""
    pass  # Codes are generated server-side


class AccountStatusForm(forms.ModelForm):
    """Form for managing account status."""
    class Meta:
        model = AccountStatus
        fields = ['status', 'disabled_reason', 'locked_until']


class MembershipForm(forms.Form):
    """Form for adding/removing members from customer organizations."""
    action = forms.ChoiceField(choices=[('added', 'Add member'), ('removed', 'Remove member')])
    user = forms.ModelChoiceField(queryset=User.objects.all(), required=True, empty_label="Select a user")
    customer = forms.ModelChoiceField(queryset=Customer.objects.all(), required=True)

    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        user = cleaned_data.get('user')
        customer = cleaned_data.get('customer')

        # Prevent adding same user twice to same customer
        if action == 'added' and CustomerMembership.objects.filter(customer=customer, user=user).exists():
            raise forms.ValidationError(f"User {user.username} is already a member of {customer.name}.")

        return cleaned_data


class AdminActionForm(forms.ModelForm):
    """Form for logging admin actions (internal use)."""
    class Meta:
        model = AdminActionLog
        fields = ['action_type', 'details']

class DiscountCodeForm(forms.Form):
    code=forms.CharField(max_length=80,label='Discount code')
    merchant_url=forms.URLField(required=False,label='Merchant or product URL (optional)')
    source=forms.ModelChoiceField(queryset=Source.objects.none(),required=False,label='Mentioned in source (optional)')
    def __init__(self,*args,project=None,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['source'].queryset=project.sources.all() if project else Source.objects.none()
    def clean_code(self):
        value=self.cleaned_data['code'].strip()
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{1,39}',value):
            raise forms.ValidationError('Enter one code using letters, numbers, dots, underscores or hyphens.')
        return value

class DiscountCodeReviewForm(forms.Form):
    status=forms.ChoiceField(choices=DiscountCode.STATUS_CHOICES,label='Manual status')
    merchant_url=forms.URLField(required=False,label='Merchant or product URL')
    evidence=forms.CharField(required=False,widget=forms.Textarea(attrs={'rows':4}),label='Evidence and method')
    def clean(self):
        data=super().clean()
        if data.get('status') in ('verified','expired') and not (data.get('evidence') or '').strip():
            self.add_error('evidence','Record what you checked and how you checked it.')
        return data
