"""Explicit discount-code records and unique commercial-URL review accounting."""
import re

from .models import DiscountCode, Link

# Accept exact code tokens or an explicit "CODE - N% off" owner-supplied note.
# Do not extract arbitrary words from prose or infer unknown discount codes.
CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,39}$")


def code_tokens(text):
    """Return unique single-token code lines, preserving their original spelling."""
    values = []
    seen = set()
    for line in (text or "").splitlines():
        value = line.strip()
        if not CODE_PATTERN.fullmatch(value):
            annotated = re.fullmatch(
                r"([A-Za-z0-9][A-Za-z0-9._-]{1,39})\s+-\s+\d{1,3}%\s*off",
                value, flags=re.IGNORECASE,
            )
            if not annotated:
                continue
            value = annotated.group(1)
        key = value.casefold()
        if CODE_PATTERN.fullmatch(value) and key not in seen:
            values.append(value)
            seen.add(key)
    return values


def register_owner_source_codes(project, sources):
    """Register exact code lines from owner-supplied sources as unverified records.

    API-derived YouTube descriptions are excluded: their text expires with the saved
    source, while an explicit register entry is owner-maintained project data. The raw
    description remains visible until retention cleanup, and reviewers can register a
    code manually from it when appropriate.
    """
    created = 0
    for source in sources:
        if source.youtube_video_id:
            continue
        for value in code_tokens(source.codes):
            record, made = DiscountCode.objects.get_or_create(
                project=project, code__iexact=value, defaults={"code": value}
            )
            record.sources.add(source)
            created += int(made)
    return created


def reviewed_commercial_url_count(project, exclude_url=None):
    """Count distinct reviewed commercial URLs, not repeated source-link occurrences."""
    links = Link.objects.filter(source__project=project).exclude(manual_status="unreviewed")
    if exclude_url is not None:
        links = links.exclude(url=exclude_url)
    return links.values("url").distinct().count()


def code_register(project):
    """Serializable project register used by reports, print output and CSV exports."""
    records = project.discount_codes.prefetch_related("sources").order_by("code")
    return [
        {
            "code": record.code,
            "status": record.status,
            "merchant_url": record.merchant_url,
            "evidence": record.evidence,
            "reviewed_by": record.reviewed_by,
            "reviewed_at": record.reviewed_at.isoformat() if record.reviewed_at else None,
            "source_titles": [source.title for source in record.sources.all()],
        }
        for record in records
    ]
