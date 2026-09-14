"""Submit exactly one four-GPU preflight under the existing user authorization."""

import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
RUN = HERE / 'parallel_preflight_01'
SCO = '/mnt/afs/260010168/bin/sco'
PYTHON = '/mnt/afs/260010168/.venvs/disastertrace-qwen3-v1/bin/python'


def save(name, row):
    with (RUN/name).open('x') as stream:
        json.dump(row, stream, indent=2); stream.write('\n')


def main():
    if (RUN/'SUBMISSION_INTENT.json').exists():
        raise ValueError('Submission intent is already consumed; inspect existing status')
    query = subprocess.run([SCO, 'acp', 'jobs', 'list', '--workspace-name=share-space',
                            '--user-name=260010168', '--page-size=500', '--format=json'],
                           capture_output=True, text=True, timeout=60, check=True)
    jobs = json.loads(query.stdout)
    if len(jobs) >= 500 or any(j['ownership']['user_name'] != '260010168' for j in jobs):
        raise ValueError('Ambiguous account scope')
    active = [j for j in jobs if j['state'] not in {'SUCCEEDED','FAILED','DELETED'}]
    count = sum(int(role['total_replicas']) * int(role['resource_spec'][0]['requests']['nvidia.com/gpu'])
                for job in active for role in job['roles'])
    save('ACCOUNT_BEFORE.json', {'active_requested_gpus': count, 'active_jobs': active})
    if count:
        raise ValueError('Four-GPU account envelope is not free')
    name = 'dtv8-4h100-preflight-' + datetime.now(timezone.utc).strftime('%Y%m%dt%H%M%Sz')
    command = ['timeout','--signal=TERM','--kill-after=30','600s','env','HF_HUB_OFFLINE=1',
               'TRANSFORMERS_OFFLINE=1','PYTHONDONTWRITEBYTECODE=1','OMP_NUM_THREADS=4',
               PYTHON,'-m','torch.distributed.run','--standalone','--nproc_per_node=4',str(RUN/'preflight.py')]
    runner = RUN/'run.sh'
    runner.write_text('#!/usr/bin/env bash\nset -euo pipefail\n' + shlex.join(command) +
                      ' > ' + shlex.quote(str(RUN/'worker.log')) + ' 2>&1\n')
    args = [SCO,'acp','jobs','create','--workspace-name=share-space','--aec2-name=computing-cluster-01g-02',
            '--job-name='+name,
            '--container-image-url=registry.cn-sh-01g.sensecore.cn/lepton-trainingjob/nvidia24.04-ubuntu22.04-py3.10-cuda12.4-cudnn9.1-torch2.3.0-transformerengine1.5:v1.0.0-20241130-nvdia-base-image',
            '--training-framework=pytorch','--worker-nodes=1','--worker-spec=N6lS.Iu.I10.4.56c792g',
            '--storage-mount=01a04263-91e5-7603-bc01-c67e503da6b5:/mnt/afs','--quota-type=reserved',
            '--priority=NORMAL','--retry-times=0','--command=bash '+shlex.quote(str(runner))]
    save('SUBMISSION_INTENT.json', {'name':name,'args':args,'expected_gpus':4,'model_calls':0,
                                    'script_sha256':hashlib.sha256((RUN/'preflight.py').read_bytes()).hexdigest()})
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=90)
    except subprocess.TimeoutExpired:
        save('SUBMISSION_UNKNOWN.json', {'name':name,'reason':'CLI timed out; query this name before any subsequent submission'})
        raise
    save('SUBMISSION_RESPONSE.json', {'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
    match = re.search(r'job (pt-[a-z0-9]+) submitted successfully',result.stdout)
    if result.returncode or not match:
        raise ValueError('Inspect saved submission response')
    (RUN/'job-id.txt').write_text(match.group(1)+'\n')
    print(json.dumps({'job_id':match.group(1),'run':str(RUN),'expected_gpus':4,'status':'submitted_not_yet_verified'}))


if __name__ == '__main__':
    main()
