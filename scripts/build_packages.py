#!/usr/bin/env python3
"""Build separate, complete downloads for each setup option (stdlib only)."""
from pathlib import Path
import argparse
import hashlib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REPO = 'https://github.com/Harris-KS/Artcraft-tools'
LINUX_FILES = ['artcraft_edge.py','mcp_bridge.py','Dockerfile','compose.yaml',
               '.env.example','.gitignore','run-installer.sh','setup-pullio.sh',
               'compose.pullio.yaml','pullio/Dockerfile','pullio/run-pullio.sh',
               'publishing/publish-image.yml','README.txt']

WINDOWS_GUIDE = '''WINDOWS INSTALLER
Two options: use this script to select individual apps, or use the official hub:
  https://github.com/storytold/craft-launcher/releases/latest
The hub is called ArtCraft Launcher and manages app installation and updates.
ArtCraft's AI studio is a separate app. The hub is optional for this script.
Leave ArtCraft Launcher unchecked in the menu if you do not want the hub.
1. Extract this ZIP completely (right-click > Extract All).
2. Double-click Run-ArtCraft-Installer.cmd in the extracted folder.
Keep Install-ArtCraft.ps1 beside the launcher. No Linux or Docker setup is included.
The menu checks current GitHub repositories and releases, shows app descriptions,
and installs only selected, checksum-verified Windows MSI packages.
Requires Windows PowerShell 5.1 and internet access. An MSI may request admin rights.
Detailed reference: ArtCraft-Installer-Readme.txt.
To update selected apps later, rerun this script. No automatic desktop upgrades.
'''
LINUX_GUIDE = '''NATIVE LINUX INSTALLER
Two options: use this script to select individual apps, or use the official hub:
  https://github.com/storytold/craft-launcher/releases/latest
Choose the hub's Linux .deb, .rpm or AppImage for your platform; upstream calls it
ArtCraft Launcher. ArtCraft's AI studio is a separate app. The hub is optional here.
Leave craft-launcher unchecked in the menu if you do not want the hub.
Extract this ZIP, open a terminal in linux-edge, and run:
  sh run-installer.sh
For discovery only: sh run-installer.sh --check
Requires Python 3.10+, Linux x64 or ARM64, and internet access.
No Docker or pip packages are needed. Keep artcraft_edge.py beside the launcher.
The menu discovers repositories/releases and unpacks selected app packages privately
under ~/.local/share/artcraft-edge. Native runtime libraries must already be present;
Debian packages require dpkg-deb for extraction. Resources may need manual loading.
This package does not set up Docker, Pullio, or an LLM client.
To update selected apps later, rerun this script. No automatic desktop upgrades.
Private installs made by this script are not the launcher's system package layout;
do not assume the launcher detects or updates those private copies.
'''
DOCKER_GUIDE = '''DOCKER / LOCAL LLM WORKER
Extract this ZIP, open a terminal in linux-edge, and run:
  cp .env.example .env
  python3 -c "import secrets; print(secrets.token_urlsafe(32))"
Put the generated token in .env as ARTCRAFT_API_TOKEN, then:
  docker compose up -d --build
  docker compose exec artcraft python3 artcraft_edge.py
Requires Docker Engine and Docker Compose on Linux x64 or ARM64.
Use the numbered menu to install apps. The localhost API is on port 8787.
Connect an MCP client using python3 /absolute/path/mcp_bridge.py, with
ARTCRAFT_API_URL=http://127.0.0.1:8787 and the same ARTCRAFT_API_TOKEN.
The tools list the catalog and run installed CLI tools. Model training is not needed.
Your client must support HTTP tools or MCP. GUI apps are not hosted by this worker.
App/file volumes persist. GitHub discovery runs every six hours by default.
This package builds the worker locally; automatic image replacement is in the
separate Pullio package. No Windows installer or publishing workflow is included.
Full API guide: https://github.com/Harris-KS/Artcraft-tools/blob/main/linux-edge/README.txt
'''
PULLIO_GUIDE = '''PULLIO / PUBLISHED WORKER DEPLOYMENT
Extract this ZIP, open a terminal in linux-edge, and run:
  bash setup-pullio.sh ghcr.io/harris-ks/artcraft-tools:latest
Requires Docker Engine, Docker Compose, Python 3, and an accessible published image.
It runs both the registry-based worker and Pullio; a local Docker build is not needed.
The setup script creates .env and an API token if needed, makes the supplied template
the default compose.yaml, builds the Pullio wrapper, and starts the services.
Pullio replaces the worker image automatically when that rolling tag changes.
PULLIO_INTERVAL_SECONDS controls image checks (21600 = six hours).
ARTCRAFT_REFRESH_SECONDS separately controls new-app/version discovery inside the worker.
Installed app upgrades remain operator-selected. App and file volumes persist.
To add Pullio to an existing local-worker deployment, extract these files into that
deployment's existing linux-edge directory rather than starting a different project.
Pullio needs Docker-daemon access through the Docker socket and prunes dangling images.
Container replacement may interrupt a running job.
Keep the entire supplied folder, including pullio/, together. No Windows installer
or image-publishing source is included. The MCP bridge is included for LLM clients.
'''
PUBLISH_GUIDE = '''IMAGE PUBLISHING SOURCE
This package is for maintaining/building the worker image, rather than desktop setup.
Extract it and place its .github/, linux-edge/, and tests/ folders at the root of your
own GitHub repository. Enable GitHub Actions, then push to main or run the
Publish ArtCraft edge image workflow manually.
It tests the tools, builds linux/amd64 and linux/arm64 images, and publishes to:
  ghcr.io/<your-lowercase-account>/<your-lowercase-repository>:latest
The workflow uses GitHub's provided GITHUB_TOKEN; do not commit personal credentials.
For the supplied Pullio public-image setup, make the resulting GHCR package public
after its first publication. Private images require extra registry authentication.
This includes worker source and validation dependencies, but no Windows installer.
'''

