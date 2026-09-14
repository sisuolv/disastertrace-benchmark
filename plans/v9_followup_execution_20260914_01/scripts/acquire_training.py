"""Preregister independent regional fitting/calibration data and download once."""

import concurrent.futures
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import shutil
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
V8 = REPO / 'plans/v8_measurement_execution_20260913_01'
OUT = ROOT / 'regional_training_02'
REGIONS = {'bay': ['KSFO', 'KOAK', 'KSJC'], 'new_york': ['KJFK', 'KLGA', 'KEWR'],
           'chicago': ['KORD', 'KMDW', 'KRFD'], 'denver': ['KDEN', 'KBJC', 'KAPA']}


def load(p):
    return json.loads(p.read_text())


def save(p, d):
    with p.open('x') as f:
        json.dump(d, f, indent=2, allow_nan=False)
        f.write('\n')


def helper():
    spec = importlib.util.spec_from_file_location('fresh_training_io', OUT / 'source/acquisition_helpers.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.OUT, mod.REPO = OUT, REPO
    mod.PYTHON = str(REPO / 'disastertrace-starter/.venv/bin/python')
    return mod


def acquire_region(name):
    folder, io = OUT / name, helper()
    try:
        catalogs = io.acquire(folder, folder / 'SOURCE_CATALOG_PLAN.json', 'catalogs')
        plan = folder / 'SOURCE_NATIVE_PLAN.json'
        io.run(folder, 'prepare_native', [io.PYTHON, str(OUT / 'source/prepare_native_fetch.py'),
                                        '--catalogs', str(catalogs), '--output', str(plan)])
        count = len(load(plan)['requests'])
        assert count <= 1800, 'Registered per-region source ceiling exceeded'
        native = io.acquire(folder, plan, 'native')
        stage = folder / 'dataset_stage_v1'
        io.run(folder, 'decode', [io.PYTHON, str(OUT / 'source/build_regional_stage_v1.py'),
            '--contract', str(folder / 'CALENDAR.json'), '--metar', str(catalogs), '--taf', str(native),
            '--source-root', str(folder), '--output', str(stage)])
        io.run(folder, 'version_contract', [io.PYTHON, str(OUT / 'source/build_native_v2.py'),
            '--dataset', str(stage), '--source-root', str(folder), '--output', str(folder / 'dataset_v2')])
        row = {'region': name, 'complete': True, 'native_requests': count,
               'completed_at': dt.datetime.now(dt.timezone.utc).isoformat()}
    except Exception as exc:
        row = {'region': name, 'complete': False, 'error_type': type(exc).__name__, 'error': str(exc)}
    save(folder / 'RESULT.json', row)
    with (OUT / 'EVENTS.jsonl').open('a') as f:
        f.write(json.dumps(row) + '\n')
    return row


def main():
    OUT.mkdir(exist_ok=False)
    source = OUT / 'source'
    source.mkdir()
    prior = REPO / 'plans/v7_adaptive_execution_20260913'
    template = load(prior / 'DEVELOPMENT_CALENDAR.json')
    original = load(prior / 'SOURCE_CATALOG_PLAN.json')
    for name, stations in REGIONS.items():
        folder = OUT / name
        folder.mkdir()
        calendar = {**template, 'stations': stations, 'lead_hours': [1],
            'cutoff_start': '2024-12-01T00:00:00Z', 'cutoff_end_exclusive': '2025-01-01T00:00:00Z',
            'opportunities_per_threshold': 2232, 'stage': 'regional_fit_calibration_only',
            'preregistered_at': dt.datetime.now(dt.timezone.utc).isoformat(),
            'date_selection': 'Previous complete December before existing Jan/Feb 2025 evaluation; no outcome filter',
            'image_admission': 'none', 'baseline_mapping': 'Fitting not performed until role purge is validated'}
        save(folder / 'CALENDAR.json', calendar)
        requests = []
        for station in stations:
            for old in original['requests'][:2]:
                url = urlsplit(old['url'])
                params = dict(parse_qsl(url.query))
                metar = old['id'].startswith('metar')
                params.update(station=station[1:] if metar else station, year1='2024', month1='11', day1='29',
                              year2='2025', month2='1', day2='2')
                requests.append({**old, 'id': ('metar-routine-' if metar else 'taf-catalog-') + station,
                                 'url': urlunsplit((url.scheme, url.netloc, url.path, urlencode(params), '')),
                                 'max_bytes': 8_000_000, 'timeout': 120})
        save(folder / 'SOURCE_CATALOG_PLAN.json', {**original, 'requests': requests,
             'registered_at': calendar['preregistered_at'], 'calendar_sha256': None,
             'limits': {'requests': 6, 'bytes': 48_000_006}, 'pause_seconds': 2})
    sources = {'acquisition_helpers.py': V8 / 'scripts/extend_regional_calendars.py',
        'fetch_public.py': REPO / 'plans/v7_review_execution_20260912/fetch_public.py',
        'prepare_native_fetch.py': REPO / 'plans/v7_review_execution_20260912/prepare_native_fetch.py',
        'build_regional_stage_v1.py': prior / 'build_regional.py',
        'build_native_v2.py': V8 / 'scripts/build_native_v2.py', 'acquire_training.py': Path(__file__)}
    for name, path in sources.items():
        shutil.copyfile(path, source / name)
    for module in ['monitoring_v1', 'monitoring_fixed_v1']:
        shutil.copytree(REPO / 'disastertrace-starter/src/disastertrace' / module,
                        source / 'disastertrace' / module, ignore=shutil.ignore_patterns('__pycache__'))
    (source / 'disastertrace/__init__.py').write_text('"""Frozen independent training acquisition."""\n')
    save(OUT / 'PREREGISTRATION.json', {'regions': REGIONS, 'cutoff_period': ['2024-12-01', '2025-01-01'],
        'fit_interval': ['2024-12-01', '2024-12-19'], 'calibration_interval': ['2024-12-23', '2024-12-29'],
        'role_admission': 'entire native input and future reference footprint inside role interval',
        'cross_role_shared_native_versions': 'forbidden', 'lead_hours': [1], 'model_calls': 0,
        'max_native_requests_per_region': 1800, 'exact_download_retries': 1,
        'confirmation_opened': False, 'simultaneous_regional_fetchers': 4,
        'historical_availability': 'declared archive delays, not first-seen proof'})
    # Use public direct connections; inherited broken proxy settings are not credentials.
    for key in ['http_proxy', 'https_proxy', 'all_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY']:
        os.environ.pop(key, None)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(acquire_region, REGIONS))
    save(OUT / 'COMPLETE.json', {'regions': rows, 'all_complete': all(r['complete'] for r in rows)})
    print(json.dumps(rows), flush=True)


if __name__ == '__main__':
    main()
