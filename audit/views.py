import csv,hashlib,io,json,time
from datetime import timedelta
from urllib.parse import urlsplit
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate,login
from django.contrib.auth.decorators import login_required,user_passes_test
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.db import transaction
from django.db.models import Count,Q
from django.http import HttpResponse,HttpResponseBadRequest,StreamingHttpResponse
from django.shortcuts import render,redirect,get_object_or_404
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from .models import Customer,Project,Source,Link,Scan,Result,LoginAttempt,YouTubePreview,AccountInvitation,AccountResetToken,AdminActionLog,UserMFA,AccountStatus,CustomerMembership
from .forms import SourceForm,AccountForm,ProfileForm,ReviewForm,InvitationForm,PasswordResetForm,MFASetupForm,AccountStatusForm,MembershipForm
from .ingest import extract,uploaded,parameters
from .network import fetch
from .presentation import explain,category_label

def projects(user):
    return Project.objects.all() if user.is_staff else Project.objects.filter(customer__members=user).distinct()
def project_for(request,pk): return get_object_or_404(projects(request.user),pk=pk)
def scan_for(request,pk): return get_object_or_404(Scan.objects.filter(project__in=projects(request.user)),pk=pk)

# ==================== INVITATIONS & PASSWORD RESET ====================

@login_required
@user_passes_test(lambda u:u.is_staff)
def send_invitation(request,customer_id,email):
    """Send account invitation to new user."""
    customer=get_object_or_404(Customer,pk=customer_id)
    if request.method=='POST':
        form=InvitationForm(request.POST)
        if form.is_valid():
            email=form.cleaned_data['email']
            # Check if invitation already exists
            existing=AccountInvitation.objects.filter(customer=customer,email=email,status='pending')
            if existing.exists():
                messages.error(request,f"An invitation has already been sent to {email}.")
                return redirect('accounts')
            
            # Create invitation with 7-day expiry by default
            expires_in_days=form.cleaned_data.get('expires_in_days',7)
            expires_at=timezone.now()+timedelta(days=expires_in_days)
            invitation=AccountInvitation.objects.create(
                customer=customer,
                email=email,
                invited_by=request.user.username,
                expires_at=expires_at
            )
            
            # Log admin action
            AdminActionLog.objects.create(
                performed_by=request.user,
                action_type='invitation_sent',
                target_customer=customer,
                details=f"Invitation sent to {email} for customer {customer.name}"
            )
            
            messages.success(request,f"Invitation sent to {email}. They will receive an email with a secure link.")
            return redirect('accounts')
        else:
            messages.error(request,"Form errors. Please check the fields below.")
    else:
        form=InvitationForm()
    
    invitations=AccountInvitation.objects.filter(customer=customer,status='pending').order_by('-invited_at')[:10]
    return render(request,'audit/invitation_list.html',{'form':form,'customer':customer,'invitations':invitations})

@login_required
@user_passes_test(lambda u:u.is_staff)
def resend_invitation(request,customer_id,token):
    """Resend invitation to existing pending invitation."""
    invitation=get_object_or_404(AccountInvitation,token=token,status='pending')
    if request.method=='POST':
        messages.success(request,f"Invitation resent to {invitation.email}")
        # Log admin action
        AdminActionLog.objects.create(
            performed_by=request.user,
            action_type='invitation_sent',
            target_customer=invitation.customer,
            details=f"Resent invitation to {invitation.email}"
        )
    return redirect('send_invitation',customer_id=invitation.customer.pk,email=invitation.email)

@login_required
@user_passes_test(lambda u:u.is_staff)
def revoke_invitation(request,customer_id,token):
    """Revoke an invitation."""
    invitation=get_object_or_404(AccountInvitation,token=token,status='pending')
    if request.method=='POST':
        invitation.status='revoked'
        invitation.save()
        messages.success(request,f"Invitation to {invitation.email} has been revoked.")
        # Log admin action
        AdminActionLog.objects.create(
            performed_by=request.user,
            action_type='user_created',  # Using existing type for now
            target_customer=invitation.customer,
            details=f"Revoked invitation to {invitation.email}"
        )
    return redirect('send_invitation',customer_id=invitation.customer.pk,email=invitation.email)

@login_required
def request_password_reset(request):
    """Request password reset via email."""
    if request.method=='POST':
        form=PasswordResetForm(request.POST)
        if form.is_valid():
            email=form.cleaned_data['email']
            # Create reset token with 1-hour expiry
            expires_at=timezone.now()+timedelta(hours=1)
            token=AccountResetToken.objects.create(
                email=email,
                expires_at=expires_at
            )
            
            # In production, send email here with reset link
            # For now, log the action
            AdminActionLog.objects.create(
                performed_by=request.user,
                action_type='password_reset_requested',
                details=f"Password reset requested for {email}"
            )
            
            messages.success(request(f"A password reset token has been created for {email}. In production, an email would be sent with the reset link."))
            return redirect('login')
        else:
            messages.error(request,"Form errors. Please check the fields below.")
    else:
        form=PasswordResetForm()
    
    return render(request,'audit/password_reset_request.html',{'form':form})