def linux(names):
    return [(f'linux-edge/{name}', f'linux-edge/{name}') for name in names]

PACKAGES = {
    'ArtCraft-Windows-Installer.zip': (
        [(f'windows/{n}', n) for n in ['Run-ArtCraft-Installer.cmd','Install-ArtCraft.ps1','ArtCraft-Installer-Readme.txt']],
        WINDOWS_GUIDE),
    'ArtCraft-Linux-Installer.zip': (
        linux(['run-installer.sh','artcraft_edge.py']), LINUX_GUIDE),
    'ArtCraft-Docker-LLM.zip': (
        linux(['artcraft_edge.py','mcp_bridge.py','Dockerfile','compose.yaml','.env.example']), DOCKER_GUIDE),
    'ArtCraft-Pullio-Setup.zip': (
        linux(['setup-pullio.sh','compose.pullio.yaml','.env.example','pullio/Dockerfile','pullio/run-pullio.sh','mcp_bridge.py']), PULLIO_GUIDE),
    'ArtCraft-Image-Publishing.zip': (
        linux(LINUX_FILES) + [('.github/workflows/publish-image.yml','.github/workflows/publish-image.yml'),
                            ('tests/test_artcraft_edge.py','tests/test_artcraft_edge.py'),
                            ('tests/test_pullio_setup.py','tests/test_pullio_setup.py')], PUBLISH_GUIDE),
}

def build(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    checksums=[]
    for name,(files,guide) in PACKAGES.items():
        path=output/name
        with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('START-HERE.txt',guide)
            for source,target in files:
                data=(ROOT/source).read_bytes()
                if source.endswith(('.sh','.py','.yml','.yaml')) or source.endswith('Dockerfile'):
                    data=data.replace(b'\r\n',b'\n')
                entry=zipfile.ZipInfo(target)
                entry.create_system=3
                entry.external_attr=((0o100755 if source.endswith(('.sh','.py')) else 0o100644)<<16)
                archive.writestr(entry,data,compress_type=zipfile.ZIP_DEFLATED)
        with zipfile.ZipFile(path) as archive:
            if archive.testzip(): raise ValueError(f'Corrupt archive: {name}')
        checksums.append(hashlib.sha256(path.read_bytes()).hexdigest()+'  '+name)
        print(name)
    (output/'SHA256SUMS.txt').write_text('\n'.join(checksums)+'\n',encoding='utf-8')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default=str(ROOT/'dist'))
    build(parser.parse_args().output)
