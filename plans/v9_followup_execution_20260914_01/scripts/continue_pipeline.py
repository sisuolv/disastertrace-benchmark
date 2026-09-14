"""Run qualified stages after native downloads; persist state at stage boundaries."""

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[1]


def load(p):
    return json.loads(p.read_text())


def status(phase, **details):
    row={'at':dt.datetime.now(dt.timezone.utc).isoformat(),'phase':phase,**details}
    with (ROOT/'runtime/PIPELINE_EVENTS.jsonl').open('a') as f:
        f.write(json.dumps(row)+'\n');f.flush();os.fsync(f.fileno())
    destination=ROOT/'runtime/PIPELINE_STATUS.json'
    temporary=destination.with_suffix('.tmp')
    temporary.write_text(json.dumps(row,indent=2)+'\n');temporary.replace(destination)
    print(json.dumps(row),flush=True)


def run(name,script,*args):
    status(name+'_RUNNING')
    command=[sys.executable,str(ROOT/'scripts'/script),*args]
    with (ROOT/'runtime'/(name+'.command.json')).open('x') as f:
        json.dump(command,f,indent=2)
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(REPO/'disastertrace-starter/src'))
    with (ROOT/'runtime'/(name+'.log')).open('x') as log:
        result=subprocess.run(command,cwd=REPO,env=env,stdout=log,stderr=subprocess.STDOUT)
    with (ROOT/'runtime'/(name+'.exit.json')).open('x') as f:
        json.dump({'exit_code':result.returncode},f)
    if result.returncode:
        raise RuntimeError(name+' failed; logs and original attempts retained')
    status(name+'_COMPLETE')


def main():
    with (ROOT/'runtime/PIPELINE_CLAIM.json').open('x') as f:
        json.dump({'started_at':dt.datetime.now(dt.timezone.utc).isoformat()},f)
    try:
        status('WAITING_FOR_DOWNLOADS_AND_RELEASE')
        deadline=time.monotonic()+6*3600
        complete=ROOT/'regional_training_02/COMPLETE.json'
        release=ROOT/'runtime/PIPELINE_RELEASE.json'
        while not (complete.exists() and release.exists()):
            if time.monotonic()>deadline:
                raise RuntimeError('Pre-stage six-hour waiting limit reached')
            time.sleep(30)
        if not load(complete)['all_complete']:
            raise RuntimeError('One or more native training acquisitions failed')
        gate=load(release)
        for path,sha in gate['files'].items():
            assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==sha, 'Released implementation changed'
        run('N2_full_manifest','build_process_manifest.py','--include-training')
        run('N3_regional_baselines','fit_regional_baselines.py')
        run('N3_api_evidence','run_api_evidence.py')
        run('N4_api_pilot','run_api_pilot.py')
        status('REGISTERED_PIPELINE_COMPLETE',limitations='Development only; confirmation and 16-hazard admission remain closed')
    except Exception as exc:
        status('STOPPED_AT_GATE',error_type=type(exc).__name__,reason=str(exc))
        raise


if __name__=='__main__':
    main()
