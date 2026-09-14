"""Freeze a consecutive development calendar, then acquire complete native sources."""

import datetime
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
OUT = HERE / 'calendar_extension_01'


def write(path, data):
    with path.open('x') as handle:
        json.dump(data, handle, indent=2)
        handle.write('\n')


def run(name, command):
    write(OUT / (name + '.command.json'), command)
    with (OUT / (name + '.log')).open('x') as handle:
        result = subprocess.run(command, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'),
                                stdout=handle, stderr=subprocess.STDOUT, cwd=REPO)
    write(OUT / (name + '.exit.json'), {'exit_code': result.returncode})
    if result.returncode:
        raise SystemExit('Retain failed stage: ' + name)


def main():
    OUT.mkdir(exist_ok=False)
    (OUT / 'source').mkdir()
    prior = REPO / 'plans/v7_adaptive_execution_20260913'
    original = json.loads((prior / 'DEVELOPMENT_CALENDAR.json').read_text())
    original.update(preregistered_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    stage='consecutive_development_extension_not_confirmation',
                    cutoff_start='2025-02-04T00:00:00Z', cutoff_end_exclusive='2025-02-11T00:00:00Z',
                    opportunities_per_threshold=1512, image_admission='none in this native-text work package',
                    baseline_fit='unchanged 2023-12-02 through 2023-12-14 Bay bank; disclosed temporal transfer',
                    native_baseline_rule='latest_before_coverage.v2 in final derived dataset',
                    selection='all days, hours, sites, leads and thresholds; no positive-event or model-gain filtering',
                    reserved_confirmation={'cutoff_start':'2025-02-17T00:00:00Z',
                                           'cutoff_end_exclusive':'2025-02-24T00:00:00Z',
                                           'status':'reserved only; no new retrieval or evaluation in this script'})
    write(OUT / 'CALENDAR.json', original)
    plan = json.loads((prior / 'SOURCE_CATALOG_PLAN.json').read_text())
    plan['registered_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    plan['calendar_sha256'] = hashlib.sha256((OUT / 'CALENDAR.json').read_bytes()).hexdigest()
    for request in plan['requests']:
        parsed = urlsplit(request['url']); query = dict(parse_qsl(parsed.query))
        query.update(year1='2025', month1='2', day1='2', year2='2025', month2='2', day2='12')
        request['url'] = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), ''))
    write(OUT / 'SOURCE_CATALOG_PLAN.json', plan)
    old = REPO / 'plans/v7_review_execution_20260912'
    for filename in ('fetch_public.py', 'prepare_native_fetch.py'):
        shutil.copyfile(old / filename, OUT / 'source' / filename)
    shutil.copyfile(prior / 'build_regional.py', OUT / 'source/build_regional_stage_v1.py')
    shutil.copyfile(HERE / 'scripts/build_native_v2.py', OUT / 'source/build_native_v2.py')
    python = str(REPO / 'disastertrace-starter/.venv/bin/python')
    run('01_catalog', [python, str(OUT / 'source/fetch_public.py'), str(OUT / 'SOURCE_CATALOG_PLAN.json'), str(OUT / 'catalogs')])
    run('02_native_plan', [python, str(OUT / 'source/prepare_native_fetch.py'), '--catalogs', str(OUT / 'catalogs'), '--output', str(OUT / 'SOURCE_NATIVE_PLAN.json')])
    run('03_native', [python, str(OUT / 'source/fetch_public.py'), str(OUT / 'SOURCE_NATIVE_PLAN.json'), str(OUT / 'native')])
    run('04_stage', [python, str(OUT / 'source/build_regional_stage_v1.py'), '--contract', str(OUT / 'CALENDAR.json'),
        '--metar', str(OUT / 'catalogs'), '--taf', str(OUT / 'native'), '--source-root', str(OUT), '--output', str(OUT / 'dataset_stage_v1')])
    run('05_derive', [python, str(OUT / 'source/build_native_v2.py'), '--dataset', str(OUT / 'dataset_stage_v1'),
        '--source-root', str(OUT), '--output', str(OUT / 'dataset_v2')])
    write(OUT / 'COMPLETE.json', {'finished_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'schema': 'disastertrace.consecutive_calendar_acquisition.v1', 'new_model_calls': 0,
          'confirmation_opened': False, 'new_opportunities': 3024,
          'report': json.loads((OUT / 'dataset_stage_v1/REGIONAL_JOIN_AUDIT.json').read_text())})
    print('Consecutive seven-day native calendar acquired and derived', flush=True)


if __name__ == '__main__':
    main()
