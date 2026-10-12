#!/usr/bin/env bash
set -euo pipefail
task_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
cd "$task_dir"
image="${1:-${ARTCRAFT_IMAGE:-}}"
if [[ -z "$image" ]]; then
    echo 'Usage: bash setup-pullio.sh ghcr.io/YOUR-ACCOUNT/YOUR-REPO:latest' >&2
    echo 'Publish the worker image first; the included workflow prepares GHCR publication.' >&2
    exit 1
fi
command -v python3 >/dev/null
docker compose version >/dev/null
python3 - "$task_dir" "$image" <<'PY'
import json, os, re, secrets, sys
from pathlib import Path
folder=Path(sys.argv[1]); image=sys.argv[2]
if not re.fullmatch(r'[a-z0-9][a-z0-9./:_-]+',image) or '@' in image or '/' not in image:
    raise SystemExit('Use a lowercase published registry/image:rolling-tag reference, not a digest')
if any(x in str(folder) for x in ('\n','\r','$',':')):
    raise SystemExit('Project path cannot contain newline, dollar sign or colon')
path=folder/'.env'
text=path.read_text() if path.exists() else (folder/'.env.example').read_text()
lines=text.splitlines()
def set_value(key,value):
    encoded=key+'='+json.dumps(value)
    for i,line in enumerate(lines):
        if line.startswith(key+'='): lines[i]=encoded; break
    else: lines.append(encoded)
token=next((line.split('=',1)[1].strip().strip('"\'') for line in lines if line.startswith('ARTCRAFT_API_TOKEN=')), '')
if len(token)<24 or token.startswith('replace-with-'): set_value('ARTCRAFT_API_TOKEN',secrets.token_urlsafe(32))
set_value('ARTCRAFT_IMAGE',image)
set_value('ARTCRAFT_PROJECT_DIR',str(folder))
temporary=folder/'.env.tmp'
fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
with os.fdopen(fd,'w') as output: output.write('\n'.join(lines)+'\n')
temporary.chmod(0o600); temporary.replace(path)
PY
if [[ -f compose.yaml && ! -f compose.before-pullio.yaml ]]; then
    cp -p compose.yaml compose.before-pullio.yaml
fi
cp compose.pullio.yaml compose.yaml
docker compose config --quiet
docker compose pull artcraft
docker compose build pullio
docker compose up -d --no-build
echo 'Pullio is running. It automatically checks and replaces the published worker image.'
echo 'Check logs with: docker compose logs -f pullio'
