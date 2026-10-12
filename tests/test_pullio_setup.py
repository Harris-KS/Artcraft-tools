from pathlib import Path
import json
import subprocess
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent.parent
LINUX=ROOT/'linux-edge'
SCRIPT=(LINUX/'setup-pullio.sh').read_text()
EMBEDDED=SCRIPT.split("<<'PY'\n",1)[1].split('\nPY\n',1)[0]
CODE=compile(EMBEDDED,'setup-pullio.sh embedded Python','exec')

class PullioSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'tests')
        self.folder=Path(self.temp.name)
        self.relative=str(self.folder.relative_to(Path.cwd()))
        (self.folder/'.env.example').write_text((LINUX/'.env.example').read_text())
    def tearDown(self): self.temp.cleanup()
    def configure(self,image):
        with patch.object(sys,'argv',['setup',self.relative,image]): exec(CODE,{'__name__':'__main__'})
    def test_generates_token_and_registry_settings(self):
        self.configure('ghcr.io/example/worker:latest')
        text=(self.folder/'.env').read_text()
        line=next(x for x in text.splitlines() if x.startswith('ARTCRAFT_API_TOKEN='))
        token=json.loads(line.split('=',1)[1])
        self.assertGreaterEqual(len(token),24)
        self.assertFalse(token.startswith('replace-with-'))
        self.assertIn('ARTCRAFT_IMAGE="ghcr.io/example/worker:latest"',text)
        self.assertIn('ARTCRAFT_PROJECT_DIR=',text)
        self.configure('ghcr.io/example/worker:stable')
        text=(self.folder/'.env').read_text()
        self.assertIn(line,text)
        self.assertIn('ARTCRAFT_IMAGE="ghcr.io/example/worker:stable"',text)
    def test_invalid_registry_reference_rejected(self):
        for image in ['image;echo bad','ghcr.io/Example/worker:latest','ghcr.io/example/worker@sha256:abc']:
            with self.assertRaises(SystemExit): self.configure(image)
    def test_default_filename_and_scoped_labels(self):
        compose=(LINUX/'compose.pullio.yaml').read_text()
        self.assertIn('org.hotio.pullio.artcraft.update: "true"',compose)
        self.assertNotIn('org.hotio.pullio.update:',compose)
        self.assertIn('cp compose.pullio.yaml compose.yaml',SCRIPT)
        self.assertIn('docker compose up -d --no-build',SCRIPT)
        self.assertIn('--tag artcraft',(LINUX/'pullio/run-pullio.sh').read_text())
    def test_shell_syntax(self):
        bash=Path(shutil.which('bash') or 'C:/Program Files/Git/bin/bash.exe')
        if not bash.exists(): self.skipTest('Bash unavailable')
        for name in ['setup-pullio.sh','pullio/run-pullio.sh','run-installer.sh']:
            result=subprocess.run([str(bash),'-n',str(LINUX/name)],capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__': unittest.main(verbosity=2)
