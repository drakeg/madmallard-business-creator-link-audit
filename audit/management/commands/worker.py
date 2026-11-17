import time
from concurrent.futures import ThreadPoolExecutor,as_completed
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
from django.db import close_old_connections
from audit.models import Scan,Result
from audit.network import check
from audit.content_checks import asin
class Command(BaseCommand):
    help='Single persistent scan worker. Do not scale beyond one with SQLite.'
    def handle(self,*args,**kwargs):
        Scan.objects.filter(state='running').update(state='interrupted',error='Worker restarted; partial evidence preserved. Delete this attempt and retry if no completed baseline exists.',finished=timezone.now())
        while True:
            close_old_connections()
            scan=Scan.objects.filter(state='queued').order_by('created').first()
            if not scan: time.sleep(1); continue
            if not Scan.objects.filter(pk=scan.pk,state='queued').update(state='running'): continue
            try:
                links=list(scan.project.sources.prefetch_related('links').all())
                links=[link for source in links for link in source.links.all()]
                if scan.purpose=="inspection": links=[link for link in links if str(link.pk) in scan.targets]
                targets={l.pk:scan.targets.get(str(l.pk),l.url) for l in links}
                unique=list(dict.fromkeys(targets.values()))
                if len(unique)>settings.MAX_LINKS: raise ValueError('Unique link limit exceeded')
                scan.total=len(unique); scan.save(update_fields=['total'])
                previous={r.link_id:r for r in scan.baseline.results.all()} if scan.baseline else {}
                with ThreadPoolExecutor(max_workers=settings.SCAN_CONCURRENCY) as pool:
                    jobs={pool.submit(check,url):url for url in unique}
                    for job in as_completed(jobs):
                        url=jobs[job]; evidence=job.result()
                        for link in links:
                            if targets[link.pk]!=url: continue
                            old=previous.get(link.pk)
                            per_link=dict(evidence)
                            if old and asin(old.final_url) and asin(per_link.get('final_url','')) and asin(old.final_url)!=asin(per_link['final_url']):
                                per_link['content_evidence']=dict(per_link.get('content_evidence',{}),outcome='product_changed',reasons=['The destination product identifier changed from the previous saved check.'])
                            Result.objects.create(scan=scan,link=link,tested_url=url,previous_category=old.category if old else '',previous_status=old.status if old else None,manual_status=link.manual_status,notes=link.notes,replacement=link.replacement,reviewed_by=link.reviewed_by,reviewed_at=link.reviewed_at,**per_link)
                        scan.progress+=1; scan.save(update_fields=['progress'])
                scan.state='complete'
            except Exception as exc:
                scan.state='failed'; scan.error=f'{type(exc).__name__}: {str(exc)[:400]}'
            scan.finished=timezone.now(); scan.save(update_fields=['state','error','finished'])
