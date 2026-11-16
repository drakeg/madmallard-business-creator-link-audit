import csv,io,re,subprocess,tempfile,html
from html.parser import HTMLParser
from urllib.parse import urlsplit,urljoin
from django.conf import settings
class Anchors(HTMLParser):
    def __init__(self): super().__init__(); self.urls=[]
    def handle_starttag(self,tag,attrs):
        if tag=='a':
            self.urls += [v for k,v in attrs if k=='href' and v]
def extract(content,base=''):
    parser=Anchors(); parser.feed(content)
    raw=re.findall(r'https?://[^\s<>"\x27]+',content)
    urls=[]
    for value in parser.urls+raw:
        value=html.unescape(value).rstrip('.,;')
        # Markdown delimiters are not part of the URL; balanced parentheses are.
        while value.endswith(')') and value.count(')')>value.count('('): value=value[:-1]
        if base: value=urljoin(base,value)
        if value.startswith(('http://','https://')) and value not in urls: urls.append(value)
    # Lychee is used only in local dump-only mode on local source files. It never
    # receives a remote input and never performs network checks in this service.
    if urls:
        with tempfile.NamedTemporaryFile(suffix='.html' if '<a ' in content.lower() else '.md',mode='w') as file:
            file.write(content); file.flush()
            completed=subprocess.run([settings.LYCHEE_BIN,'--dump','--no-progress','--',file.name],capture_output=True,text=True,timeout=15,check=False)
            if completed.returncode != 0: raise ValueError('Lychee extraction failed; no sources imported')
            # Favor Lychee-extracted exact source matches, retaining encoded query
            # values. Keep fallback extraction for URLs excluded by Lychee defaults.
            matches=[u for u in completed.stdout.splitlines() if u in urls]
            urls=list(dict.fromkeys(matches+urls))
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
