#!/usr/bin/env python3
"""Live Storytold catalog, per-user Linux packages, and model-neutral local API.
Python 3.10+; standard library only. Run --help for commands.
"""
import argparse
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import urlparse

COMPARISONS = dict(zip(
    ['photocraft','lightcraft','vectorcraft','filmcraft','effectcraft','designcraft',
     'pdfcraft','wordcraft','gridcraft','deckcraft','cadcraft','soundcraft'],
    ['Adobe Photoshop','Adobe Lightroom Classic','Adobe Illustrator','Adobe Premiere Pro',
     'Adobe After Effects','Adobe InDesign','Adobe Acrobat Pro','Microsoft Word',
     'Microsoft Excel','Microsoft PowerPoint','Autodesk AutoCAD','Avid Pro Tools']))

def asset_key(name):
    return re.sub(r'\d+\.\d+\.\d+(?:[-+]\d+)?', 'VERSION', name)

def version_number(text):
    match=re.fullmatch(r'(?:[A-Za-z][A-Za-z-]*-)?v?(\d+)\.(\d+)\.(\d+)(?:\.(\d+))?',text or '')
    return tuple(int(x or 0) for x in match.groups()) if match else None

def update_state(installed, latest):
    if not installed: return 'Not installed'
    old=version_number(installed.get('version')); new=version_number(latest)
    if old is None or new is None: return 'Installed; version comparison unavailable'
    if new>old: return 'Update available'
    if new==old: return 'Up to date'
    return 'Installed version is newer; downgrade blocked'

def system_packages():
    """Read native package databases. Never execute app binaries or modify packages."""
    if sys.platform!='linux': return {}
    if shutil.which('dpkg-query'):
        command=['dpkg-query','-W','-f=${Package}\t${Version}\t${db:Status-Status}\n']
    elif shutil.which('rpm'):
        command=['rpm','-qa','--qf','%{NAME}\t%{VERSION}\tinstalled\n']
    else: return {}
    try: result=subprocess.run(command,capture_output=True,text=True,timeout=15)
    except (OSError,subprocess.SubprocessError): return {}
    if result.returncode: return {}
    packages={}
    for line in result.stdout.splitlines():
        fields=line.split('\t')
        if len(fields)!=3 or fields[2]!='installed': continue
        name=fields[0].split(':')[0].lower()
        if name=='artcraft-launcher': name='craft-launcher'
        packages[name]={'version':fields[1],'source':'system package manager'}
    return packages

def architecture():
    cpu = platform.machine().lower()
    if cpu in ('x86_64','amd64'): return 'x86_64'
    if cpu in ('aarch64','arm64'): return 'aarch64'
    raise ValueError(f'Unsupported CPU: {cpu}; supported: x64 and ARM64')

def github(path):
    headers = {'User-Agent':'ArtCraft-Edge-Catalog','Accept':'application/vnd.github+json'}
    if os.environ.get('GITHUB_TOKEN'): headers['Authorization']='Bearer '+os.environ['GITHUB_TOKEN']
    try:
        with urlopen(Request('https://api.github.com/'+path, headers=headers), timeout=45) as response:
            return json.load(response)
    except HTTPError as exc:
        if exc.code == 404: return None
        if exc.code in (403,429): raise RuntimeError('GitHub refused/rate-limited the request. Wait, or set GITHUB_TOKEN.') from exc
        raise

def official_url(url, repo):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.netloc != 'github.com' or not parsed.path.startswith(f'/storytold/{repo}/releases/download/'):
        raise ValueError('Download is outside the official repository releases')

def package_for(release, arch):
    aliases = r'(?:x86_64|x64|amd64)' if arch == 'x86_64' else r'(?:aarch64|arm64)'
    assets = [a for a in release.get('assets',[]) if re.search(r'[-_]linux[-_]'+aliases+r'(?:[-_.]|$)',a['name'],re.I)]
    for suffix in ('.tar.gz','.deb'):
        found = [a for a in assets if a['name'].endswith(suffix) and not re.search(r'(plugin|addon|extension)',a['name'],re.I)]
        # Some apps publish a second CLI-only tarball beside the full app tree.
        # Prefer the full tree; use the CLI-only package when it is the only option.
        found = [a for a in found if not re.search(r'[-_]cli[-_]',a['name'],re.I)] or found
        if len(found)>1: raise ValueError('Ambiguous Linux package; review release manually')
        if found: return found[0]
    return None

