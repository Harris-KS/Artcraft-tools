import importlib.util
import io
import hashlib
import json
from pathlib import Path
import tarfile
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch

OUTPUT=Path(__file__).resolve().parent.parent/'linux-edge'
def load(name):
    spec=importlib.util.spec_from_file_location(name,OUTPUT/(name+'.py'))
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module
edge=load('artcraft_edge'); bridge=load('mcp_bridge')

def repo(name): return {'name':name,'owner':{'login':'storytold'},'description':name+' editor','fork':False,'archived':False}
def release(version='1.0.0'):
    names=[f'newcraft-{version}-linux-x86_64.tar.gz',f'newcraft-{version}-linux-aarch64.tar.gz',f'filter-{version}.wasm']
    return {'tag_name':'v'+version,'assets':[{'name':name,'browser_download_url':f'https://github.com/storytold/newcraft/releases/download/v{version}/{name}'} for name in names]}

class EdgeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
        self.manager=edge.Manager(self.root/'state',self.root/'files','x86_64')
    def tearDown(self): self.temp.cleanup()
    def test_arch_package(self):
        self.assertIn('x86_64',edge.package_for(release(),'x86_64')['name'])
        self.assertIn('aarch64',edge.package_for(release(),'aarch64')['name'])
    def test_full_package_preferred_over_separate_cli_archive(self):
        rel=release()
        rel['assets'].append({'name':'newcraft-cli-1.0.0-linux-x86_64.tar.gz'})
        self.assertEqual(edge.package_for(rel,'x86_64')['name'],'newcraft-1.0.0-linux-x86_64.tar.gz')
        rel['assets']=[rel['assets'][-1]]
        self.assertEqual(edge.package_for(rel,'x86_64')['name'],'newcraft-cli-1.0.0-linux-x86_64.tar.gz')
    def test_discovery_new_repo_resources_and_versions(self):
        rows=[repo('newcraft'),repo('library')]; version='1.0.0'
        def api(path):
            if path.startswith('orgs/'): return rows
            return release(version) if '/newcraft/' in path else None
        with patch.object(edge,'github',side_effect=api):
            first=self.manager.refresh()
            self.assertEqual(len(first['items']),3)
            self.assertFalse(any(x['new'] for x in first['items']))
            rows.append(repo('freshcraft')); version='2.0.0'
            second=self.manager.refresh()
            self.assertTrue(next(x for x in second['items'] if x['id']=='freshcraft')['new'])
            resource=next(x for x in second['items'] if x['kind']=='resource')
            self.assertFalse(resource['new'])
            self.assertEqual(resource['version'],'v2.0.0')
    def test_pagination(self):
        rows=[{**repo(f'r{i}'),'fork':True} for i in range(100)]
        def api(path):
            if path.startswith('orgs/'): return rows if 'page=1&' in path else [repo('final')]
            return None
        with patch.object(edge,'github',side_effect=api): result=self.manager.refresh()
        self.assertEqual(len(result['repositories']),101)
        self.assertIn('final',[x['id'] for x in result['items']])
    def test_scan_failure_retains_previous_snapshot(self):
        self.manager.snapshot['checked_at']='old'
        with patch.object(edge,'github',side_effect=RuntimeError('offline')):
            with self.assertRaises(RuntimeError): self.manager.refresh()
        self.assertEqual(self.manager.snapshot['checked_at'],'old')
    def test_release_failure_visible(self):
        def api(path):
            if path.startswith('orgs/'): return [repo('newcraft')]
            raise RuntimeError('quota')
        with patch.object(edge,'github',side_effect=api): result=self.manager.refresh()
        self.assertEqual(result['errors'][0]['repo'],'newcraft')
        self.assertEqual(result['items'][0]['kind'],'repository')
    def test_official_url(self):
        for url in ['http://github.com/storytold/newcraft/releases/download/v1/a','https://evil.test/a','https://github.com/other/newcraft/releases/download/v1/a']:
            with self.assertRaises(ValueError): edge.official_url(url,'newcraft')
    def test_verified_download_and_hash_failure(self):
        data=b'fixture'
        rel=release(); rel['assets'][0]['digest']='sha256:'+hashlib.sha256(data).hexdigest()
        item={'repo':'newcraft','kind':'app'}
        with patch.object(edge,'github',return_value=rel), patch.object(edge,'urlopen',side_effect=lambda *a,**k:io.BytesIO(data)):
            path,version=self.manager.download(item,self.root/'download')
            self.assertEqual(path.read_bytes(),data); self.assertEqual(version,'v1.0.0')
            rel['assets'][0]['digest']='sha256:'+'0'*64
            with self.assertRaisesRegex(ValueError,'SHA-256'): self.manager.download(item,self.root/'bad')
            self.assertFalse(any((self.root/'bad').glob('*.partial')))
    def test_missing_checksum_rejected(self):
        with patch.object(edge,'github',return_value=release()):
            with self.assertRaisesRegex(ValueError,'checksum'): self.manager.download({'repo':'newcraft','kind':'app'},self.root/'bad')
    def archive(self,name,kind=None):
        path=self.root/'fixture.tar.gz'
        with tarfile.open(path,'w:gz') as tar:
            info=tarfile.TarInfo(name)
            if kind: info.type=kind; info.linkname='outside'
            else: info.size=2
            tar.addfile(info,None if kind else io.BytesIO(b'hi'))
        return path
    def test_tar_extraction_and_traversal(self):
        target=self.root/'unpacked'; target.mkdir()
        edge.Manager.unpack(self.archive('bin/newcraft-cli'),target)
        self.assertEqual((target/'bin/newcraft-cli').read_bytes(),b'hi')
        for name,kind in [('../escape',None),('/absolute',None),('link',tarfile.SYMTYPE)]:
            with self.assertRaises(ValueError): edge.Manager.unpack(self.archive(name,kind),target)
    def test_failed_install_does_not_replace_active_version(self):
        self.manager.installed['newcraft']={'version':'old','cli':None}
        self.manager.snapshot['items']=[{'id':'newcraft','repo':'newcraft','kind':'app'}]
        with patch.object(edge.sys,'platform','linux'),patch.object(edge,'github',return_value=release()),patch.object(self.manager,'download',return_value=(self.archive('../escape'),'new')):
            with self.assertRaises(ValueError): self.manager.install('newcraft')
        self.assertEqual(self.manager.installed['newcraft']['version'],'old')
    def test_cli_discovery(self):
        self.manager.snapshot['items']=[{'id':'newcraft','repo':'newcraft','kind':'app'}]
        with patch.object(edge.sys,'platform','linux'),patch.object(edge,'github',return_value=release()),patch.object(self.manager,'download',return_value=(self.archive('bin/newcraft-cli'),'new')):
            result=self.manager.install('newcraft')
        self.assertTrue(result['cli'].endswith('newcraft-cli'))
    def test_cli_arguments_and_secret_environment(self):
        cli=self.manager.root/'apps'/'newcraft-cli'; cli.parent.mkdir(); cli.write_text('fixture')
        self.manager.installed['newcraft']={'cli':str(cli)}
        class Process:
            def wait(self,timeout): return 0
        with patch.object(edge.subprocess,'Popen',return_value=Process()) as popen:
            result=self.manager.run_cli('newcraft',['--help'])
        self.assertEqual(result['exit_code'],0)
        self.assertEqual(popen.call_args.args[0],[str(cli),'--help'])
        self.assertNotIn('ARTCRAFT_API_TOKEN',popen.call_args.kwargs['env'])
        self.assertNotIn('GITHUB_TOKEN',popen.call_args.kwargs['env'])
        self.assertNotIn('shell',popen.call_args.kwargs)
        with self.assertRaises(ValueError): self.manager.run_cli('newcraft','--help')
        with self.assertRaises(ValueError): self.manager.run_cli('newcraft',['--help'],301)
    def test_mcp_initialize_list_and_call(self):
        self.assertEqual(bridge.dispatch({'method':'initialize','params':{'protocolVersion':'2025-11-25'}})['protocolVersion'],'2025-11-25')
        names=[t['name'] for t in bridge.dispatch({'method':'tools/list'})['tools']]
        self.assertEqual(names,['artcraft_catalog','artcraft_run'])
        with patch.object(bridge,'api',return_value={'items':[]}) as api:
            result=bridge.dispatch({'method':'tools/call','params':{'name':'artcraft_catalog','arguments':{'refresh':True}}})
            api.assert_called_once_with('/refresh',{})
        self.assertFalse(result['isError'])
        with patch.object(bridge,'api',return_value={'exit_code':1}):
            result=bridge.dispatch({'method':'tools/call','params':{'name':'artcraft_run','arguments':{'app':'x','args':[]}}})
        self.assertTrue(result['isError'])
    def test_mcp_stdio_transport(self):
        messages=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-11-25'}},
                  {'jsonrpc':'2.0','method':'notifications/initialized'},
                  {'jsonrpc':'2.0','id':2,'method':'tools/list'}]
        result=subprocess.run([sys.executable,'-B',str(OUTPUT/'mcp_bridge.py')],
                              input='\n'.join(json.dumps(x) for x in messages)+'\n',text=True,capture_output=True,timeout=10)
        self.assertEqual(result.returncode,0)
        replies=[json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual([x['id'] for x in replies],[1,2])
        self.assertIn('tools',replies[1]['result'])
    def test_api_auth_and_operator_install_gate(self):
        token='random-test-token-for-local-api-123'
        with patch.dict(edge.os.environ,{'ARTCRAFT_API_TOKEN':token,'ARTCRAFT_ALLOW_API_INSTALL':'0'}),patch.object(edge,'HTTPServer') as server:
            edge.serve(self.manager,'127.0.0.1',8787)
            handler_class=server.call_args.args[1]
            handler=object.__new__(handler_class); replies=[]
            handler.reply=lambda code,data:replies.append((code,data))
            handler.headers={}; handler.path='/catalog'; handler.do_GET()
            self.assertEqual(replies[-1][0],401)
            handler.headers={'Authorization':'Bearer '+token}; handler.do_GET()
            self.assertEqual(replies[-1][0],200)
            handler.headers['Origin']='https://example.com'; handler.do_GET()
            self.assertEqual(replies[-1][0],401)
            payload=json.dumps({'id':'newcraft'}).encode()
            handler.headers={'Authorization':'Bearer '+token,'Content-Length':str(len(payload))}
            handler.path='/install'; handler.rfile=io.BytesIO(payload); handler.do_POST()
            self.assertEqual(replies[-1][0],403)
    def test_scheduled_refresh_and_failure_retry(self):
        env={'ARTCRAFT_API_TOKEN':'random-test-token-for-local-api-123','ARTCRAFT_REFRESH_SECONDS':'60'}
        with patch.dict(edge.os.environ,env),patch.object(edge,'HTTPServer') as server,patch.object(edge.time,'monotonic',return_value=100) as clock:
            edge.serve(self.manager,'127.0.0.1',8787)
            tick=server.return_value.service_actions
            with patch.object(self.manager,'refresh',return_value={'items':[],'errors':[]}) as refresh:
                clock.return_value=159; tick(); refresh.assert_not_called()
                clock.return_value=160; tick(); self.assertEqual(refresh.call_count,1)
                clock.return_value=161; tick(); self.assertEqual(refresh.call_count,1)
                refresh.side_effect=RuntimeError('offline')
                clock.return_value=220; tick(); self.assertEqual(refresh.call_count,2)
                clock.return_value=221; tick(); self.assertEqual(refresh.call_count,2)
                refresh.side_effect=None
                clock.return_value=280; tick(); self.assertEqual(refresh.call_count,3)
    def test_scheduled_refresh_disabled(self):
        env={'ARTCRAFT_API_TOKEN':'random-test-token-for-local-api-123','ARTCRAFT_REFRESH_SECONDS':'0'}
        with patch.dict(edge.os.environ,env),patch.object(edge,'HTTPServer') as server:
            edge.serve(self.manager,'127.0.0.1',8787)
            with patch.object(self.manager,'refresh') as refresh:
                server.return_value.service_actions(); refresh.assert_not_called()

if __name__=='__main__': unittest.main(verbosity=2)
