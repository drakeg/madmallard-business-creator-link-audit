"""Run on the Docker host. Creates a clearly labeled synthetic demo, never modifies
external content. Uses actual HTTP with CSRF and the separate persistent scan worker.
Credentials read from .env, never printed. No third-party customer content is used.
"""
import http.cookiejar,urllib.request,urllib.parse,re,time,pathlib,csv,io,json
root=pathlib.Path(__file__).resolve().parent.parent
env=dict(line.split('=',1) for line in (root/'.env').read_text().splitlines() if '=' in line and not line.startswith('#'))
base='http://127.0.0.1:'+env.get('PORT','8042')
jar=http.cookiejar.CookieJar();opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
def get(path):
 r=opener.open(base+path,timeout=30);return r.geturl(),r.read().decode()
def post(path,data):
 token=next(c.value for c in jar if c.name=='csrftoken')
 data=dict(data,csrfmiddlewaretoken=token)
 r=opener.open(urllib.request.Request(base+path,urllib.parse.urlencode(data,doseq=True).encode(),headers={'Referer':base+path}),timeout=30)
 return r.geturl(),r.read().decode()
get('/login/')
url,body=post('/login/',{'username':env['ADMIN_USERNAME'],'password':env['ADMIN_PASSWORD']})
assert 'Clear evidence' in body,'Live sign-in failed'
post('/accounts/',{'action':'customer','name':'Synthetic smoke-test sandbox'})
_,body=get('/')
ids=re.findall(r'<option value="(\d+)">Synthetic smoke-test sandbox</option>',body)
assert ids,'Customer creation failed'
url,body=post('/projects/new/',{'customer':ids[-1],'name':'Synthetic demo · no creator data'})
project=urllib.parse.urlsplit(url).path
url,body=post(project,{'title':'Synthetic link evidence','content':'Synthetic test only. Public page: https://example.com\nMissing path: https://example.com/madmallard-audit-missing-page\nBlocked safety example: http://169.254.169.254/latest/meta-data/','authorized':'on'})
assert 'Synthetic link evidence' in body and 'outbound links' in body,'Source import failed'
url,body=post(project+'scan/',{})
report=urllib.parse.urlsplit(url).path
for _ in range(75):
 _,body=get(report)
 if '<span class="pill">complete</span>' in body:break
 if '<span class="pill">failed</span>' in body:raise AssertionError('Worker failed: '+body[:500])
 time.sleep(2)
else:raise AssertionError('Worker did not complete within 150 seconds')
assert 'unsafe_blocked' in body,'Private destination not blocked'
assert 'destination_review' in body,'Public 2xx result missing'
_,data=get(report+'export/')
rows=list(csv.DictReader(io.StringIO(data)));assert len(rows)==3
_,html=get(report+'export/?format=html');assert 'Print / save PDF' in html and 'Source content' in html
result_id=re.search(r'/results/(\d+)/review/',body).group(1)
post('/results/'+result_id+'/review/',{'manual_status':'needs_owner','notes':'Synthetic smoke test: manual review UI saved. No commission or product verification performed.','replacement':''})
_,body=post(project+'scan/',{'approved':'on'})
retest_url=urllib.parse.urlsplit(_).path
for _i in range(75):
 _,body=get(retest_url)
 if '<span class="pill">complete</span>' in body:break
 time.sleep(2)
else:raise AssertionError('Retest did not complete')
assert 'Retest comparison' in body and 'Initial:' in body
print(json.dumps({'live_login':'passed','customer_project_source_import':'passed','worker_initial_scan':'passed','public_http_success':'passed','metadata_target_blocked':'passed','csv_rows':len(rows),'printable_html':'passed','manual_review':'passed','approved_retest_comparison':'passed','demo_project':base+project,'initial_report':base+report,'retest_report':base+retest_url},indent=2))
