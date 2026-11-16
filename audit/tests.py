import io,json,socket
from unittest.mock import patch,Mock
from django.test import TestCase,Client,override_settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from .models import Customer,Project,Source,Link,Scan,Result
from .network import resolve_public,UnsafeURL,check,fetch
from .ingest import parameters,uploaded,extract

class IsolationTests(TestCase):
    def setUp(self):
        self.a=User.objects.create_user('alice',password='a-test-password-123')
        self.b=User.objects.create_user('bob',password='b-test-password-123')
        ca=Customer.objects.create(name='A');ca.members.add(self.a)
        cb=Customer.objects.create(name='B');cb.members.add(self.b)
        self.pa=Project.objects.create(customer=ca,name='Alice private')
        self.pb=Project.objects.create(customer=cb,name='Bob private')
        s=Source.objects.create(project=self.pb,title='Secret source',content='secret text')
        self.link=Link.objects.create(source=s,url='https://example.com?tag=Bob%2BId')
        self.scan=Scan.objects.create(project=self.pb,state='complete')
        self.result=Result.objects.create(scan=self.scan,link=self.link,tested_url=self.link.url,category='broken',status=404)
        self.client.force_login(self.a)
    def test_cross_customer_reads_and_exports(self):
        for url in [f'/projects/{self.pb.pk}/',f'/reports/{self.scan.pk}/',f'/reports/{self.scan.pk}/export/',f'/reports/{self.scan.pk}/export/?format=html',f'/results/{self.result.pk}/review/',f'/projects/{self.pb.pk}/delete/?scans={self.scan.pk}']:
            self.assertEqual(self.client.get(url).status_code,404,url)
        body=self.client.get('/').content.decode()
        self.assertNotIn('Bob private',body)
    def test_cross_customer_mutations(self):
        for url,data in [(f'/projects/{self.pb.pk}/scan/',{}),(f'/results/{self.result.pk}/review/',{'manual_status':'destination_verified','notes':'forged'}),(f'/projects/{self.pb.pk}/delete/',{'scans':[self.scan.pk],'confirm':'DELETE'}),('/projects/new/',{'customer':self.pb.customer_id,'name':'intrusion'})]:
            self.assertEqual(self.client.post(url,data).status_code,404,url)
        self.assertTrue(Scan.objects.filter(pk=self.scan.pk).exists())
        self.result.refresh_from_db();self.assertEqual(self.result.manual_status,'unreviewed')
    def test_customer_cannot_create_admin(self):
        self.assertEqual(self.client.get('/accounts/').status_code,302)
        self.assertEqual(self.client.post('/accounts/',{'username':'evil','administrator':'on'}).status_code,302)
        self.assertFalse(User.objects.filter(username='evil').exists())
    def test_own_report_export_escaping_and_deletion(self):
        self.client.force_login(self.b)
        self.link.source.content='<script>alert(1)</script>';self.link.source.save()
        self.assertEqual(self.client.get(f'/reports/{self.scan.pk}/').status_code,200)
        html=self.client.get(f'/reports/{self.scan.pk}/export/?format=html').content.decode()
        self.assertIn('&lt;script&gt;',html);self.assertNotIn('<script>alert(1)</script>',html)
        data=b''.join(self.client.get(f'/reports/{self.scan.pk}/export/').streaming_content).decode()
        self.assertIn('Bob%2BId',data)
        self.client.post(f'/projects/{self.pb.pk}/delete/',{'scans':[self.scan.pk]})
        self.assertTrue(Scan.objects.filter(pk=self.scan.pk).exists())
        self.client.post(f'/projects/{self.pb.pk}/delete/',{'scans':[self.scan.pk],'confirm':'DELETE'})
        self.assertFalse(Scan.objects.filter(pk=self.scan.pk).exists())
        self.assertTrue(Source.objects.filter(project=self.pb).exists())
    def test_csrf_required(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.a)
        self.assertEqual(client.post('/projects/new/',{'name':'No token','customer':self.pa.customer_id}).status_code,403)
    @patch('audit.views.extract',return_value=['https://example.com?tag=A%2BB'])
    def test_paste_source_and_initial_scan_retest_gate(self,extract_mock):
        response=self.client.post(f'/projects/{self.pa.pk}/',{'title':'RV list','content':'https://example.com?tag=A%2BB','authorized':'on'})
        self.assertEqual(response.status_code,302)
        link=Link.objects.get(source__project=self.pa);self.assertEqual(link.affiliate_parameters,'tag=A%2BB')
        self.client.post(f'/projects/{self.pa.pk}/scan/')
        scan=self.pa.scans.get();scan.state='complete';scan.save()
        self.client.post(f'/projects/{self.pa.pk}/scan/')
        self.assertEqual(self.pa.scans.count(),1)
        self.client.post(f'/projects/{self.pa.pk}/scan/',{'approved':'on'})
        self.assertEqual(self.pa.scans.count(),2)
        self.client.post(f'/projects/{self.pa.pk}/',{'content':'new','authorized':'on'})
        self.assertEqual(self.pa.sources.count(),1)
    def test_profile_password_and_role_cannot_be_changed(self):
        self.client.post('/profile/',{'first_name':'Alice','email':'alice@example.com','is_staff':'on'})
        self.a.refresh_from_db();self.assertFalse(self.a.is_staff);self.assertEqual(self.a.first_name,'Alice')
    def test_manual_verification_requires_evidence(self):
        self.client.force_login(self.b)
        self.client.post(f'/results/{self.result.pk}/review/',{'manual_status':'discount_verified','notes':''})
        self.result.refresh_from_db();self.assertEqual(self.result.manual_status,'unreviewed')
    def test_login_lockout(self):
        self.client.logout()
        for _ in range(8): self.client.post('/login/',{'username':'alice','password':'wrong'})
        response=self.client.post('/login/',{'username':'alice','password':'a-test-password-123'})
        self.assertContains(response,'Too many attempts')

