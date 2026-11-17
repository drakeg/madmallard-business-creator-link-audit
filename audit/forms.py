import re
from django import forms
from django.contrib.auth.forms import UserCreationForm,PasswordChangeForm
from django.contrib.auth.models import User
from .models import Customer,DiscountCode,Source
class SourceForm(forms.Form):
    title=forms.CharField(max_length=200,required=False)
    original_url=forms.URLField(required=False,label='Original source URL (optional)')
    content=forms.CharField(widget=forms.Textarea(attrs={'rows':7}),required=False,label='Description or blog content')
    discount_codes=forms.CharField(required=False,widget=forms.Textarea(attrs={'rows':2}),label='Discount codes mentioned (unverified; one per line)')
    file=forms.FileField(required=False,label='CSV, Markdown or HTML (UTF-8, max 1 MB)')
    retrieve=forms.BooleanField(required=False,label='Retrieve the public source URL instead of pasting content')
    authorized=forms.BooleanField(label='I own this content or have permission to submit it')
class AccountForm(UserCreationForm):
    customer=forms.ModelChoiceField(queryset=Customer.objects.all(),required=False)
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
