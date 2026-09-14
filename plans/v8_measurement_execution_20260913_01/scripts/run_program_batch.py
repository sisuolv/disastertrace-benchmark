"""Bounded two-process CPU orchestration; each experiment has a fresh claim."""

import concurrent.futures
import datetime
import json
import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
PYTHON = REPO / 'disastertrace-starter/.venv/bin/python'
BASE = HERE / 'reports/program_calendar_02'


def command(command, out, stem, env):
    with (out / (stem + '.command.json')).open('x') as f:
        json.dump({'command': command, 'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}, f, indent=2)
    with (out / (stem + '.log')).open('x') as f:
        result = subprocess.run(command, cwd=REPO, env=env, stdout=f, stderr=subprocess.STDOUT)
    (out / (stem + '.exit.json')).write_text(json.dumps({'exit_code': result.returncode}) + '\n')
    return result.returncode


def execute(case, arm):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(case / 'source'),
               DISASTERTRACE_V8_EXECUTION_ROOT=str(HERE))
    code = command([str(PYTHON), str(case / 'source/run_program_calendar.py'), 'run', '--out', str(case), '--arm', arm], case, arm + '-run', env)
    print(json.dumps({'case': case.name, 'arm': arm, 'exit_code': code}), flush=True)
    return case, arm, code


def main():
    BASE.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    cases = []
    for threshold in (1000, 5000):
        for protocol in ('base_bound_override', 'persistent_override'):
            case = BASE / (str(threshold) + '__' + protocol)
            cmd = [str(PYTHON), str(HERE / 'scripts/run_program_calendar.py'), 'freeze', '--out', str(case),
                   '--threshold', str(threshold), '--protocol', protocol]
            rc = command(cmd, BASE, 'freeze-' + case.name, env)
            if rc:
                raise SystemExit('Freeze failed; retain the failed directory: ' + str(case))
            cases.append(case)
    pending = [(case, arm) for case in cases for arm in json.loads((case / 'CONFIGS.json').read_text())]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda pair: execute(*pair), pending))
    if any(rc for _, _, rc in results):
        raise SystemExit('Some program arms failed; do not silently retry')
    for case in cases:
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(case / 'source'),
                   DISASTERTRACE_V8_EXECUTION_ROOT=str(HERE))
        rc = command([str(PYTHON), str(case / 'source/run_program_calendar.py'), 'score', '--out', str(case)], case, 'score', env)
        if rc:
            raise SystemExit('Comparison failed: ' + str(case))
    (BASE / 'BATCH_COMPLETE.json').write_text(json.dumps({'cases': [str(p) for p in cases],
         'program_arm_runs': len(results), 'new_model_calls': 0, 'all_passed': True,
         'completed_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}, indent=2) + '\n')


if __name__ == '__main__':
    main()