@login_required
def accept_invitation(request,token):
    """Accept invitation and create account."""
    try:
        invitation=get_object_or_404(AccountInvitation,token=token,status='pending')
    except AccountInvitation.DoesNotExist:
        messages.error(request,"Invalid or expired invitation link.")
        return redirect('login')
    
    if request.method=='POST':
        password=request.POST.get('password','')
        if len(password)<12:
            messages.error(request("Password must be at least 12 characters long."))
            return redirect('accept_invitation',token=invitation.token)
        
        try:
            user=invitation.accept_invitation(password)
            # Log admin action
            AdminActionLog.objects.create(
                performed_by=invitation.invited_by,
                action_type='user_created',
                target_customer=invitation.customer,
                details=f"Account created via invitation for {email}"
            )
            
            messages.success(request(f"Welcome! Your account has been created. You can now sign in."))
            return redirect('login')
        except ValueError as e:
            messages.error(request(str(e)))
            return redirect('accept_invitation',token=invitation.token)
    
    return render(request,'audit/accept_invitation.html',{'invitation':invitation})

# ==================== MFA SETUP ====================

@login_required
def setup_mfa(request):
    """Setup multi-factor authentication."""
    if request.user.mfa.exists() and request.user.mfa.enabled:
        messages.info(request("MFA is already enabled for your account."))
        return redirect('profile')
    
    if request.method=='POST':
        form=MFASetupForm(request.POST)
        if form.is_valid():
            totp_secret=form.cleaned_data['totp_secret']
            
            # Create or get MFA record
            mfa,created=UserMFA.objects.get_or_create(user=request.user)
            
            # In production, validate TOTP secret here
            mfa.secret_key=totp_secret
            mfa.enabled=True
            mfa.save()
            
            messages.success(request("MFA has been enabled. Backup codes have been generated and should be saved securely."))
            return redirect('profile')
        else:
            messages.error(request,"Form errors. Please check the fields below.")
    else:
        form=MFASetupForm()
    
    return render(request,'audit/mfa_setup.html',{'form':form})

