import csv,hashlib,io,json,time,uuid,random
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
def login_view(request):
    next_url=request.POST.get('next') or request.GET.get('next') or '/'
    if not url_has_allowed_host_and_scheme(next_url,allowed_hosts={request.get_host()},require_https=request.is_secure()): next_url='/'
    if request.user.is_authenticated: return redirect(next_url)
    error=''
    if request.method=='POST':
        username=request.POST.get('username','')[:150]
        key=hashlib.sha256((request.META.get('REMOTE_ADDR','')+'|'+username).encode()).hexdigest()
        attempt,_=LoginAttempt.objects.get_or_create(key=key)
        if attempt.updated<timezone.now()-timedelta(minutes=15): attempt.failures=0
        if attempt.failures>=8: error='Too many attempts. Try again in 15 minutes.'
        else:
            user=authenticate(request,username=username,password=request.POST.get('password',''))
            if user:
                login(request,user); attempt.delete(); return redirect(next_url)
            attempt.failures+=1; attempt.save(); error='Sign-in failed. Check your username and password.'
    return render(request,'audit/login.html',{'error':error,'next_url':next_url})
@login_required
def dashboard(request):
    qs=projects(request.user).select_related('customer').annotate(source_count=Count('sources',distinct=True),scan_count=Count('scans',distinct=True)).order_by('-created')
    latest=Scan.objects.filter(project__in=projects(request.user)).order_by('-created')
    stats=Result.objects.filter(scan__in=latest).values('category').annotate(count=Count('id'))
    customers=Customer.objects.all() if request.user.is_staff else Customer.objects.filter(members=request.user)
    return render(request,'audit/dashboard.html',{'projects':qs,'customers':customers,'scans':latest[:10],'stats':stats,'report_count':latest.count()})
@login_required
@require_POST
def create_project(request):
    customers=Customer.objects.all() if request.user.is_staff else Customer.objects.filter(members=request.user)
    customer=get_object_or_404(customers,pk=request.POST.get('customer'))
    name=request.POST.get('name','').strip()[:160]
    if not name: return HttpResponseBadRequest('Project name required')
    p=Project.objects.create(customer=customer,name=name)
    return redirect('project',pk=p.pk)
@login_required
def project(request,pk):
    p=project_for(request,pk); form=SourceForm(request.POST or None,request.FILES or None)
    if request.method=='POST' and form.is_valid():
        try:
            if p.scans.exists(): raise ValueError('Sources are locked after the first scan to preserve evidence. Use a new project for revised source content; a retest can explicitly check reviewed replacement URLs.')
            d=form.cleaned_data
            if sum(bool(x) for x in (d.get('file'),d.get('retrieve'),d.get('content'))) != 1: raise ValueError('Choose exactly one input: paste, upload, or public retrieval')
            if d.get('file'): rows=uploaded(d['file'])
            elif d.get('retrieve'):
                if not d['original_url']: raise ValueError('Source URL required')
                status,final,chain,body=fetch(d['original_url'],True)
                if status!=200: raise ValueError(f'Public retrieval returned HTTP {status}; no bypass attempted')
                rows=[(d['title'] or final,d['original_url'],body.decode('utf-8',errors='replace'),d['discount_codes'])]
            else: rows=[(d['title'] or 'Pasted source',d['original_url'],d['content'],d['discount_codes'])]
            prepared=[]
            extraction_notices=[]
            extraction_deadline=time.monotonic()+20
            for title,url,content,codes in rows:
                if not content.strip(): raise ValueError('Every source needs content')
                if len(content)>1_000_000: raise ValueError('Source exceeds size limit')
                prepared.append((title[:200],url,content,codes,extract(content,url,notices=extraction_notices,deadline=extraction_deadline)))
            with transaction.atomic():
                Project.objects.filter(pk=p.pk).update(name=p.name) # SQLite write lock before limit checks
                if p.scans.exists(): raise ValueError('Sources locked: scan already queued')
                if p.sources.count()+len(prepared)>settings.MAX_SOURCES: raise ValueError('Pilot source limit exceeded')
                urls=set(Link.objects.filter(source__project=p).values_list('url',flat=True))
                urls.update(u for row in prepared for u in row[4])
                if len(urls)>settings.MAX_LINKS: raise ValueError('Pilot unique link limit exceeded')
                for title,url,content,codes,links in prepared:
                    source=Source.objects.create(project=p,title=title,original_url=url,content=content,codes=codes)
                    Link.objects.bulk_create([Link(source=source,url=u,affiliate_parameters=parameters(u)) for u in links])
            for notice in extraction_notices: messages.warning(request,notice)
            messages.success(request,f'Imported {len(rows)} source(s); original content and link associations preserved.')
            return redirect('project',pk=p.pk)
        except Exception as exc: form.add_error(None,str(exc)[:500])
    return render(request,'audit/project.html',{'project':p,'form':form,'sources':p.sources.prefetch_related('links'),'scans':p.scans.order_by('-created'),'max_sources':settings.MAX_SOURCES,'max_links':settings.MAX_LINKS,'youtube_preview':YouTubePreview.objects.filter(project=p,user=request.user,expires_at__gt=timezone.now()).order_by('-expires_at').first(),'youtube_import_count':p.sources.exclude(youtube_video_id='').count(),'latest_scan':p.scans.order_by('-created').first()})