class Manager:
    def __init__(self, root, files, arch=None):
        self.root=Path(root).expanduser().resolve()
        self.files=Path(files).expanduser().resolve()
        self.root.mkdir(parents=True,exist_ok=True)
        self.files.mkdir(parents=True,exist_ok=True)
        self.arch=arch or architecture()
        self.catalog_path=self.root/'catalog.json'
        self.installed_path=self.root/'installed.json'
        self.snapshot=self.load(self.catalog_path,{'items':[], 'repositories':[], 'errors':[], 'checked_at':None})
        self.installed=self.load(self.installed_path,{})
        self.external={}

    @staticmethod
    def load(path, default):
        if not path.exists(): return default
        return json.loads(path.read_text(encoding='utf-8'))

    @staticmethod
    def save(path, value):
        temp=path.with_suffix('.tmp')
        temp.write_text(json.dumps(value,indent=2),encoding='utf-8')
        temp.replace(path)

    def refresh(self):
        self.external=system_packages()
        repos=[]; page=1
        while True:
            batch=github(f'orgs/storytold/repos?type=public&per_page=100&page={page}&sort=full_name') or []
            repos.extend(batch)
            if len(batch)<100: break
            page+=1
        items=[]; errors=[]
        prior={x['id'] for x in self.snapshot['items']}
        prior_repos={x['name'] for x in self.snapshot.get('repositories',[])}
        first_run=self.snapshot['checked_at'] is None
        for repo in repos:
            name=repo['name']
            if repo.get('owner',{}).get('login','').lower()!='storytold' or not re.fullmatch(r'[A-Za-z0-9_.-]+',name): continue
            row={'id':name,'repo':name,'name':name,'description':repo.get('description') or 'No repository description provided.',
                 'compare':COMPARISONS.get(name,'Not documented; consult the README'),
                 'url':f'https://github.com/storytold/{name}','kind':'repository','version':None,'asset':None,
                 'status':'No supported Linux release package','new':False}
            if repo.get('archived') or repo.get('fork') or repo.get('disabled'):
                row['status']='Archived, forked or disabled repository; listed for discovery only'
                items.append(row); continue
            try:
                release=github(f'repos/storytold/{name}/releases/latest')
                if release and not release.get('draft') and not release.get('prerelease'):
                    row['version']=release['tag_name']
                    package=package_for(release,self.arch)
                    if package:
                        row.update(kind='app',asset=package,status='Ready; official Linux package')
                    row['new']=not first_run and name not in prior_repos
                    items.append(row)
                    for asset in release.get('assets',[]):
                        if not (asset['name'].endswith(('.wasm','.jsx')) or re.search(r'(plugin|addon|add-on|extension).*\.zip$',asset['name'],re.I)): continue
                        identity=name+':'+asset_key(asset['name'])
                        items.append({'id':identity,'repo':name,'name':asset['name'],'kind':'resource',
                                      'description':'Release add-on candidate. Verified download; follow README to install/load. Compatibility is not inferred.',
                                      'compare':'Not documented','url':row['url'],'version':release['tag_name'],
                                      'asset':asset,'status':'Download; manual installation','new':not first_run and identity not in prior})
                    continue
                row['status']='No published stable release'
            except Exception as exc:
                row['status']='Release check failed: '+str(exc)
                errors.append({'repo':name,'error':str(exc)})
            row['new']=not first_run and name not in prior_repos
            items.append(row)
        # The report includes every public repository, even libraries without installers.
        self.snapshot={'checked_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'architecture':self.arch,
                       'repositories':[{'name':r['name'],'description':r.get('description'),'created_at':r.get('created_at')} for r in repos],
                       'items':items,'errors':errors,'first_scan':first_run}
        self.save(self.catalog_path,self.snapshot)
        return self.catalog()

    def catalog(self):
        result=dict(self.snapshot)
        result['items']=[dict(row) for row in self.snapshot['items']]
        for row in result['items']:
            if row['kind']!='app': continue
            installed=self.detected_install(row['repo'])
            row['installed_version']=installed.get('version') if installed else None
            row['installed_source']=installed.get('source','private installer') if installed else None
            row['update_state']=update_state(installed,row.get('version'))
            if installed:
                row['status']+=' | '+row['update_state']+' (installed: '+str(row['installed_version'])+')'
                if installed.get('source'): row['status']+='; update with your native package manager or launcher'
        result['installed']=self.installed
        result['cli_tools']={repo:row['cli'] for repo,row in self.installed.items() if row.get('cli')}
        return result

    def detected_install(self, repo):
        row=self.installed.get(repo,{})
        if row.get('root') and Path(row['root']).is_dir(): return row
        return self.external.get(repo)

    def item(self, identity):
        found=[x for x in self.snapshot['items'] if x['id']==identity]
        if len(found)!=1: raise ValueError('Unknown catalog ID. Refresh catalog first.')
        return found[0]

    def download(self, item, folder, release=None):
        # Always fetch the current stable release again just before downloading.
        release=release or github(f"repos/storytold/{item['repo']}/releases/latest")
        if not release or release.get('draft') or release.get('prerelease'): raise ValueError('No current stable release')
        if item['kind']=='app': asset=package_for(release,self.arch)
        else:
            matches=[a for a in release.get('assets',[]) if asset_key(a['name'])==asset_key(item['asset']['name'])]
            if len(matches)!=1: raise ValueError('Resource missing or ambiguous in current release')
            asset=matches[0]
        if not asset: raise ValueError('Current release has no compatible package')
        name=asset['name']
        if not re.fullmatch(r'[A-Za-z0-9_. -]+',name) or name in ('.','..'): raise ValueError('Unsafe filename')
        official_url(asset['browser_download_url'],item['repo'])
        digest=asset.get('digest') or ''
        if re.fullmatch(r'sha256:[a-fA-F0-9]{64}',digest): expected=digest.split(':')[1].lower()
        else:
            sums=[a for a in release['assets'] if a['name'].lower()=='sha256sums.txt']
            if len(sums)!=1: raise ValueError('No published SHA-256 checksum; download refused')
            official_url(sums[0]['browser_download_url'],item['repo'])
            with urlopen(sums[0]['browser_download_url'],timeout=60) as response: text=response.read(1024*1024).decode('utf-8')
            expected=None
            for line in text.splitlines():
                match=re.match(r'^([a-fA-F0-9]{64})\s+\*?(.+?)\s*$',line)
                if match and match[2]==name: expected=match[1].lower(); break
            if not expected: raise ValueError('Package absent from SHA256SUMS.txt')
        folder.mkdir(parents=True,exist_ok=True)
        path=folder/name; partial=folder/(name+'.partial')
        digest=hashlib.sha256(); count=0
        try:
            with urlopen(asset['browser_download_url'],timeout=120) as response, partial.open('wb') as output:
                while True:
                    chunk=response.read(1024*1024)
                    if not chunk: break
                    count+=len(chunk)
                    if count>2*1024**3: raise ValueError('Download exceeds 2 GiB limit')
                    digest.update(chunk); output.write(chunk)
            if not hmac.compare_digest(digest.hexdigest(),expected): raise ValueError('SHA-256 mismatch; package will not be used')
            partial.replace(path)
        finally:
            partial.unlink(missing_ok=True)
        return path,release['tag_name']

    @staticmethod
    def unpack(archive, destination):
        if archive.name.endswith('.tar.gz'):
            with tarfile.open(archive,'r:gz') as tar:
                members=tar.getmembers()
                if len(members)>50000 or sum(m.size for m in members)>4*1024**3: raise ValueError('Archive exceeds extraction limits')
                for member in members:
                    resolved=(destination/member.name).resolve()
                    if not resolved.is_relative_to(destination.resolve()) or not (member.isfile() or member.isdir()):
                        raise ValueError('Archive contains unsafe path, link or special file')
                if hasattr(tarfile,'data_filter'):
                    tar.extractall(destination,members=members,filter='data')
                else:
                    tar.extractall(destination,members=members)
        elif archive.name.endswith('.deb'):
            if not shutil.which('dpkg-deb'): raise ValueError('This package needs dpkg-deb; install dpkg or use the Docker image')
            subprocess.run(['dpkg-deb','--extract',str(archive),str(destination)],check=True,timeout=180)
        else: raise ValueError('Unsupported Linux package format')

    def install(self, identity, download_only=False):
        if sys.platform!='linux' and not download_only: raise ValueError('Linux installation requires Linux or Docker')
        item=self.item(identity)
        if item['kind'] not in ('app','resource'): raise ValueError('This repository has no supported installable package')
        release=github(f"repos/storytold/{item['repo']}/releases/latest")
        if not release or release.get('draft') or release.get('prerelease'): raise ValueError('No current stable release')
        if item['kind']=='app' and not download_only:
            installed=self.detected_install(item['repo'])
            state=update_state(installed,release['tag_name'])
            if installed and installed.get('source'):
                return {'id':identity,'status':'Skipped: system installation; update with your native package manager or launcher','update_state':state}
            if state not in ('Not installed','Update available'):
                return {'id':identity,'status':'Skipped: '+state,'version':installed.get('version')}
        run=self.root/'downloads'/uuid.uuid4().hex
        archive,version=self.download(item,run,release=release)
        if download_only or item['kind']=='resource':
            return {'id':identity,'version':version,'download':str(archive),'status':'Verified download. Follow repository instructions for manual resource installation.' if item['kind']=='resource' else 'Downloaded; not installed'}
        destination=self.root/'apps'/item['repo']/uuid.uuid4().hex
        destination.mkdir(parents=True)
        try: self.unpack(archive,destination)
        except Exception:
            shutil.rmtree(destination); raise
        cli_name=item['repo']+'-cli'
        cli=[p for p in destination.rglob(cli_name) if p.is_file() and not p.is_symlink()]
        executable=[p for p in destination.rglob(item['repo']) if p.is_file() and not p.is_symlink()]
        if len(cli)==1: cli[0].chmod(cli[0].stat().st_mode | 0o100)
        row={'version':version,'root':str(destination),'cli':str(cli[0]) if len(cli)==1 else None,
             'desktop':str(executable[0]) if len(executable)==1 else None}
        self.installed[item['repo']]=row
        self.save(self.installed_path,self.installed)
        return {'id':identity,**row,'status':'Installed privately; previous versions retained. CLI readiness requires --help check.'}

    def run_cli(self, repo, args, timeout=120):
        if not isinstance(args,list) or len(args)>128 or any(not isinstance(x,str) or '\0' in x or len(x)>65536 for x in args):
            raise ValueError('args must be a bounded array of strings')
        if not isinstance(timeout,int) or not 1<=timeout<=300: raise ValueError('timeout must be 1-300 seconds')
        row=self.installed.get(repo,{})
        cli=row.get('cli')
        if not cli or not Path(cli).is_file() or Path(cli).is_symlink(): raise ValueError('No installed CLI for this app; install it first')
        if not Path(cli).resolve().is_relative_to(self.root/'apps'): raise ValueError('CLI path outside managed apps')
        job=self.files/'jobs'/uuid.uuid4().hex
        job.mkdir(parents=True)
        # Never pass the API/GitHub credentials into app processes; never invoke a shell.
        env={'PATH':'/usr/local/bin:/usr/bin:/bin','HOME':str(job),'TMPDIR':str(job),'LANG':'C.UTF-8'}
        stdout=job/'stdout.txt'; stderr=job/'stderr.txt'
        with stdout.open('wb') as out, stderr.open('wb') as err:
            process=subprocess.Popen([cli,*args],cwd=job,env=env,stdout=out,stderr=err,start_new_session=True)
            try: code=process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL); process.wait()
                raise ValueError(f'CLI timed out; diagnostics: {job}')
        def tail(path):
            with path.open('rb') as stream:
                stream.seek(max(0,path.stat().st_size-100000)); return stream.read().decode('utf-8',errors='replace')
        return {'exit_code':code,'stdout':tail(stdout),'stderr':tail(stderr),'job_directory':str(job),
                'files':[str(p.relative_to(self.files)) for p in job.rglob('*') if p.is_file() and not p.is_symlink()]}

