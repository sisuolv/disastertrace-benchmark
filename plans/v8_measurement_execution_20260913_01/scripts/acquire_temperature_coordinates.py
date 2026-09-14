"""Complete registered native coordinates for the already-downloaded EUPP arrays."""

import concurrent.futures
import datetime
import hashlib
import json
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
PRIOR = REPO / 'plans/v7_execution_20260913/sources_numerical'
OUT = HERE / 'temperature_extension_01'
BASE = 'https://object-store.os-api.cci1.ecmwf.int/eumetnet-postprocessing-benchmark-1st-phase-training-dataset/data/stations_data/'
PREFIXES = {'eupp_ensemble_forecasts_surface': 'stations_ensemble_forecasts_surface_germany.zarr',
            'eupp_forecasts_observations_surface': 'stations_forecasts_observations_surface_germany.zarr'}


def save(path, value):
    with path.open('x') as handle:
        json.dump(value, handle, indent=2)
        handle.write('\n')


def fetch(row):
    receipt = {**row, 'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    path = OUT / 'coordinates' / row['relative']
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        req = urllib.request.Request(row['url'], headers={'User-Agent': 'DisasterTrace-coordinate-verification/1.0'})
        with urllib.request.urlopen(req, timeout=25) as response:
            payload = response.read(262145)
            if len(payload) > 262144:
                raise ValueError('Coordinate object exceeds preregistered cap')
            length = response.headers.get('Content-Length')
            if response.status != 200 or (length is not None and int(length) != len(payload)):
                raise ValueError('Incomplete coordinate object')
            sha = hashlib.sha256(payload).hexdigest()
            etag = response.headers.get('ETag', '').strip('"')
            if len(etag) == 32 and hashlib.md5(payload).hexdigest() != etag:
                raise ValueError('Single-part ETag differs from coordinate bytes')
            with path.open('xb') as handle:
                handle.write(payload)
            receipt.update(status='verified', http_status=response.status, bytes=len(payload),
                           sha256=sha, etag=etag, last_modified=response.headers.get('Last-Modified'))
    except Exception as exc:
        receipt.update(status='failed', error_type=type(exc).__name__, error=str(exc))
    receipt['finished_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return receipt


def main():
    OUT.mkdir(exist_ok=False)
    old = [json.loads(line) for line in (PRIOR / 'REQUESTS.jsonl').read_text().splitlines()]
    receipts = {r.get('name'): r for r in old if r.get('status') == 200 and 'error' not in r}
    requests, reused = [], []
    for prefix, source in PREFIXES.items():
        meta = json.loads((PRIOR / 'raw' / (prefix + '_metadata.json')).read_text())['metadata']
        assert meta['time/.zarray']['shape'] == [730] and meta['time/.zarray']['chunks'] == [1]
        variables = ('time', 'valid_time') if prefix == 'eupp_ensemble_forecasts_surface' else ('time',)
        for variable in variables:
            for index in range(730):
                key = str(index) + ('.0' if variable == 'valid_time' else '')
                relative = prefix + '/' + variable + '/' + key
                path = PRIOR / 'raw' / relative
                if path.exists():
                    receipt = receipts[relative]
                    assert hashlib.sha256(path.read_bytes()).hexdigest() == receipt['sha256']
                    reused.append({'relative': relative, 'path': str(path.resolve()), 'sha256': receipt['sha256'],
                                   'original_receipt': receipt})
                else:
                    requests.append({'relative': relative, 'url': BASE + source + '/' + variable + '/' + key})
    save(OUT / 'CALENDAR.json', {'frozen_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
         'selection': 'All 730 published initialization indices, all 21 leads and 51 members of station index 0, DWD460 Berus.',
         'expected_positive_lead_opportunities': 14600, 'zero_lead_retained_as_nonscored_initial_state': 730,
         'source_array': 'Existing complete 51 x 730 x 21 forecast and 730 x 21 observation chunks.',
         'additional_download': 'Only native time and valid_time coordinate chunks, before interpreting the full outcome array.',
         'future_semantics': 'instant 2m temperature, init + 3h availability scenario, init + 4h cutoff; no daily-extreme substitution',
         'full_natural_calendar': True, 'independent_confirmation': False, 'model_calls': 0,
         'max_workers': 4, 'max_attempts_per_new_coordinate': 1, 'object_cap_bytes': 262144,
         'date_source': 'Actual coordinates determine dates; no manufactured regular daily times.',
         'quality': 'All raw observations retained; DWD hourly source, native quality codes and unit match checked separately.',
         'physical_extreme_event_qualified': False, 'requests': requests, 'reused': reused})
    result = []
    with (OUT / 'COORDINATE_RECEIPTS.jsonl').open('x') as handle:
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            for receipt in pool.map(fetch, requests):
                result.append(receipt)
                handle.write(json.dumps(receipt) + '\n')
                handle.flush()
                if len(result) % 100 == 0:
                    print(json.dumps({'completed': len(result), 'expected': len(requests),
                                      'failures': sum(r['status'] != 'verified' for r in result)}), flush=True)
    save(OUT / 'ACQUISITION.json', {'new_requests': len(result), 'reused_coordinates': len(reused),
         'all_verified': all(r['status'] == 'verified' for r in result),
         'failures': [r for r in result if r['status'] != 'verified'],
         'new_bytes': sum(r.get('bytes', 0) for r in result), 'model_calls': 0})
    print(json.dumps({k: v for k, v in json.loads((OUT / 'ACQUISITION.json').read_text()).items() if k != 'failures'}))


if __name__ == '__main__':
    main()
