from collections import Counter
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.db import transaction
from django.http import Http404,HttpResponseBadRequest
from django.shortcuts import render,redirect
from django.utils import timezone
from django.views.decorators.http import require_POST
from .views import scan_for
from .models import Project,Scan,Link
from .forms import ReviewForm
from .quick_review import grouped_results,state_digest

SALT="unique-link-review-v1"

def find_group(scan,result_id):
    for group in grouped_results(scan):
        if any(r.pk==result_id for r in group["rows"]):return group
    raise Http404("Link group not found")

@login_required
def quick_report(request,pk):
    scan=scan_for(request,pk)
    groups=grouped_results(scan)
    counts=Counter(g["bucket"] for g in groups)
    selected=request.GET.get("show","all")
    visible=[g for g in groups if selected=="all" or g["bucket"]==selected]
    return render(request,"audit/quick_report.html",{"scan":scan,"groups":visible,"counts":dict(counts),"unique_count":len(groups),"occurrences":sum(g["count"] for g in groups),"selected":selected,"inspected":sum(bool(g["evidence"]) for g in groups)})

@login_required
@require_POST
def inspect_destinations(request,pk):
    scan=scan_for(request,pk)
    with transaction.atomic():
        Project.objects.filter(pk=scan.project_id).update(name=scan.project.name)
        existing=Scan.objects.filter(project=scan.project,purpose="inspection",baseline=scan).first()
        if existing:return redirect("quick_report",pk=existing.pk)
        if scan.state!="complete":
            messages.error(request,"Wait for the current check to finish.")
            return redirect("quick_report",pk=pk)
        if scan.project.scans.filter(state__in=["queued","running"]).exists() or Scan.objects.filter(state__in=["queued","running"]).count()>=10:
            messages.error(request,"A check is active or the queue is full. Try again later.")
            return redirect("quick_report",pk=pk)
        targets={str(r.link_id):r.tested_url or r.link.url for r in scan.results.select_related("link")}
        if not targets or len(set(targets.values()))>settings.MAX_LINKS:
            return HttpResponseBadRequest("No eligible targets or target limit exceeded")
        inspection=Scan.objects.create(project=scan.project,baseline=scan,purpose="inspection",targets=targets)
    return redirect("quick_report",pk=inspection.pk)

@login_required
def review_unique(request,pk,result_id):
    scan=scan_for(request,pk)
    group=find_group(scan,result_id)
    form=ReviewForm(request.POST or None,initial={"manual_status":"needs_owner"})
    error=""
    if request.method=="POST" and request.POST.get("action")=="apply":
        try:
            payload=signing.loads(request.POST.get("token",""),salt=SALT,max_age=600)
        except signing.BadSignature:
            return HttpResponseBadRequest("Review preview expired or invalid; preview again.")
        if payload.get("user")!=request.user.pk or payload.get("scan")!=scan.pk or request.POST.get("confirm")!="on":
            return HttpResponseBadRequest("Explicit confirmation required")
        with transaction.atomic():
            Project.objects.filter(pk=scan.project_id).update(name=scan.project.name)
            group=find_group(scan,result_id)
            if scan.state!="complete" or payload.get("key")!=group["key"] or payload.get("digest")!=state_digest(group):
                return HttpResponseBadRequest("These records changed after preview. Review and preview again.")
            decision=payload["decision"]
            original=group["representative"].link.url
            reviewed=Link.objects.filter(source__project=scan.project).exclude(manual_status="unreviewed").exclude(url=original).values("url").distinct().count()
            if decision["manual_status"]!="unreviewed" and reviewed>=10:
                return HttpResponseBadRequest("Pilot manual review limit is 10 unique original URLs.")
            now=timezone.now()
            block=(f"Shared unique-link review ({now.isoformat()}) by {request.user.username}: "+decision["notes"]).strip()
            for r in group["rows"]:
                for obj in (r,r.link):
                    obj.manual_status=decision["manual_status"]
                    if decision["notes"]:obj.notes=(obj.notes+"\n\n"+block).strip()
                    if decision["replacement"]:obj.replacement=decision["replacement"]
                    obj.reviewed_by=request.user.username;obj.reviewed_at=now
                    obj.save(update_fields=["manual_status","notes","replacement","reviewed_by","reviewed_at"])
        messages.success(request,f"Applied one review to {group['count']} uses of this exact link in this scan. No source URL or external site was changed.")
        return redirect("quick_report",pk=scan.pk)
    if request.method=="POST" and form.is_valid():
        decision=form.cleaned_data
        if scan.state!="complete":error="Wait for the scan to finish before reviewing its group."
        elif len(decision["notes"])>5000:error="Keep shared evidence notes under 5,000 characters."
        elif decision["manual_status"] in ("destination_verified","discount_verified","wrong_destination") and (not decision["notes"].strip() or request.POST.get("attest")!="on"):
            error="Record evidence and confirm you manually checked this selected link."
        if not error:
            token=signing.dumps({"user":request.user.pk,"scan":scan.pk,"key":group["key"],"digest":state_digest(group),"decision":decision},salt=SALT,compress=True)
            return render(request,"audit/unique_confirm.html",{"scan":scan,"group":group,"decision":decision,"token":token})
    return render(request,"audit/unique_review.html",{"scan":scan,"group":group,"form":form,"error":error})
