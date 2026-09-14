"""Run one named validation, preserving command, log, exit and JUnit evidence."""

import argparse
import datetime
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1] / 'validation'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('name')
    parser.add_argument('tests', nargs='+')
    args = parser.parse_args()
    command = [str(ROOT / 'disastertrace-starter/.venv/bin/python'), '-m', 'pytest',
               *args.tests, '-q', '--disable-warnings', '--junitxml=' + str(OUT / (args.name + '.xml'))]
    now = lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    with (OUT / (args.name + '.command.json')).open('x') as handle:
        json.dump({'command': command, 'cwd': str(ROOT), 'started_at': now()}, handle, indent=2)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', DISASTERTRACE_AUDIT_MODE='repo')
    env['PYTHONPATH'] = str(ROOT / 'disastertrace-starter/src')
    with (OUT / (args.name + '.log')).open('x') as handle:
        result = subprocess.run(command, cwd=ROOT, env=env, stdout=handle, stderr=subprocess.STDOUT)
    (OUT / (args.name + '.exit.json')).write_text(json.dumps(
        {'exit_code': result.returncode, 'finished_at': now()}, indent=2) + '\n')
    print((OUT / (args.name + '.log')).read_text()[-4000:])
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
