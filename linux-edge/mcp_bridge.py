#!/usr/bin/env python3
"""Small stdio MCP bridge to the model-neutral ArtCraft HTTP API (stdlib only)."""
import json
import os
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError

TOOLS=[
    {'name':'artcraft_catalog','description':'List discovered GitHub apps/resources and installed CLI tools. Set refresh=true to discover newly published items and versions. Discovery does not install apps.',
     'inputSchema':{'type':'object','properties':{'refresh':{'type':'boolean','default':False}},'additionalProperties':False}},
    {'name':'artcraft_run','description':'Run an installed ArtCraft CLI without a shell. First inspect --help; CLI commands differ by app. Use relative paths for output in the returned job_directory, or /files paths in Docker. Does not install apps. Exit code and stderr identify failures.',
     'inputSchema':{'type':'object','properties':{'app':{'type':'string'},'args':{'type':'array','items':{'type':'string'},'maxItems':128},'timeout':{'type':'integer','minimum':1,'maximum':300,'default':120}},'required':['app','args'],'additionalProperties':False}}
]

def api(path,body=None):
    token=os.environ.get('ARTCRAFT_API_TOKEN','')
    if not token: raise ValueError('ARTCRAFT_API_TOKEN is not set in the MCP process environment')
    url=os.environ.get('ARTCRAFT_API_URL','http://127.0.0.1:8787').rstrip('/')+path
    headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'}
    request=Request(url,data=None if body is None else json.dumps(body).encode(),headers=headers)
    try:
        with urlopen(request,timeout=3600 if path=='/refresh' else 330) as response: return json.load(response)
    except HTTPError as exc:
        detail=exc.read(100000).decode('utf-8',errors='replace')
        raise ValueError(f'ArtCraft API HTTP {exc.code}: {detail}') from exc

def dispatch(message):
    method=message.get('method'); params=message.get('params') or {}
    if method=='initialize':
        supported=('2025-11-25','2025-06-18','2025-03-26','2024-11-05')
        requested=params.get('protocolVersion')
        return {'protocolVersion':requested if requested in supported else supported[0],
                'capabilities':{'tools':{}},'serverInfo':{'name':'artcraft-edge','version':'2.0.0'},
                'instructions':'Refresh the catalog to find new apps. An operator installs apps separately. Discover the installed CLI with --help before generating files. Verify exit_code and files; do not claim a failed tool produced output.'}
    if method=='ping': return {}
    if method=='tools/list': return {'tools':TOOLS}
    if method=='tools/call':
        name=params.get('name'); args=params.get('arguments') or {}
        try:
            if name=='artcraft_catalog': result=api('/refresh',{}) if args.get('refresh') else api('/catalog')
            elif name=='artcraft_run': result=api('/run',args)
            else: raise ValueError('Unknown tool')
            return {'content':[{'type':'text','text':json.dumps(result)}],'isError':bool(result.get('exit_code',0))}
        except Exception as exc: return {'content':[{'type':'text','text':str(exc)}],'isError':True}
    raise ValueError('Method not found')

def main():
    for line in sys.stdin:
        message=None
        try:
            message=json.loads(line)
            if not isinstance(message,dict): raise ValueError('Expected JSON-RPC object')
            if 'id' not in message: continue  # Notifications, including initialized/cancellation.
            response={'jsonrpc':'2.0','id':message['id'],'result':dispatch(message)}
        except Exception as exc:
            response={'jsonrpc':'2.0','id':message.get('id') if isinstance(message,dict) else None,
                      'error':{'code':-32700 if message is None else -32601,'message':str(exc)}}
        print(json.dumps(response),flush=True)

if __name__=='__main__': main()