class NetworkTests(TestCase):
    def test_unsafe_schemes_credentials_and_ports(self):
        for url in ['file:///etc/passwd','ftp://example.com','http://user:pass@example.com','http://example.com:8000','http://metadata.google.internal','http://localhost','http://host.local']:
            with self.assertRaises(UnsafeURL,msg=url): resolve_public(url)
    @patch('audit.network.socket.getaddrinfo')
    def test_private_and_mixed_dns_denied(self,dns):
        for ip in ['127.0.0.1','10.0.0.1','169.254.169.254','192.168.1.1','0.0.0.0','::1','fc00::1','::ffff:127.0.0.1','100.100.100.200']:
            dns.return_value=[(socket.AF_INET,socket.SOCK_STREAM,6,'',(ip,80))]
            with self.assertRaises(UnsafeURL,msg=ip): resolve_public('http://public.example')
        dns.return_value=[(2,1,6,'',('93.184.216.34',80)),(2,1,6,'',('127.0.0.1',80))]
        with self.assertRaises(UnsafeURL): resolve_public('http://mixed.example')
    @patch('audit.network.urllib3.HTTPConnectionPool')
    @patch('audit.network.socket.getaddrinfo')
    def test_redirect_to_private_blocked_before_second_connection(self,dns,pool):
        dns.side_effect=[[(2,1,6,'',('93.184.216.34',80))],[(2,1,6,'',('169.254.169.254',80))]]
        response=Mock(status=302,headers={'Location':'http://169.254.169.254/latest/meta-data/'})
        pool.return_value.urlopen.return_value=response
        result=check('http://example.com')
        self.assertEqual(result['category'],'unsafe_blocked');self.assertEqual(pool.call_count,1)
        self.assertEqual(result['chain'][0]['status'],302)
    @patch('audit.network.urllib3.HTTPSConnectionPool')
    @patch('audit.network.socket.getaddrinfo',return_value=[(2,1,6,'',('93.184.216.34',443))])
    def test_dns_pinning_and_no_auto_redirects(self,dns,pool):
        pool.return_value.urlopen.return_value=Mock(status=200,headers={})
        fetch('https://example.com/path?tag=Ab%2B1')
        self.assertEqual(pool.call_args.args[0],'93.184.216.34')
        self.assertEqual(pool.call_args.kwargs['server_hostname'],'example.com')
        self.assertEqual(pool.return_value.urlopen.call_args.args[1],'/path?tag=Ab%2B1')
        self.assertFalse(pool.return_value.urlopen.call_args.kwargs['redirect'])
    @patch('audit.network.fetch')
    def test_categories(self,fetch_mock):
        for code,category in [(200,'destination_review'),(404,'broken'),(410,'broken'),(403,'access_blocked'),(429,'rate_limited'),(503,'server_error')]:
            fetch_mock.return_value=(code,'https://example.com',[],b'')
            self.assertEqual(check('https://example.com')['category'],category)
        fetch_mock.side_effect=TimeoutError('timed out')
        self.assertEqual(check('https://example.com')['category'],'timeout')