def serve(manager, host, port):
    token=os.environ.get('ARTCRAFT_API_TOKEN','')
    if len(token)<24 or token.startswith('replace-with-'): raise ValueError('Set ARTCRAFT_API_TOKEN to a random token of at least 24 characters')
    interval=float(os.environ.get('ARTCRAFT_REFRESH_SECONDS','21600'))
    if not math.isfinite(interval) or interval<0 or (interval and interval<60): raise ValueError('ARTCRAFT_REFRESH_SECONDS must be 0 (disabled) or at least 60')
    class Handler(BaseHTTPRequestHandler):
        def reply(self,code,data):
            body=json.dumps(data).encode()
            self.send_response(code); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(body)))
            self.end_headers(); self.wfile.write(body)
        def authorized(self):
            # This is a JSON tool API, not a browser endpoint. Do not accept browser-origin requests.
            if self.headers.get('Origin') or not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+token):
                self.reply(401,{'error':'Authorized local tool client required'}); return False
            return True
        def do_GET(self):
            if not self.authorized(): return
            if self.path=='/catalog': self.reply(200,manager.catalog())
            elif self.path=='/health': self.reply(200,{'ok':True})
            else: self.reply(404,{'error':'Unknown endpoint'})
        def do_POST(self):
            if not self.authorized(): return
            try:
                length=int(self.headers.get('Content-Length','0'))
                if length<0 or length>1024*1024: raise ValueError('Invalid request length')
                body=json.loads(self.rfile.read(length) or '{}')
                if not isinstance(body,dict): raise ValueError('Expected JSON object')
                if self.path=='/refresh': result=manager.refresh()
                elif self.path=='/run': result=manager.run_cli(body['app'],body['args'],body.get('timeout',120))
                elif self.path=='/install':
                    if os.environ.get('ARTCRAFT_ALLOW_API_INSTALL')!='1':
                        self.reply(403,{'error':'API installs disabled; use the operator installer menu'}); return
                    result=manager.install(body['id'],bool(body.get('download_only',False)))
                else: self.reply(404,{'error':'Unknown endpoint'}); return
                self.reply(200,result)
            except Exception as exc: self.reply(400,{'error':str(exc)})
        def log_message(self, fmt, *args): print(fmt % args,file=sys.stderr)
    print(f'ArtCraft API listening on {host}:{port}; catalog interval {interval:g}s; no automatic package upgrades',file=sys.stderr)
    server=HTTPServer((host,port),Handler)
    next_refresh=time.monotonic()+interval
    def scheduled_refresh():
        nonlocal next_refresh
        if not interval or time.monotonic()<next_refresh: return
        try:
            result=manager.refresh()
            print(f"Scheduled catalog refresh completed: {len(result['items'])} items, {len(result['errors'])} release-check errors",file=sys.stderr)
        except Exception as exc:
            print('Scheduled catalog refresh failed; previous catalog retained: '+str(exc),file=sys.stderr)
        finally:
            next_refresh=time.monotonic()+interval
    # Serial HTTPServer invokes this between requests; a CLI job finishes first.
    server.service_actions=scheduled_refresh
    try: server.serve_forever()
    finally: server.server_close()

