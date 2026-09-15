"""Derive version-corrected native baselines from verified original captures."""

import argparse
import hashlib
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from disastertrace.monitoring_v1.providers.aviation import parse_taf
from disastertrace.monitoring_v1.providers.taf_timeline import unavailable_product
from disastertrace.monitoring_v1.providers.versions import current_taf, taf_semantics
from disastertrace.monitoring_v1.targets import canonical_hash

REPO = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parents[1]
LAG = 120_000_000


def load(path):
    return json.loads(path.read_text())


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.write('\n')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(dataset, source_root, output):
    sources = load(dataset / 'SOURCES.json')
    expected_plan = source_root / 'SOURCE_NATIVE_PLAN.json'
    if expected_plan.exists():
        expected = {r['id'] for r in load(expected_plan)['requests']}
        missing = sorted(expected - set(sources))
        if missing:
            raise ValueError('Native catalog acquisitions missing from the source-bound dataset: ' + ', '.join(missing))
    verified, products, parsed, failures = {}, [], {}, []
    for sid, binding in sources.items():
        path = source_root / binding['path']
        receipt_path = source_root / binding['receipt_path']
        receipt = load(receipt_path)
        assert digest(path) == binding['sha256'] == receipt['sha256']
        assert digest(receipt_path) == binding['receipt_sha256']
        assert path.stat().st_size == binding['bytes'] == receipt['bytes']
        assert receipt['http_status'] == 200 and receipt['complete'] and receipt['curl_exit'] == 0
        verified[sid] = dict(binding, path=str(path.resolve()), receipt_path=str(receipt_path.resolve()))
        if not sid.startswith('taf-'):
            continue
        meta = receipt['catalog_metadata']
        issue = meta['issued_at'].replace(' ', 'T') + ':00Z'
        raw = path.read_text()
        try:
            product = parse_taf(raw, station=meta['station'], archive_issue=issue)
            parsed[sid] = product
            products.append({'source_id': sid, 'station': product.station, 'issued_at': product.issued_at,
                             'valid_start': product.valid_start, 'valid_end': product.valid_end,
                             'status': product.status, 'amendment_kind': product.amendment_kind,
                             'clause_operators': [c.operator for c in product.clauses],
                             'native_semantics_sha256': taf_semantics(product)})
        except ValueError as exc:
            envelope = unavailable_product(raw, station=meta['station'], archive_issue=issue,
                                           source_id=sid, reason=str(exc))
            envelope['native_semantics_sha256'] = canonical_hash({'unparsed_raw': envelope['raw']})
            products.append(envelope)
            failures.append({'source_id': sid, 'status': 'unparsed', 'reason': str(exc)})
    targets = {t['target_id']: t for t in load(dataset / 'public/TARGETS.json')}
    opportunities = load(dataset / 'public/OPPORTUNITIES.json')
    candidates, latest, decisions, by_pair = [], [], [], {}
    for opportunity in opportunities:
        target = targets[opportunity['target_id']]
        start, end = target['physical_start'], target['physical_end']
        for row in products:
            if row['station'] != target['entity'] or row['issued_at'] + LAG > opportunity['cutoff']:
                continue
            sid = row['source_id']
            if sid not in parsed:
                projection = {'status': 'unparsed', 'reason': row['reason'],
                              'native_valid_start': row['valid_start'], 'native_valid_end': row['valid_end']}
                unavailable = {'projection_status': 'unavailable'}
                if not row['valid_start'] <= start < end <= row['valid_end']:
                    continue
                raw = row['raw']
            else:
                try:
                    projection = parsed[sid].project(start, end)
                except ValueError:
                    continue
                raw, unavailable = parsed[sid].raw, {}
            candidate = {'opportunity_id': opportunity['opportunity_id'], 'target_id': target['target_id'],
                         'source_id': sid, 'issued_at': row['issued_at'], 'available_at': row['issued_at'] + LAG,
                         'valid_until': min(row['valid_end'], start), 'projection': projection, 'raw': raw,
                         'amendment_kind': row['amendment_kind'], 'probability': None,
                         'probability_status': 'awaiting_separate_development_calibration',
                         'native_semantics_sha256': row['native_semantics_sha256'], **unavailable}
            candidates.append(candidate)
            by_pair[(opportunity['opportunity_id'], sid)] = candidate
        decision = current_taf(products, station=target['entity'], cutoff=opportunity['cutoff'], start=start, end=end)
        decisions.append({'opportunity_id': opportunity['opportunity_id'], **decision})
        if decision['status'] in {'active', 'unparsed'}:
            latest.append(by_pair[(opportunity['opportunity_id'], decision['selected_id'])])
    old = {r['opportunity_id']: r for r in load(dataset / 'environment/LATEST_BASELINES.json')}
    new = {r['opportunity_id']: r for r in latest}
    changes = []
    for o in opportunities:
        oid = o['opportunity_id']
        before, after = old.get(oid), new.get(oid)
        strip = lambda row: None if row is None else {k: v for k, v in row.items() if k != 'native_semantics_sha256'}
        if strip(before) != strip(after):
            changes.append({'opportunity_id': oid, 'old_source': None if before is None else before['source_id'],
                            'new_source': None if after is None else after['source_id']})
    output.mkdir(parents=True, exist_ok=False)
    for directory in ('public', 'private'):
        shutil.copytree(dataset / directory, output / directory)
    (output / 'environment').mkdir()
    shutil.copyfile(dataset / 'environment/QUERY_RESULTS.json', output / 'environment/QUERY_RESULTS.json')
    save(output / 'environment/BASELINE_CANDIDATES.json', candidates)
    save(output / 'environment/LATEST_BASELINES.json', latest)
    save(output / 'environment/NATIVE_PRODUCT_INDEX.json', products)
    save(output / 'environment/NATIVE_RESOLUTION.json', decisions)
    save(output / 'SOURCES.json', verified)
    save(output / 'SOURCE_IMPACT.json', {'schema': 'disastertrace.native_impact.v2',
         'source_dataset': str(dataset), 'original_sources_sha256': digest(dataset / 'SOURCES.json'),
         'verified_captures': len(verified), 'decoded_native_taf': len(parsed),
         'opportunities': len(opportunities), 'unchanged': len(opportunities) - len(changes),
         'affected': changes, 'not_evaluated': [], 'decisions': dict(Counter(r['status'] for r in decisions)),
         'failures': failures, 'new_model_calls': 0, 'bank_not_refitted': True,
         'native_version_policy': 'latest_before_coverage.v2', 'first_seen_historically_verified': False})
    save(output / 'BUILD.json', {'builder_sha256': digest(Path(__file__)),
         'built_at': datetime.now(timezone.utc).isoformat(),
         'files': {str(p.relative_to(output)): digest(p) for p in output.rglob('*') if p.is_file()},
         'scope': 'derived development data; original captures and datasets remain frozen'})
    print(json.dumps(load(output / 'SOURCE_IMPACT.json'), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset', type=Path, default=REPO / 'plans/v7_adaptive_execution_20260913/development_dataset_01')
    parser.add_argument('--source-root', type=Path, default=REPO / 'plans/v7_adaptive_execution_20260913')
    parser.add_argument('--output', type=Path, default=HERE / 'development_dataset_v2')
    args = parser.parse_args()
    main(args.dataset, args.source_root, args.output)