class IngestTests(TestCase):
    def test_exact_query_values(self):
        self.assertEqual(parameters('https://example.com?tag=a%2Bb&ref=X+Y&ref=Two&utm_source=YT&other=1'),'tag=a%2Bb&ref=X+Y&ref=Two&utm_source=YT')
    def test_csv_rows(self):
        file=SimpleUploadedFile('sources.csv',b'title,original_url,content\nOne,https://a.example,https://product.example\nTwo,,https://other.example\n')
        self.assertEqual(len(uploaded(file)),2)
    @patch('audit.ingest.subprocess.run',return_value=Mock(returncode=0,stdout=""))
    def test_lychee_dump_uses_local_input_and_preserves_raw_links(self,run):
        urls=extract('[gear](https://example.com/item?tag=Exact%2BId&ref=One+Two)')
        self.assertEqual(urls,['https://example.com/item?tag=Exact%2BId&ref=One+Two'])
        self.assertIn('--dump',run.call_args.args[0]);self.assertNotIn('https://',run.call_args.args[0][-1])

class LimitAndReportTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user('pilot',password='pilot-test-password')
        customer=Customer.objects.create(name='Pilot');customer.members.add(self.user)
        self.project=Project.objects.create(customer=customer,name='Limits')
        self.client.force_login(self.user)
    @override_settings(MAX_SOURCES=1)
    @patch('audit.views.extract',return_value=['https://example.com/one'])
    def test_source_limit_is_atomic(self,mock):
        Source.objects.create(project=self.project,title='Existing',content='Existing')
        response=self.client.post(f'/projects/{self.project.pk}/',{'title':'Excess','content':'https://example.com/one','authorized':'on'})
        self.assertEqual(response.status_code,200);self.assertEqual(self.project.sources.count(),1)
    @override_settings(MAX_LINKS=1)
    @patch('audit.views.extract',return_value=['https://example.com/one','https://example.com/two'])
    def test_unique_link_limit_rejects_whole_import(self,mock):
        self.client.post(f'/projects/{self.project.pk}/',{'content':'two links','authorized':'on'})
        self.assertEqual(self.project.sources.count(),0)
    def test_retest_targets_snapshot_proposals(self):
        source=Source.objects.create(project=self.project,title='Gear',content='Original')
        link=Link.objects.create(source=source,url='https://example.com?tag=Original',replacement='https://example.com?tag=OwnerChosen')
        baseline=Scan.objects.create(project=self.project,state='complete')
        self.client.post(f'/projects/{self.project.pk}/scan/',{'approved':'on','use_replacements':'on'})
        retest=self.project.scans.exclude(pk=baseline.pk).get()
        link.replacement='https://example.com?tag=LaterEdit';link.save()
        self.assertEqual(retest.targets[str(link.pk)],'https://example.com?tag=OwnerChosen')
        self.assertEqual(link.url,'https://example.com?tag=Original')
    def test_csv_formula_neutralized(self):
        source=Source.objects.create(project=self.project,title='=SUM(1,2)',content='+formula',codes='')
        link=Link.objects.create(source=source,url='https://example.com')
        scan=Scan.objects.create(project=self.project,state='complete')
        Result.objects.create(scan=scan,link=link,category='destination_review',notes='@malicious')
        text=b''.join(self.client.get(f'/reports/{scan.pk}/export/').streaming_content).decode()
        self.assertIn("'=SUM",text);self.assertIn("'+formula",text);self.assertIn("'@malicious",text)
    def test_manual_limit(self):
        source=Source.objects.create(project=self.project,title='Links',content='List')
        for i in range(10): Link.objects.create(source=source,url=f'https://example.com/{i}',manual_status='needs_owner')
        link=Link.objects.create(source=source,url='https://example.com/eleven')
        scan=Scan.objects.create(project=self.project,state='complete')
        result=Result.objects.create(scan=scan,link=link,category='broken')
        response=self.client.post(f'/results/{result.pk}/review/',{'manual_status':'needs_owner','notes':'Owner needed'})
        self.assertContains(response,'limit is 10');result.refresh_from_db();self.assertEqual(result.manual_status,'unreviewed')
    def test_bulk_delete_requires_confirmation_and_scopes_selection(self):
        a=Scan.objects.create(project=self.project,state='complete');b=Scan.objects.create(project=self.project,state='complete')
        other=Project.objects.create(customer=Customer.objects.create(name='Other'),name='Other')
        foreign=Scan.objects.create(project=other,state='complete')
        self.client.post(f'/projects/{self.project.pk}/delete/',{'scans':[a.pk,b.pk,foreign.pk],'confirm':'DELETE'})
        self.assertEqual(self.project.scans.count(),0);self.assertTrue(Scan.objects.filter(pk=foreign.pk).exists())
    def test_upload_csv_and_markdown(self):
        for name,content in [('one.csv',b'title,content\nCSV source,https://example.com\n'),('two.md',b'[Gear](https://example.com/product)')]:
            with patch('audit.views.extract',return_value=['https://example.com']):
                response=self.client.post(f'/projects/{self.project.pk}/',{'file':SimpleUploadedFile(name,content),'authorized':'on'})
                self.assertEqual(response.status_code,302)
        self.assertEqual(self.project.sources.count(),2)