def selector(manager, download_only):
    items=manager.refresh()['items']; selected=set()
    updates={i for i,x in enumerate(items,1) if x.get('update_state')=='Update available' and x.get('installed_source')=='private installer'}
    if updates and input(f'{len(updates)} installed apps have updates. Select those updates? [y/N] ').strip().lower() in ('y','yes'):
        selected=set(updates)
    while True:
        print('\nNumbers toggle checkboxes; A = all apps; U = updates only; N = none; I = install/download; Q = quit')
        for index,item in enumerate(items,1):
            mark='x' if index in selected else ' '
            if item['kind']=='repository': mark='-'
            new='NEW ' if item['new'] else ''
            print(f"{index:2}. [{mark}] {new}{item['name']} {item['version'] or ''} | {item['status']}")
            print(f"     {item['description']} | Compare: {item['compare']}")
        answer=input('Selection: ').strip().upper()
        if answer=='Q': return
        if answer=='A': selected={i for i,x in enumerate(items,1) if x['kind']=='app'}; continue
        if answer=='N': selected.clear(); continue
        if answer=='U': selected=set(updates); continue
        if answer=='I':
            for i in sorted(selected):
                try: print(json.dumps(manager.install(items[i-1]['id'],download_only),indent=2))
                except Exception as exc: print(f"FAILED {items[i-1]['name']}: {exc}",file=sys.stderr)
            return
        for text in re.split(r'[,\s]+',answer):
            if not text.isdigit() or not 1<=int(text)<=len(items): print('Invalid choice:',text); continue
            index=int(text)
            if items[index-1]['kind']=='repository': print('No supported package for this entry'); continue
            if index in selected: selected.remove(index)
            else: selected.add(index)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',default=os.environ.get('ARTCRAFT_DATA',str(Path.home()/'.local/share/artcraft-edge')))
    parser.add_argument('--files',default=os.environ.get('ARTCRAFT_FILES',str(Path.home()/'ArtCraftFiles')))
    parser.add_argument('--check',action='store_true',help='Refresh and print live catalog JSON')
    parser.add_argument('--download-only',action='store_true')
    parser.add_argument('--install',metavar='CATALOG_ID')
    parser.add_argument('--serve',action='store_true')
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=8787)
    opts=parser.parse_args()
    manager=Manager(opts.root,opts.files)
    if opts.serve:
        try: manager.refresh()
        except Exception as exc: print('Initial discovery failed; cached catalog retained: '+str(exc),file=sys.stderr)
        serve(manager,opts.host,opts.port)
    elif opts.check: print(json.dumps(manager.refresh(),indent=2))
    elif opts.install:
        manager.refresh(); print(json.dumps(manager.install(opts.install,opts.download_only),indent=2))
    else: selector(manager,opts.download_only)

if __name__=='__main__':
    try: main()
    except (KeyboardInterrupt,EOFError): sys.exit(130)
    except Exception as exc: print('ERROR: '+str(exc),file=sys.stderr); sys.exit(1)