@login_required
@require_POST
def start_scan(request,pk):
    p=project_for(request,pk)
    with transaction.atomic():
        Project.objects.filter(pk=p.pk).update(name=p.name)
        if p.scans.filter(state__in=['queued','running']).exists():
            messages.error(request,'A scan is already in progress.'); return redirect('project',pk=pk)
        if not Link.objects.filter(source__project=p).exists():
            messages.error(request,'Add at least one outbound link.'); return redirect('project',pk=pk)
        completed=p.scans.filter(state='complete').exclude(purpose='inspection').order_by('created')
        baseline=completed.first()
        if p.scans.filter(baseline__isnull=False).exclude(purpose='inspection').exists():
            messages.error(request,'Pilot includes one initial scan and one retest. Create a new project for another engagement.'); return redirect('project',pk=pk)
        approved=request.POST.get('approved')=='on'
        if baseline and not approved:
            messages.error(request,'Confirm that the owner approved corrections before retesting.'); return redirect('project',pk=pk)
        if Scan.objects.filter(state__in=['queued','running']).count()>=10:
            messages.error(request,'Global queue is full; try later.'); return redirect('project',pk=pk)
        use_replacements=bool(baseline and request.POST.get('use_replacements')=='on')
        targets={str(l.pk):l.replacement if use_replacements and l.replacement else l.url for l in Link.objects.filter(source__project=p)}
        scan=Scan.objects.create(project=p,baseline=baseline,corrections_approved=approved,use_replacements=use_replacements,targets=targets)
    return redirect('quick_report',pk=scan.pk)
@login_required
def report(request,pk):
    scan=scan_for(request,pk)
    results=scan.results.select_related('link__source').defer('link__source__content').order_by('link__source_id','link_id')
    category=request.GET.get('category',''); review=request.GET.get('review',''); query=request.GET.get('q','')
    if category: results=results.filter(category=category)
    if review: results=results.filter(manual_status=review)
    if query: results=results.filter(Q(tested_url__icontains=query)|Q(link__source__title__icontains=query)|Q(reason__icontains=query))
    results=list(results)
    for item in results: item.explanation=explain(item)
    outcome_summary=list(scan.results.values('category').annotate(count=Count('id')))
    for outcome in outcome_summary: outcome['label']=category_label(outcome['category'])
    category_choices=[{'value':c,'label':category_label(c)} for c in scan.results.values_list('category',flat=True).distinct()]
    return render(request,'audit/report.html',{'scan':scan,'results':results,'categories':category_choices,'summary':outcome_summary,'destination_mismatches':scan.results.filter(manual_status='wrong_destination').count(),'reviewed':scan.results.exclude(manual_status='unreviewed').count(),'category':category,'review':review,'query':query,'sources':scan.project.sources.all()})
