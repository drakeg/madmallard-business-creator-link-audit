import csv,io,re,subprocess,tempfile,html,time,logging
logger=logging.getLogger(__name__)
from html.parser import HTMLParser
from urllib.parse import urlsplit,urljoin
from django.conf import settings
class Anchors(HTMLParser):
    def __init__(self): super().__init__(); self.urls=[]
    def handle_starttag(self,tag,attrs):
        if tag=='a':
            self.urls += [v for k,v in attrs if k=='href' and v]
def extract(content,base='',*,notices=None,deadline=None):
    parser=Anchors()
    try: parser.feed(content)
    except (AssertionError,ValueError):
        logger.warning('Malformed source markup; continuing with literal URL extraction')
        message='Source markup was malformed; review the imported link list for coverage.'
        if notices is not None and message not in notices: notices.append(message)
    raw=re.findall(r'https?://[^\s<>"\x27]+',content)
    urls=[]
    for value in parser.urls+raw:
        value=html.unescape(value).rstrip('.,;')
        # Markdown delimiters are not part of the URL; balanced parentheses are.
        while value.endswith(')') and value.count(')')>value.count('('): value=value[:-1]
        if base: value=urljoin(base,value)
        if value.startswith(('http://','https://')) and value not in urls: urls.append(value)
    # Literal URLs/hrefs above are preserved even if the supplementary CLI fails.
    # One import request gets a bounded helper budget, not 15 seconds per video.
    if urls:
        reason = None
        remaining = 5 if deadline is None else min(5, deadline-time.monotonic())
        if remaining <= 0:
            reason = 'batch deadline'
        else:
            try:
                with tempfile.NamedTemporaryFile(suffix='.html' if '<a ' in content.lower() else '.md',mode='w') as file:
                    file.write(content); file.flush()
                    completed=subprocess.run([settings.LYCHEE_BIN,'--dump','--no-progress','--',file.name],capture_output=True,text=True,errors='replace',timeout=remaining,check=False)
                if completed.returncode == 0:
                    matches=[u for u in completed.stdout.splitlines() if u in urls]
                    urls=list(dict.fromkeys(matches+urls))
                else:
                    reason = 'nonzero exit'
            except subprocess.TimeoutExpired:
                reason = 'timeout'
            except (OSError,UnicodeError,subprocess.SubprocessError):
                reason = 'unavailable helper'
        if reason:
            message = 'Some links used the built-in URL parser because Lychee was unavailable or timed out. Review the imported link list for coverage before scanning.'
            if notices is not None and message not in notices: notices.append(message)
            logger.warning('Supplementary Lychee extraction skipped: %s',reason)

    return urls

def parameters(url):
    return '&'.join(part for part in urlsplit(url).query.split('&') if re.search(r'(^|_)(tag|ref|aff|affiliate|associate|partner|tracking|utm|subid|clickid|irclickid|ascsubtag)',part.split('=')[0],re.I))

def uploaded(file):
    if file.size>1_000_000: raise ValueError('Upload exceeds 1 MB')
    text=file.read().decode('utf-8-sig')
    ext=file.name.lower().rsplit('.',1)[-1]
    if ext in ('md','markdown','html','htm'): return [(file.name,'',text,'')]
    if ext!='csv': raise ValueError('Use CSV, Markdown or HTML')
    reader=csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or not {'title','content'}.issubset(reader.fieldnames): raise ValueError('CSV requires title,content columns; optional original_url,discount_codes')
    rows=[]
    for row in reader:
        rows.append((row['title'],row.get('original_url',''),row['content'],row.get('discount_codes','')))
        if len(rows)>settings.MAX_SOURCES: raise ValueError('CSV exceeds source limit')
    return rows
