from datetime import timedelta
from django.db import migrations
from django.utils import timezone


def extend_existing_previews(apps, schema_editor):
    Preview = apps.get_model("audit", "YouTubePreview")
    # Previously fetched previews expired 30 minutes after retrieval. Extend their
    # original retrieval-based lifetime to 29 days; do not pretend they were refreshed.
    for preview in Preview.objects.filter(expires_at__gt=timezone.now()).iterator():
        preview.expires_at += timedelta(days=29) - timedelta(minutes=30)
        preview.save(update_fields=["expires_at"])


class Migration(migrations.Migration):
    dependencies = [("audit", "0003_project_youtube_channel_url_source_api_expires_at_and_more")]
    operations = [migrations.RunPython(extend_existing_previews, migrations.RunPython.noop)]