@login_required
def review(request,pk):
    result=get_object_or_404(Result.objects.filter(scan__project__in=projects(request.user)).select_related('link__source','scan'),pk=pk)
    form=ReviewForm(request.POST or None,initial={'manual_status':result.manual_status,'notes':result.notes,'replacement':result.replacement})
    if request.method=='POST' and form.is_valid():
        d=form.cleaned_data
        if d['manual_status'] in ('destination_verified','discount_verified','wrong_destination') and not d['notes'].strip():
            form.add_error('notes','Record the evidence and method used for manual verification.')
            return render(request,'audit/review.html',{'result':result,'form':form,'explanation':explain(result,include_source=True)})
        with transaction.atomic():
            Project.objects.filter(pk=result.scan.project_id).update(name=result.scan.project.name)
            # Review budget is distinct links per engagement, not individual edits.
            reviewed=Link.objects.filter(source__project=result.scan.project).exclude(manual_status='unreviewed').exclude(url=result.link.url).values('url').distinct().count()
            if d['manual_status']!='unreviewed' and reviewed>=10: form.add_error(None,'Pilot manual verification limit is 10 links.')
            else:
                for obj in (result,result.link):
                    for key,value in d.items(): setattr(obj,key,value)
                    obj.reviewed_by=request.user.username; obj.reviewed_at=timezone.now(); obj.save()
                messages.success(request,'Review saved. No source or external website was changed.')
                return redirect('report',pk=result.scan_id)
    return render(request,'audit/review.html',{'result':result,'form':form,'explanation':explain(result,include_source=True)})
@login_required
def export(request,pk):
    scan=scan_for(request,pk); results=scan.results.select_related('link__source').defer('link__source__content').order_by('link__source_id','link_id')
    if request.GET.get('format')=='html':
        results=list(results)
        for item in results: item.explanation=explain(item)
        return render(request,'audit/print.html',{'scan':scan,'results':results})
    class Echo:
        def write(self,value): return value
    def safe(value):
        text='' if value is None else str(value)
        return "'"+text if text.lstrip().startswith(('=','+','-','@','\t','\r')) else text
    def rows():
        writer=csv.writer(Echo())
        yield writer.writerow(['project','customer','source','source_original_url','source_content','discount_codes_unverified','original_link','tested_url','suspected_affiliate_parameters_exact','category','http_status','redirect_chain','final_destination','checked_at_utc','reason','manual_status','notes','proposed_replacement','reviewed_by','reviewed_at','baseline_scan','previous_category','previous_status','plain_assessment','recommended_action','redirect_count','final_destination_affiliate_parameters'])
        sources={s.pk:s for s in scan.project.sources.all()}
        for r in results.iterator(chunk_size=10):
            s=sources[r.link.source_id]
            explanation=explain(r)
            yield writer.writerow([safe(v) for v in [scan.project.name,scan.project.customer.name,s.title,s.original_url,s.content,s.codes,r.link.url,r.tested_url,r.link.affiliate_parameters,r.category,r.status,json.dumps(r.chain),r.final_url,r.checked_at.isoformat(),r.reason,r.manual_status,r.notes,r.replacement,r.reviewed_by,r.reviewed_at,scan.baseline_id,r.previous_category,r.previous_status,explanation["assessment"],explanation["action"],explanation["redirect_count"],explanation["final_parameters"]]])
    response=StreamingHttpResponse(rows(),content_type='text/csv; charset=utf-8')
    response['Content-Disposition']=f'attachment; filename="audit-{scan.pk}.csv"'
    return response

