"""Wait for verified weights, then make one bounded four-H100 submission."""

import hashlib
import json
import re
import shlex
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
BATCH = HERE / 'large_diagnostic_02'
OUT = BATCH / 'submission_01'
SCO = '/mnt/afs/260010168/bin/sco'
PYTHON = '/mnt/afs/260010168/.venvs/disastertrace-qwen3-v1/bin/python'


def load(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, value):
    with (OUT / name).open('x') as f:
        json.dump(value, f, indent=2)
        f.write('\n')


def main():
    OUT.mkdir(exist_ok=False)
    save('GOVERNOR_STARTED.json', {'started_at': datetime.now(timezone.utc).isoformat(),
         'latest_submission_at': '2026-09-13T23:15:00+00:00', 'maximum_new_gpu_jobs': 1,
         'maximum_concurrent_gpus': 4, 'maximum_user_inference_requests': 1010})
    while not (HERE / 'DOWNLOAD_RESULT.json').exists():
        if datetime.now(timezone.utc) >= datetime.fromisoformat('2026-09-13T23:15:00+00:00'):
            save('NOT_SUBMITTED.json', {'reason': 'weights not ready before latest bounded start'})
            return
        time.sleep(30)
    download = load(HERE / 'DOWNLOAD_RESULT.json')
    if not download['all_verified']:
        save('NOT_SUBMITTED.json', {'reason': 'weight verification failed; inspect download receipts'})
        return
    plan, cpu = load(BATCH / 'PLAN.json'), load(BATCH / 'CPU_PREFLIGHT.json')
    assert cpu['all_inputs_visible_at_dispatch']
    assert cpu['plan_sha256'] == digest(BATCH / 'PLAN.json') and cpu['tasks_per_model'] == 504
    assert load(HERE.parent / 'validation/full_dispatch_and_collector_05.exit.json')['exit_code'] == 0
    protocol = load(BATCH / 'evaluation_protocol_02/PROTOCOL.json')
    assert protocol['plan_sha256'] == digest(BATCH / 'PLAN.json')
    assert protocol['all_dispatch_inputs_and_native_time_pairs_verified']
    assert protocol['program_admission_and_journal_replay_verified']
    for rel, sha in protocol['files'].items():
        assert digest(BATCH / 'evaluation_protocol_02' / rel) == sha, rel
    assert load(HERE / 'parallel_preflight_01/VALIDATION.json')['passed']
    assert load(HERE.parent / 'reports/history_impact_01/EXECUTION_IMPACT.json')['total_existing_calls_audited'] == 360
    assert len(plan['tasks']) == 504 and plan['maximum_total_calls'] == 1010
    for rel, sha in plan['files'].items():
        assert digest(BATCH / rel) == sha, rel
    current = subprocess.run([SCO, 'acp', 'jobs', 'list', '--workspace-name=share-space',
         '--user-name=260010168', '--page-size=500', '--format=json'], capture_output=True,
         text=True, timeout=60, check=True)
    jobs = json.loads(current.stdout)
    assert len(jobs) < 500 and all(j['ownership']['user_name'] == '260010168' for j in jobs)
    active = [j for j in jobs if j['state'] not in {'SUCCEEDED', 'FAILED', 'DELETED'}]
    count = sum(int(role['total_replicas']) * int(role['resource_spec'][0]['requests']['nvidia.com/gpu'])
                for job in active for role in job['roles'])
    save('ACCOUNT_BEFORE.json', {'active_requested_gpus': count, 'active_jobs': active})
    if count:
        save('NOT_SUBMITTED.json', {'reason': 'Four-GPU account envelope was not free; no duplicate allocation'})
        return
    env = ['env', 'HF_HUB_OFFLINE=1', 'TRANSFORMERS_OFFLINE=1', 'PYTHONDONTWRITEBYTECODE=1',
           'VLLM_WORKER_MULTIPROC_METHOD=spawn', 'OMP_NUM_THREADS=4',
           'PYTHONPATH=' + str(BATCH / 'source')]
    lines = ['#!/usr/bin/env bash', 'set -uo pipefail', 'overall_rc=0']
    for key in plan['model_order']:
        command = env + [PYTHON, str(BATCH / 'source/large_worker.py'), '--batch', str(BATCH), '--model', key]
        lines += [shlex.join(command) + ' > ' + shlex.quote(str(BATCH / (key + '.log'))) + ' 2>&1',
                  'model_rc=$?',
                  'printf \'%s\\n\' "$model_rc" > ' + shlex.quote(str(BATCH / (key + '.exit.txt'))),
                  'if [ "$model_rc" -ne 0 ]; then overall_rc=1; fi']
    lines += ['exit "$overall_rc"']
    runner = OUT / 'run_models.sh'
    runner.write_text('\n'.join(lines) + '\n')
    outer = OUT / 'run.sh'
    outer.write_text('#!/usr/bin/env bash\nset -euo pipefail\n' + shlex.join(
        ['timeout', '--signal=TERM', '--kill-after=60', '12000s', 'bash', str(runner)]) + '\n')
    name = 'dtv8-qwen235b-4h100-' + datetime.now(timezone.utc).strftime('%Y%m%dt%H%M%Sz')
    command = [SCO, 'acp', 'jobs', 'create', '--workspace-name=share-space',
        '--aec2-name=computing-cluster-01g-02', '--job-name=' + name,
        '--container-image-url=registry.cn-sh-01g.sensecore.cn/lepton-trainingjob/nvidia24.04-ubuntu22.04-py3.10-cuda12.4-cudnn9.1-torch2.3.0-transformerengine1.5:v1.0.0-20241130-nvdia-base-image',
        '--training-framework=pytorch', '--worker-nodes=1', '--worker-spec=N6lS.Iu.I10.4.56c792g',
        '--storage-mount=01a04263-91e5-7603-bc01-c67e503da6b5:/mnt/afs', '--quota-type=reserved',
        '--priority=NORMAL', '--retry-times=0', '--command=bash ' + shlex.quote(str(outer))]
    save('SUBMISSION_INTENT.json', {'name': name, 'command': command, 'plan_sha256': digest(BATCH / 'PLAN.json'),
                                  'expected_gpus': 4, 'benchmark_requests': 1008, 'compatibility_requests': 2})
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=90)
    except subprocess.TimeoutExpired:
        save('SUBMISSION_UNKNOWN.json', {'name': name, 'reason': 'CLI timeout; inspect this exact job name before any further submission'})
        raise
    save('SUBMISSION_RESPONSE.json', {'exit_code': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr})
    match = re.search(r'job (pt-[a-z0-9]+) submitted successfully', result.stdout)
    assert result.returncode == 0 and match
    (OUT / 'job-id.txt').write_text(match.group(1) + '\n')
    print(json.dumps({'job_id': match.group(1), 'status': 'submitted', 'expected_gpus': 4}), flush=True)


if __name__ == '__main__':
    main()
