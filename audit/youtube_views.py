from datetime import timedelta
import uuid
import time
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseBadRequest, Http404
from django.utils import timezone
from django.views.decorators.debug import sensitive_post_parameters
from .models import Project, Source, Link, YouTubePreview
from .views import project_for
from .youtube import load_channel, parse_channel, YouTubeError
from .ingest import extract, parameters

def scoped_preview(value, project, user):
    try: value = uuid.UUID(str(value))
    except (ValueError, TypeError): raise Http404("Preview not found")
    return get_object_or_404(YouTubePreview, pk=value, project=project, user=user)

def purge_expired():
    now = timezone.now()
    YouTubePreview.objects.filter(expires_at__lte=now).delete()
    Source.objects.filter(api_expires_at__lte=now).delete()

class YouTubeRetentionMiddleware:
    def __init__(self, get_response): self.get_response = get_response
    def __call__(self, request):
        purge_expired()
        return self.get_response(request)

@sensitive_post_parameters("api_key")
@login_required
def channel_import(request, pk):
    project = project_for(request, pk)
    url = request.POST.get("channel_url", request.GET.get("channel_url", project.youtube_channel_url))
    preview = None
    if request.method == "GET":
        if request.GET.get("preview"):
            preview = scoped_preview(request.GET["preview"], project, request.user)
        elif not request.GET.get("channel_url"):
            preview = YouTubePreview.objects.filter(project=project, user=request.user, expires_at__gt=timezone.now()).order_by("-expires_at").first()
        if preview:
            url = preview.payload["channel_url"]
    error = ""
    if request.method == "POST":
        action = request.POST.get("action", "browse")
        if project.scans.exists():
            error = "Sources are locked after a scan. Create a new project to import more descriptions."
        elif action == "browse":
            key = request.POST.get("api_key", "").strip() or settings.YOUTUBE_API_KEY
            try:
                # Validate even without a key so the URL input remains useful.
                _, url = parse_channel(url)
                page_token = ""
                if request.POST.get("page"):
                    previous = scoped_preview(request.POST["page"], project, request.user)
                    if previous.expires_at <= timezone.now():
                        raise YouTubeError("This preview expired. Load the channel again.")
                    if url != previous.payload["channel_url"]:
                        raise YouTubeError("Load the new channel from its first page.")
                    page_token = previous.payload.get("next_page", "")
                    if not page_token: raise YouTubeError("No older page is available.")
                if time.time() - request.session.get("youtube_last_load", 0) < 5:
                    raise YouTubeError("Wait five seconds before loading another page.")
                if key: request.session["youtube_last_load"] = time.time()
                payload = load_channel(url, key, page_token)
                old = list(YouTubePreview.objects.filter(user=request.user, project=project).order_by("-expires_at").values_list("pk", flat=True))[4:]
                YouTubePreview.objects.filter(pk__in=old).delete()
                preview = YouTubePreview.objects.create(user=request.user, project=project, payload=payload, expires_at=timezone.now()+timedelta(minutes=30))
                project.youtube_channel_url = payload["channel_url"]
                project.save(update_fields=["youtube_channel_url"])
                count = len(payload["videos"])
                messages.success(request, f"Loaded {count} public videos from {payload['channel_title']}. Select descriptions below to import.")
                return redirect(f"/projects/{project.pk}/youtube/?preview={preview.pk}#videos")
            except YouTubeError as exc:
                error = str(exc)
        elif action == "import":
            preview = scoped_preview(request.POST.get("preview"), project, request.user)
            try:
                if preview.expires_at <= timezone.now(): raise YouTubeError("Preview expired; load the channel again.")
                if request.POST.get("authorized") != "on":
                    raise YouTubeError("Confirm ownership or permission and the metadata retention terms.")
                selected = list(dict.fromkeys(request.POST.getlist("videos")))
                if not selected: raise YouTubeError("Select at least one video.")
                if len(selected) > settings.MAX_SOURCES: raise YouTubeError("Select at most 20 videos.")
                videos = {v["id"]:v for v in preview.payload["videos"]}
                if any(v not in videos for v in selected): raise YouTubeError("Selection is not in this channel preview.")
                prepared = []
                for video_id in selected:
                    video = videos[video_id]
                    if not video["description"].strip(): raise YouTubeError("A selected video has no description.")
                    prepared.append((video, extract(video["description"], video["url"])))
                with transaction.atomic():
                    Project.objects.filter(pk=project.pk).update(name=project.name)
                    if project.scans.exists(): raise YouTubeError("A scan was queued; sources are now locked.")
                    # Serializes repeated submissions so the same video is not duplicated.
                    existing = set(project.sources.exclude(youtube_video_id="").values_list("youtube_video_id", flat=True))
                    prepared = [row for row in prepared if row[0]["id"] not in existing]
                    if project.sources.count()+len(prepared) > settings.MAX_SOURCES:
                        raise YouTubeError("Project source limit exceeded. Select fewer videos or start a new project.")
                    urls = set(Link.objects.filter(source__project=project).values_list("url", flat=True))
                    urls.update(u for video, links in prepared for u in links)
                    if len(urls) > settings.MAX_LINKS:
                        raise YouTubeError("These descriptions exceed the 100-unique-link project limit. Select fewer videos.")
                    for video, links in prepared:
                        source = Source.objects.create(project=project, title=video["title"], original_url=video["url"], content=video["description"], youtube_video_id=video["id"], api_expires_at=timezone.now()+timedelta(days=29))
                        Link.objects.bulk_create([Link(source=source, url=u, affiliate_parameters=parameters(u)) for u in links])
                    # Keep the short-lived catalogue so older-page navigation still works.
                messages.success(request, f"Imported {len(prepared)} YouTube description(s). Now queue the initial link scan.")
                return redirect(f"/projects/{project.pk}/youtube/?preview={preview.pk}#videos")
            except (YouTubeError, ValueError) as exc:
                error = str(exc)
        else:
            return HttpResponseBadRequest("Unknown import operation")
    if preview:
        existing = set(project.sources.exclude(youtube_video_id="").values_list("youtube_video_id", flat=True))
        for video in preview.payload["videos"]: video["imported"] = video["id"] in existing
    return render(request, "audit/youtube.html", {"project":project, "channel_url":url, "preview":preview, "error":error, "configured":bool(settings.YOUTUBE_API_KEY), "remaining":max(0,settings.MAX_SOURCES-project.sources.count())})

@login_required
def delete_youtube(request, pk):
    project = project_for(request, pk)
    sources = project.sources.exclude(youtube_video_id="")
    if request.method == "POST" and request.POST.get("confirm") == "DELETE":
        if project.scans.filter(state__in=["queued","running"]).exists():
            messages.error(request, "Wait until the scan finishes before deleting imported data.")
            return redirect("project", pk=pk)
        count = sources.count()
        sources.delete()
        YouTubePreview.objects.filter(project=project).delete()
        project.youtube_channel_url=""
        project.save(update_fields=["youtube_channel_url"])
        messages.success(request, f"Deleted {count} local YouTube sources and associated result rows. Nothing on YouTube changed.")
        return redirect("project", pk=pk)
    return render(request, "audit/youtube_delete.html", {"project":project, "count":sources.count()})
