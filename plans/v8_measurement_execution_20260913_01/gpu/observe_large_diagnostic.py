"""Observe one already-authorized launch, then run its frozen independent scorer."""

import datetime
import json
import os
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BATCH = HERE / 'large_diagnostic_02'
SUBMISSION = BATCH / 'submission_01'
OUT = BATCH / 'observer_01'
SCO = '/mnt/afs/260010168/bin/sco'
PYTHON = '/mnt/afs/260010168/.venvs/disastertrace-qwen3-v1/bin/python'


def save(path, value):
    with path.open('x') as handle:
        json.dump(value, handle, indent=2)
        handle.write('\n')


def main():
    OUT.mkdir(exist_ok=False)
    save(OUT / 'STARTED.json', {'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                              'submits_jobs': False, 'retries_model_calls': False})
    deadline = datetime.datetime.fromisoformat('2026-09-14T02:40:00+00:00')
    job_id = None
    count = 0
    while datetime.datetime.now(datetime.timezone.utc) < deadline:
        if (SUBMISSION / 'NOT_SUBMITTED.json').exists():
            save(OUT / 'NOT_RUN.json', json.loads((SUBMISSION / 'NOT_SUBMITTED.json').read_text()))
            return
        if job_id is None:
            if (SUBMISSION / 'job-id.txt').exists():
                job_id = (SUBMISSION / 'job-id.txt').read_text().strip()
            else:
                time.sleep(30)
                continue
        result = subprocess.run([SCO, 'acp', 'jobs', 'describe', '--workspace-name=share-space',
                                 job_id, '--format=json'], capture_output=True, text=True, timeout=45)
        count += 1
        if result.returncode == 0:
            job = json.loads(result.stdout)
            require = job['name'] == job_id and job['ownership']['user_name'] == '260010168'
            if not require:
                raise ValueError('Observed job identity mismatch')
            if job['state'] in {'SUCCEEDED', 'FAILED', 'DELETED'}:
                save(SUBMISSION / 'FINAL_JOB.json', job)
                break
        else:
            save(OUT / ('query_error_' + str(count) + '.json'), {'exit_code': result.returncode,
                 'stderr': result.stderr, 'at': datetime.datetime.now(datetime.timezone.utc).isoformat()})
        time.sleep(30)
    else:
        save(OUT / 'TIME_LIMIT.json', {'job_id': job_id, 'reason': 'Observer reached autonomy boundary; inspect job before final handoff'})
        return
    prepared = BATCH / 'evaluation_protocol_02'
    output = HERE.parent / 'reports/large_model_diagnostic_01'
    command = [PYTHON, str(prepared / 'verify_large_diagnostic.py'), 'score', '--batch', str(BATCH),
               '--prepared', str(prepared), '--out', str(output)]
    save(OUT / 'SCORE_COMMAND.json', {'command': command, 'job_id': job_id})
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(BATCH / 'source'),
               OMP_NUM_THREADS='2', MKL_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2', TOKENIZERS_PARALLELISM='false',
               HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    with (OUT / 'score.log').open('x') as handle:
        result = subprocess.run(command, env=env, stdout=handle, stderr=subprocess.STDOUT)
    save(OUT / 'COMPLETE.json', {'job_id': job_id, 'job_state': job['state'], 'scorer_exit_code': result.returncode,
         'output': str(output), 'completed_at': datetime.datetime.now(datetime.timezone.utc).isoformat()})
    print(json.dumps({'job_id': job_id, 'scorer_exit_code': result.returncode, 'output': str(output)}), flush=True)


if __name__ == '__main__':
    main()
