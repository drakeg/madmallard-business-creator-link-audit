"""Public HTTP only. Resolve once per hop and connect to that validated IP.
No proxy environment, cookies, credentials, POST, or automatic redirects.
"""
import ipaddress, socket, time
from urllib.parse import urlsplit,urljoin
import urllib3
from django.conf import settings
class UnsafeURL(ValueError): pass

def resolve_public(url):
    p=urlsplit(url)
    if p.scheme not in ('http','https') or not p.hostname or p.username or p.password:
        raise UnsafeURL('Only public HTTP/HTTPS URLs without credentials are allowed')
    try: port=p.port or (443 if p.scheme=='https' else 80)
    except ValueError: raise UnsafeURL('Invalid port')
    if port not in (80,443): raise UnsafeURL('Only ports 80 and 443 are allowed')
    host=p.hostname.rstrip('.').lower()
    if host=='localhost' or host.endswith(('.localhost','.local','.internal')) or host in ('metadata.google.internal','metadata','instance-data'):
        raise UnsafeURL('Local or metadata hostname blocked')
    addresses=socket.getaddrinfo(host,port,type=socket.SOCK_STREAM)
    ips=list(dict.fromkeys(x[4][0] for x in addresses))
    if not ips: raise UnsafeURL('No DNS addresses')
    for ip in ips:
        addr=ipaddress.ip_address(ip)
        if not addr.is_global or (addr.version==6 and (addr.ipv4_mapped or addr.sixtofour or addr.teredo)):
            raise UnsafeURL('Private, reserved, translated or metadata destination blocked')
    return p,ips[0],port

def fetch(url, read_body=False, *, allowed_content_types=("text/", "html"), request_headers=None, follow_redirects=True):
    chain=[]
    for hop in range(9):
        try: p,ip,port=resolve_public(url)
        except Exception as exc:
            exc.audit_chain=chain
            raise
        cls=urllib3.HTTPSConnectionPool if p.scheme=='https' else urllib3.HTTPConnectionPool
        options={'server_hostname':p.hostname,'assert_hostname':p.hostname} if p.scheme=='https' else {}
        pool=cls(ip,port=port,timeout=urllib3.Timeout(total=settings.SCAN_TIMEOUT,connect=settings.SCAN_TIMEOUT,read=settings.SCAN_TIMEOUT),retries=False,**options)
        response=None
        try:
            target=p.path or '/'
            if p.query: target+='?'+p.query
            response=pool.urlopen('GET',target,headers={'Host':p.netloc,'User-Agent':'MadMallardLinkAudit/0.1 (+owner-requested link check)','Accept':'text/html,application/json,*/*;q=0.5','Accept-Encoding':'identity',**(request_headers or {})},redirect=False,preload_content=False,retries=False)
            status=response.status
            location=response.headers.get('Location')
            chain.append({'url':url,'status':status,'location':location or ''})
            if follow_redirects and status in (301,302,303,307,308) and location:
                url=urljoin(url,location)
                continue
            body=b''
            if read_body:
                body=response.read(1_000_001,decode_content=False)
                if len(body)>1_000_000: raise ValueError('Public page exceeds 1 MB limit')
                if not any(t in response.headers.get('Content-Type','').lower() for t in allowed_content_types):
                    raise ValueError('Unexpected response content type')
            return status,url,chain,body
        except Exception as exc:
            exc.audit_chain=chain
            raise
        finally:
            if response: response.close()
            pool.close()
    exc=ValueError('Redirect limit exceeded (8 redirects)')
    exc.audit_chain=chain
    raise exc

def check(url):
    for attempt in range(settings.SCAN_RETRIES+1):
        try:
            status,final,chain,_=fetch(url)
            if status in (404,410): category,reason='broken','HTTP confirms missing/gone resource'
            elif status in (401,403): category,reason='access_blocked','Authentication, bot protection or access denial; not confirmed broken'
            elif status==429: category,reason='rate_limited','Rate limited; manual review or later retest required'
            elif 200<=status<300: category,reason='destination_review','Response received; verify product and affiliate destination manually. Commission tracking is not proven.'
            elif status>=500: category,reason='server_error','Server error; may be temporary'
            else: category,reason='http_review','Unexpected HTTP response; manual review required'
            if status>=500 and attempt<settings.SCAN_RETRIES: continue
            return dict(category=category,status=status,final_url=final,chain=chain,reason=reason)
        except UnsafeURL as exc:
            return dict(category='unsafe_blocked',status=None,final_url='',chain=getattr(exc,'audit_chain',[]),reason=str(exc))
        except Exception as exc:
            if attempt<settings.SCAN_RETRIES: continue
            category='timeout' if 'timeout' in type(exc).__name__.lower() or 'timed out' in str(exc).lower() else 'network_error'
            return dict(category=category,status=None,final_url='',chain=getattr(exc,'audit_chain',[]),reason=f'{type(exc).__name__}: {str(exc)[:400]}')
