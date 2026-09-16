"""Frozen, once-only parallel module regression using existing environments."""

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import socket
import subprocess
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RUN=Path(__file__).resolve().parent
REPO=RUN.parents[1]
STARTER=REPO/"disastertrace-starter"
OUT=RUN/"regression"


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def write(p,v):
    with p.open('x') as f:json.dump(v,f,indent=2,sort_keys=True);f.write('\n')


def module_path(name):
    return (STARTER if name.startswith('tests.') else REPO)/Path(name.replace('.','/')+'.py')


def prepare():
    OUT.mkdir(exist_ok=False)
    shutil.copytree(STARTER/'src/disastertrace',OUT/'source/disastertrace',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    scope=read(RUN/'TEST_SCOPE_DIFF.json')
    historical=set(scope['common']+scope['v11_only']+scope['v12_only'])
    modules={module_path(n.split('::')[0]) for n in historical}
    modules.update(STARTER.glob('tests/test_monitoring_v13_*.py'))
    missing=[str(p) for p in modules if not p.exists()]
    if missing:raise ValueError('Missing registered regression modules: '+str(missing))
    expected={str(module_path(n.split('::')[0]).relative_to(REPO))+'::'+n.split('::',1)[1] for n in historical}
    for name in ('logs','xml','temp'): (OUT/name).mkdir()
    config={'schema':'disastertrace.v13.affected_regression.v1',
            'modules':[str(p) for p in sorted(modules)],'historical_expected_nodes':sorted(expected),
            'source_hashes':{str(p):sha(p) for p in (OUT/'source').rglob('*.py')},
            'test_hashes':{str(p):sha(p) for p in sorted(modules)},
            'workers':8,'per_module_timeout_seconds':900,
            'rationale':'Union of recorded v11/v12 affected monitoring and165 supplemental tests plus new v13 tests; no raw acquisition or model API',
            'python':str(STARTER/'.venv/bin/python'), 'prepared_at':dt.datetime.now(dt.timezone.utc).isoformat()}
    write(OUT/'REGISTRATION.json',config)
    print(json.dumps({'modules':len(modules),'historical_nodes':len(expected),'source_files':len(config['source_hashes'])}))


def execute():
    config=read(OUT/'REGISTRATION.json')
    for name,h in (config['source_hashes']|config['test_hashes']).items():
        if sha(Path(name))!=h:raise ValueError('Regression source changed before launch: '+name)
    write(OUT/'CLAIM.json',{'started_at':dt.datetime.now(dt.timezone.utc).isoformat(),'hostname':socket.gethostname(),
        'registration_sha256':sha(OUT/'REGISTRATION.json'),'script_sha256':sha(Path(__file__)),
        'cpu_quota':Path('/sys/fs/cgroup/cpu.max').read_text().strip() if Path('/sys/fs/cgroup/cpu.max').exists() else None})
    env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':str(OUT/'source')+':'+str(STARTER/'tests'),
         'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'}
    def one(item):
        i,name=item; log=OUT/'logs'/f'{i:03d}.log';xml=OUT/'xml'/f'{i:03d}.xml'
        args=[config['python'],'-m','pytest',name,'-q','--junitxml='+str(xml),'--basetemp='+str(OUT/'temp'/f'{i:03d}')]
        started=time.monotonic()
        with log.open('x') as f:
            try:exit_code=subprocess.run(args,cwd=STARTER,env=env,stdout=f,stderr=subprocess.STDOUT,
                                         timeout=config['per_module_timeout_seconds']).returncode
            except subprocess.TimeoutExpired:exit_code=124
        cases=[]
        if xml.exists():
            for c in ET.parse(xml).getroot().iter('testcase'):
                status='failed' if c.find('failure') is not None or c.find('error') is not None else 'skipped' if c.find('skipped') is not None else 'passed'
                cases.append({'node_id':str(Path(name).relative_to(REPO))+'::'+c.attrib['name'],'status':status})
        result={'module':name,'command':args,'exit_code':exit_code,'seconds':time.monotonic()-started,
                'log_path':str(log),'log_sha256':sha(log),'junit_path':str(xml),
                'junit_sha256':sha(xml) if xml.exists() else None,'cases':cases}
        write(OUT/'logs'/f'{i:03d}.result.json',result)
        return result
    with ThreadPoolExecutor(max_workers=config['workers']) as pool:
        results=list(pool.map(one,enumerate(config['modules'])))
    seen={r['node_id'] for result in results for r in result['cases']}
    missing=sorted(set(config['historical_expected_nodes'])-seen)
    unchanged=all(sha(Path(p))==h for p,h in (config['source_hashes']|config['test_hashes']).items())
    passed=unchanged and not missing and all(r['exit_code']==0 and r['cases'] and all(c['status']=='passed' for c in r['cases']) for r in results)
    value={'passed':passed,'modules':len(results),'unique_nodes':len(seen),'historical_missing_nodes':missing,
           'source_and_tests_unchanged':unchanged,'results':results,'finished_at':dt.datetime.now(dt.timezone.utc).isoformat()}
    write(OUT/'RESULT.json',value)
    print(json.dumps({k:v for k,v in value.items() if k!='results'}),flush=True)
    raise SystemExit(0 if passed else 1)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','execute']);args=parser.parse_args()
    prepare() if args.action=='prepare' else execute()