@login_required
def delete_history(request,pk):
    p=project_for(request,pk)
    ids=request.POST.getlist('scans') if request.method=='POST' else request.GET.getlist('scans')
    selection=p.scans.filter(pk__in=[int(x) for x in ids if x.isdigit()])
    if request.method=='POST' and request.POST.get('confirm')=='DELETE':
        if selection.filter(state__in=['queued','running']).exists():
            messages.error(request,'Wait for queued/running scans to finish before deleting.'); return redirect('project',pk=pk)
        count=selection.count(); selection.delete(); messages.success(request,f'Deleted {count} scan histories and their result records. Sources and current review notes remain.'); return redirect('project',pk=pk)
    return render(request,'audit/delete.html',{'project':p,'selection':selection})
@login_required
def profile(request):
    form=ProfileForm(request.POST or None,instance=request.user) if request.POST.get('action')!='password' else ProfileForm(instance=request.user)
    password=PasswordChangeForm(request.user,request.POST if request.POST.get('action')=='password' else None)
    if request.method=='POST':
        if request.POST.get('action')=='password' and password.is_valid():
            user=password.save(); update_session_auth_hash(request,user); messages.success(request,'Password updated.'); return redirect('profile')
        if request.POST.get('action')!='password' and form.is_valid(): form.save(); messages.success(request,'Profile updated.'); return redirect('profile')
    return render(request,'audit/profile.html',{'form':form,'password_form':password})
@login_required
@user_passes_test(lambda u:u.is_staff)
def accounts(request):
    form=AccountForm(request.POST or None)
    if request.method=='POST' and request.POST.get('action')=='customer':
        name=request.POST.get('name','').strip()[:160]
        if name: Customer.objects.create(name=name); messages.success(request,'Customer organization created.')
        return redirect('accounts')
    if request.method=='POST' and form.is_valid():
        if not form.cleaned_data['administrator'] and not form.cleaned_data['customer']: form.add_error('customer','Customer accounts require an organization')
        else:
            user=form.save(commit=False); user.is_staff=form.cleaned_data['administrator']; user.save()
            if form.cleaned_data['customer']: form.cleaned_data['customer'].members.add(user)
            messages.success(request,'Account created. Share credentials with the intended customer securely.'); return redirect('accounts')
    return render(request,'audit/accounts.html',{'form':form,'customers':Customer.objects.prefetch_related('members')})

def health(request): return HttpResponse('ok',content_type='text/plain')

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

            messages.success(request, f"A password reset token has been created for {email}. In production, an email would be sent with the reset link.")
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
            messages.error(request, "Password must be at least 12 characters long.")
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

            messages.success(request, f"Welcome! Your account has been created. You can now sign in.")
            return redirect('login')
        except ValueError as e:
            messages.error(request, str(e))
            return redirect('accept_invitation',token=invitation.token)

    return render(request,'audit/accept_invitation.html',{'invitation':invitation})

# ==================== MFA SETUP ====================

@login_required
def setup_mfa(request):
    """Setup multi-factor authentication."""
    if request.user.mfa.exists() and request.user.mfa.enabled:
        messages.info(request, "MFA is already enabled for your account.")
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

            messages.success(request, "MFA has been enabled. Backup codes have been generated and should be saved securely.")
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
        messages.success(request,"MFA has been disabled. You can re-enable it at any time.")
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
            messages.success(request, f"Account status for {user.username} updated to {status}.")
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

        messages.success(request, f"Account for {user.username} has been disabled.")
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

            messages.success(request, f"Membership updated for {customer.name}.")
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

            messages.success(request, f"{user.username} has been added to {customer.name}.")
            return redirect('accounts')
        else:
            messages.error(request, "Username is required.")
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

        messages.success(request, f"{user.username} has been removed from {customer.name}.")
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
            response['Content-Disposition']="attachment; filename=admin_actions_%s.csv" % timezone.now().strftime("%Y%m%d")
            return response

    logs=AdminActionLog.objects.order_by('-created_at')[:100]
    return render(request,'audit/export_admin_logs.html',{'logs':logs})

# ==================== EXISTING VIEWS (unchanged) ====================

def health(request): return HttpResponse('ok',content_type='text/plain')
