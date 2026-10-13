"""Installed-version decisions: no actual app download, installation or execution."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('updates_edge',Path(__file__).resolve().parents[1]/'linux-edge/artcraft_edge.py')
edge=importlib.util.module_from_spec(spec); spec.loader.exec_module(edge)

class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
        self.manager=edge.Manager(self.root/'state',self.root/'files','x86_64')
        self.app=self.manager.root/'apps/newcraft/old'; self.app.mkdir(parents=True)
        self.manager.installed['newcraft']={'version':'v1.0.0','root':str(self.app)}
        self.manager.snapshot['items']=[{'id':'newcraft','repo':'newcraft','kind':'app','version':'v2.0.0','status':'Ready'}]
    def tearDown(self): self.temp.cleanup()
    def test_versions(self):
        self.assertEqual(edge.version_number('artcraft-v0.41.0'),(0,41,0,0))
        self.assertEqual(edge.update_state({'version':'1.2.3.0'},'v1.2.3'),'Up to date')
        self.assertEqual(edge.update_state({'version':'v1.9.0'},'v1.10.0'),'Update available')
        self.assertIn('downgrade blocked',edge.update_state({'version':'v2.0.0'},'v1.0.0'))
        for text in ('','v1.0.0-rc1','banana','1.2','1.2.3evil'):
            self.assertIsNone(edge.version_number(text))
    def test_native_package_database_does_not_count_removed_packages(self):
        import subprocess
        result=subprocess.CompletedProcess([],0,'photocraft\t0.8.2\tinstalled\nwordcraft\t0.6.1\tconfig-files\nartcraft-launcher\t0.3.2\tinstalled\n','')
        with patch.object(edge.sys,'platform','linux'),patch.object(edge.shutil,'which',return_value='/usr/bin/dpkg-query'),patch.object(edge.subprocess,'run',return_value=result) as run:
            packages=edge.system_packages()
        self.assertIn('photocraft',packages); self.assertIn('craft-launcher',packages); self.assertNotIn('wordcraft',packages)
        self.assertEqual(run.call_args.args[0][0],'dpkg-query')
    def test_catalog_does_not_accumulate_status_and_ignores_missing_install(self):
        first=self.manager.catalog()['items'][0]; second=self.manager.catalog()['items'][0]
        self.assertEqual(first,second); self.assertEqual(first['installed_version'],'v1.0.0')
        self.assertEqual(first['update_state'],'Update available')
        self.app.rmdir()
        self.assertEqual(self.manager.catalog()['items'][0]['update_state'],'Not installed')
    def test_no_download_when_current_newer_or_unknown(self):
        for version in ('v2.0.0','v3.0.0','unknown'):
            self.manager.installed['newcraft']['version']=version
            with patch.object(edge.sys,'platform','linux'),patch.object(edge,'github',return_value={'tag_name':'v2.0.0'}),patch.object(self.manager,'download') as download:
                self.assertIn('Skipped',self.manager.install('newcraft')['status']); download.assert_not_called()
    def test_system_install_is_reported_and_not_duplicated(self):
        self.app.rmdir(); self.manager.external={'newcraft':{'version':'1.0.0','source':'system package manager'}}
        row=self.manager.catalog()['items'][0]
        self.assertEqual(row['installed_source'],'system package manager')
        with patch.object(edge.sys,'platform','linux'),patch.object(edge,'github',return_value={'tag_name':'v2.0.0'}),patch.object(self.manager,'download') as download:
            self.assertIn('system installation',self.manager.install('newcraft')['status']); download.assert_not_called()
    def test_upgrade_uses_fresh_release_after_menu(self):
        fresh={'tag_name':'v3.0.0'}
        archive=self.root/'fake.tar.gz'; archive.touch()
        with patch.object(edge.sys,'platform','linux'),patch.object(edge,'github',return_value=fresh),patch.object(self.manager,'download',return_value=(archive,'v3.0.0')) as download,patch.object(self.manager,'unpack'):
            result=self.manager.install('newcraft')
        self.assertEqual(result['version'],'v3.0.0'); self.assertEqual(download.call_args.kwargs['release'],fresh)
        self.assertTrue(self.app.exists())
    def test_selector_offers_updates_but_waits_for_install_command(self):
        data=self.manager.catalog(); row=data['items'][0]; row.update(name='newcraft',new=False,description='editor',compare='test')
        with patch.object(self.manager,'refresh',return_value=data),patch('builtins.input',side_effect=['y','Q']),patch('builtins.print'),patch.object(self.manager,'install') as install:
            edge.selector(self.manager,False); install.assert_not_called()
        with patch.object(self.manager,'refresh',return_value=data),patch('builtins.input',side_effect=['n','U','I']),patch('builtins.print'),patch.object(self.manager,'install',return_value={}) as install:
            edge.selector(self.manager,False); install.assert_called_once_with('newcraft',False)

if __name__=='__main__': unittest.main()