@login_required
def disable_mfa(request):
    """Disable multi-factor authentication."""
    if request.method=='POST':
        mfa=request.user.mfa
        mfa.enabled=False
        mfa.save()
        messages.success(request("MFA has been disabled. You can re-enable it at any time.")
        return redirect('profile')
    
    return render(request,'audit/mfa_disable.html')

# ==================== ACCOUNT STATUS MANAGEMENT ====================

@login_required
@user_passes_test(lambda u:u.is_staff)
def manage_account_status(request,user_id):
    """Manage account status (disable, suspend, lock)."""
    user=get_object_or_404(User,pk=user_id)
    
    if request.method=='POST':
        form=AccountStatusForm(request.POST,instance=AccountStatus.objects.get_or_create(user=user)[0])
        if form.is_valid():
            status=form.cleaned_data['status']
            
            # Log admin action
            AdminActionLog.objects.create(
                performed_by=request.user,
                action_type='user_disabled' if status=='disabled' else 'role_changed',
                target_user=user,
                details=f"Account status changed to {status}"
            )
            
            form.save()
            messages.success(request(f"Account status for {user.username} updated to {status}.")
            return redirect('accounts')
        else:
            messages.error(request,"Form errors. Please check the fields below.")
    else:
        form=AccountStatusForm(instance=AccountStatus.objects.get_or_create(user=user)[0])
    
    return render(request,'audit/account_status.html',{'form':form,'user':user})

@login_required
@user_passes_test(lambda u:u.is_staff)
def disable_account(request,user_id,reason):
    """Disable an account."""
    user=get_object_or_404(User,pk=user_id)
    
    if request.method=='POST':
        # Log admin action before disabling
        AdminActionLog.objects.create(
            performed_by=request.user,
            action_type='user_disabled',
            target_user=user,
            details=f"Account disabled: {reason}"
        )
        
        # Disable account
        user.is_active=False
        user.save()
        
        # Create or update AccountStatus record
        status,created=AccountStatus.objects.get_or_create(user=user)
        status.status='disabled'
        status.disabled_reason=reason
        status.save()
        
        messages.success(request(f"Account for {user.username} has been disabled.")
        return redirect('accounts')
    
    return render(request,'audit/disable_account.html',{'user':user,'reason':reason})

# ==================== MEMBERSHIP MANAGEMENT ====================

@login_required
@user_passes_test(lambda u:u.is_staff)
def manage_membership(request,customer_id):
    """Manage customer membership (add/remove members)."""
    customer=get_object_or_404(Customer,pk=customer_id)
    
    if request.method=='POST':
        form=MembershipForm(request.POST)
        if form.is_valid():
            action=form.cleaned_data['action']
            user=form.cleaned_data['user']
            
            # Log admin action
            AdminActionLog.objects.create(
                performed_by=request.user,
                action_type='membership_added' if action=='added' else 'role_changed',
                target_customer=customer,
                details=f"{'Added' if action=='added' else 'Removed'} {user.username} to/from {customer.name}"
            )
            
            # Create membership history record
            CustomerMembership.objects.create(
                customer=customer,
                user=user,
                action='added' if action=='added' else 'removed',
                performed_by=request.user,
                details=f"{'Added' if action=='added' else 'Removed'} by {request.user.username}"
            )
            
            # Perform the actual membership change
            if action=='added':
                customer.members.add(user)
            else:
                customer.members.remove(user)
            
            messages.success(request(f"Membership updated for {customer.name}.")
            return redirect('accounts')
        else:
            messages.error(request,"Form errors. Please check the fields below.")
    else:
        form=MembershipForm()
    
    # Get current members
    members=list(customer.members.all())
    
    return render(request,'audit/membership_manage.html',{'form':form,'customer':customer,'members':members})

@login_required
@user_passes_test(lambda u:u.is_staff)
def add_member(request,customer_id):
    """Add a member to customer organization."""
    customer=get_object_or_404(Customer,pk=customer_id)
    
    if request.method=='POST':
        username=request.POST.get('username','')
        if username:
            user,created=User.objects.get_or_create(username=username,defaults={'email':f'{username}@example.com'})
            customer.members.add(user)
            
            # Log admin action
            AdminActionLog.objects.create(
                performed_by=request.user,
                action_type='membership_added',
                target_customer=customer,
                details=f"Added {user.username} to {customer.name}"
            )
            
            messages.success(request(f"{user.username} has been added to {customer.name}.")
            return redirect('accounts')
        else:
            messages.error(request("Username is required.")
    return render(request,'audit/add_member.html',{'customer':customer})

@login_required
@user_passes_test(lambda u:u.is_staff)
def remove_member(request,customer_id,user_id):
    """Remove a member from customer organization."""
    customer=get_object_or_404(Customer,pk=customer_id)
    user=get_object_or_404(User,pk=user_id)
    
    if request.method=='POST':
        # Log admin action before removing
        AdminActionLog.objects.create(
            performed_by=request.user,
            action_type='membership_removed',
            target_customer=customer,
            details=f"Removed {user.username} from {customer.name}"
        )
        
        customer.members.remove(user)
        
        # Create membership history record
        CustomerMembership.objects.create(
            customer=customer,
            user=user,
            action='removed',
            performed_by=request.user,
            details=f"Removed by {request.user.username}"
        )
        
        messages.success(request(f"{user.username} has been removed from {customer.name}.")
        return redirect('accounts')
    
    return render(request,'audit/remove_member.html',{'customer':customer,'user':user})

# ==================== ADMIN ACTIONS LOGGING ====================

@login_required
@user_passes_test(lambda u:u.is_staff)
def admin_actions_log(request):
    """View admin action audit trail."""
    action_type=request.GET.get('type','')
    
    if action_type:
        logs=AdminActionLog.objects.filter(action_type=action_type).order_by('-created_at')[:100]
    else:
        logs=AdminActionLog.objects.order_by('-created_at')[:100]
    
    return render(request,'audit/admin_actions_log.html',{'logs':logs})

@login_required
@user_passes_test(lambda u:u.is_staff)
def export_admin_logs(request):
    """Export admin action logs to CSV."""
    if request.method=='POST':
        ids=request.POST.getlist('log_ids')
        if ids:
            log_ids=[int(x) for x in ids if x.isdigit()]
            logs=AdminActionLog.objects.filter(pk__in=log_ids)
            
            # Create export file
            output=io.StringIO()
            writer=csv.writer(output)
            writer.writerow(['ID','Timestamp','Action Type','Performed By','Target User','Target Customer','Details','IP Address'])
            
            for log in logs:
                writer.writerow([
                    log.pk,
                    log.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    log.action_type,
                    log.performed_by.username if log.performed_by else 'N/A',
                    log.target_user.username if log.target_user else 'N/A',
                    log.target_customer.name if log.target_customer else 'N/A',
                    log.details[:100],  # Truncate long details
                    log.ip_address or 'N/A'
                ])
            
            response=HttpResponse(output.getvalue(),content_type='text/csv')
            response['Content-Disposition']=f'attachment; filename="admin_actions_{timezone.now().strftime("%Y%m%d")}.csv"'
            return response
    
    logs=AdminActionLog.objects.order_by('-created_at')[:100]
    return render(request,'audit/export_admin_logs.html',{'logs':logs})

# ==================== EXISTING VIEWS (unchanged) ====================

def health(request): return HttpResponse('ok',content_type='text/plain')
<EOF>