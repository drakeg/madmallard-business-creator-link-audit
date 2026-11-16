import csv,hashlib,io,json
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
from django.views.decorators.http import require_POST
from .models import Customer,Project,Source,Link,Scan,Result,LoginAttempt
from .forms import SourceForm,AccountForm,ProfileForm,ReviewForm
from .ingest import extract,uploaded,parameters
from .network import fetch

def projects(user):
    return Project.objects.all() if user.is_staff else Project.objects.filter(customer__members=user).distinct()
def project_for(request,pk): return get_object_or_404(projects(request.user),pk=pk)
def scan_for(request,pk): return get_object_or_404(Scan.objects.filter(project__in=projects(request.user)),pk=pk)
def login_view(request):
    if request.user.is_authenticated: return redirect('/')
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
                login(request,user); attempt.delete(); return redirect('/')
            attempt.failures+=1; attempt.save(); error='Sign-in failed. Check your username and password.'
    return render(request,'audit/login.html',{'error':error})
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
            for title,url,content,codes in rows:
                if not content.strip(): raise ValueError('Every source needs content')
                if len(content)>1_000_000: raise ValueError('Source exceeds size limit')
                prepared.append((title[:200],url,content,codes,extract(content,url)))
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
            messages.success(request,f'Imported {len(rows)} source(s); original content and link associations preserved.')
            return redirect('project',pk=p.pk)
        except Exception as exc: form.add_error(None,str(exc)[:500])
    return render(request,'audit/project.html',{'project':p,'form':form,'sources':p.sources.prefetch_related('links'),'scans':p.scans.order_by('-created'),'max_sources':settings.MAX_SOURCES,'max_links':settings.MAX_LINKS})
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
        completed=p.scans.filter(state='complete').order_by('created')
        baseline=completed.first()
        if p.scans.filter(baseline__isnull=False).exists():
            messages.error(request,'Pilot includes one initial scan and one retest. Create a new project for another engagement.'); return redirect('project',pk=pk)
        approved=request.POST.get('approved')=='on'
        if baseline and not approved:
            messages.error(request,'Confirm that the owner approved corrections before retesting.'); return redirect('project',pk=pk)
        if Scan.objects.filter(state__in=['queued','running']).count()>=10:
            messages.error(request,'Global queue is full; try later.'); return redirect('project',pk=pk)
        use_replacements=bool(baseline and request.POST.get('use_replacements')=='on')
        targets={str(l.pk):l.replacement if use_replacements and l.replacement else l.url for l in Link.objects.filter(source__project=p)}
        scan=Scan.objects.create(project=p,baseline=baseline,corrections_approved=approved,use_replacements=use_replacements,targets=targets)
    return redirect('report',pk=scan.pk)
@login_required
def report(request,pk):
    scan=scan_for(request,pk)
    results=scan.results.select_related('link__source').defer('link__source__content').order_by('link__source_id','link_id')
    category=request.GET.get('category',''); review=request.GET.get('review',''); query=request.GET.get('q','')
    if category: results=results.filter(category=category)
    if review: results=results.filter(manual_status=review)
    if query: results=results.filter(Q(tested_url__icontains=query)|Q(link__source__title__icontains=query)|Q(reason__icontains=query))
    return render(request,'audit/report.html',{'scan':scan,'results':results,'categories':scan.results.values_list('category',flat=True).distinct(),'summary':scan.results.values('category').annotate(count=Count('id')),'reviewed':scan.results.exclude(manual_status='unreviewed').count(),'category':category,'review':review,'query':query,'sources':scan.project.sources.all()})
@login_required
def review(request,pk):
    result=get_object_or_404(Result.objects.filter(scan__project__in=projects(request.user)).select_related('link__source','scan'),pk=pk)
    form=ReviewForm(request.POST or None,initial={'manual_status':result.manual_status,'notes':result.notes,'replacement':result.replacement})
    if request.method=='POST' and form.is_valid():
        d=form.cleaned_data
        if d['manual_status'] in ('destination_verified','discount_verified') and not d['notes'].strip():
            form.add_error('notes','Record the evidence and method used for manual verification.')
            return render(request,'audit/review.html',{'result':result,'form':form})
        with transaction.atomic():
            Project.objects.filter(pk=result.scan.project_id).update(name=result.scan.project.name)
            # Review budget is distinct links per engagement, not individual edits.
            reviewed=Link.objects.filter(source__project=result.scan.project).exclude(manual_status='unreviewed').exclude(pk=result.link_id).count()
            if d['manual_status']!='unreviewed' and reviewed>=10: form.add_error(None,'Pilot manual verification limit is 10 links.')
            else:
                for obj in (result,result.link):
                    for key,value in d.items(): setattr(obj,key,value)
                    obj.reviewed_by=request.user.username; obj.reviewed_at=timezone.now(); obj.save()
                messages.success(request,'Review saved. No source or external website was changed.')
                return redirect('report',pk=result.scan_id)
    return render(request,'audit/review.html',{'result':result,'form':form})
@login_required
def export(request,pk):
    scan=scan_for(request,pk); results=scan.results.select_related('link__source').defer('link__source__content').order_by('link__source_id','link_id')
    if request.GET.get('format')=='html': return render(request,'audit/print.html',{'scan':scan,'results':results})
    class Echo:
        def write(self,value): return value
    def safe(value):
        text='' if value is None else str(value)
        return "'"+text if text.lstrip().startswith(('=','+','-','@','\t','\r')) else text
    def rows():
        writer=csv.writer(Echo())
        yield writer.writerow(['project','customer','source','source_original_url','source_content','discount_codes_unverified','original_link','tested_url','suspected_affiliate_parameters_exact','category','http_status','redirect_chain','final_destination','checked_at_utc','reason','manual_status','notes','proposed_replacement','reviewed_by','reviewed_at','baseline_scan','previous_category','previous_status'])
        sources={s.pk:s for s in scan.project.sources.all()}
        for r in results.iterator(chunk_size=10):
            s=sources[r.link.source_id]
            yield writer.writerow([safe(v) for v in [scan.project.name,scan.project.customer.name,s.title,s.original_url,s.content,s.codes,r.link.url,r.tested_url,r.link.affiliate_parameters,r.category,r.status,json.dumps(r.chain),r.final_url,r.checked_at.isoformat(),r.reason,r.manual_status,r.notes,r.replacement,r.reviewed_by,r.reviewed_at,scan.baseline_id,r.previous_category,r.previous_status]])
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
