from pathlib import Path
import importlib.util
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('build_packages',ROOT/'scripts/build_packages.py')
builder=importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)

class PackageTests(unittest.TestCase):
    def test_every_download_has_its_companion_files(self):
        requirements={
            'ArtCraft-Windows-Installer.zip':{'Run-ArtCraft-Installer.cmd','Install-ArtCraft.ps1','START-HERE.txt'},
            'ArtCraft-Linux-Installer.zip':{'linux-edge/run-installer.sh','linux-edge/artcraft_edge.py','START-HERE.txt'},
            'ArtCraft-Docker-LLM.zip':{'linux-edge/Dockerfile','linux-edge/artcraft_edge.py','linux-edge/mcp_bridge.py','linux-edge/compose.yaml','linux-edge/.env.example'},
            'ArtCraft-Pullio-Setup.zip':{'linux-edge/setup-pullio.sh','linux-edge/compose.pullio.yaml','linux-edge/.env.example','linux-edge/pullio/Dockerfile','linux-edge/pullio/run-pullio.sh'},
            'ArtCraft-Image-Publishing.zip':{'.github/workflows/publish-image.yml','linux-edge/Dockerfile','linux-edge/artcraft_edge.py','tests/test_artcraft_edge.py','tests/test_pullio_setup.py'},
        }
        with tempfile.TemporaryDirectory() as folder:
            builder.build(folder)
            for name,required in requirements.items():
                with zipfile.ZipFile(Path(folder)/name) as archive:
                    names=set(archive.namelist())
                    self.assertTrue(required<=names,(name,required-names))
                    self.assertIn('START-HERE.txt',names)
                    self.assertFalse(any(Path(n).name=='.env' for n in names))
                    self.assertIsNone(archive.testzip())
            self.assertEqual(len((Path(folder)/'SHA256SUMS.txt').read_text().splitlines()),5)
    def test_platform_packages_exclude_other_setup_options(self):
        with tempfile.TemporaryDirectory() as folder:
            builder.build(folder)
            def names(package):
                with zipfile.ZipFile(Path(folder)/package) as archive: return archive.namelist()
            self.assertFalse(any(n.startswith('linux-edge/') for n in names('ArtCraft-Windows-Installer.zip')))
            self.assertFalse(any(n.endswith('Dockerfile') for n in names('ArtCraft-Linux-Installer.zip')))
            self.assertFalse(any('/pullio/' in n for n in names('ArtCraft-Docker-LLM.zip')))
            self.assertFalse(any(n.endswith('artcraft_edge.py') for n in names('ArtCraft-Pullio-Setup.zip')))

if __name__=='__main__': unittest.main()
