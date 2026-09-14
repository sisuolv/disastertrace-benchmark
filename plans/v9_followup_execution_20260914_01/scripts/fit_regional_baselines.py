"""Fit native TAF frequencies, then calibrate on a separate purged period."""

from collections import Counter, defaultdict
import copy
import datetime as dt
import itertools
import json
from pathlib import Path

from disastertrace.monitoring_v1.calibration import feature_key, predict
from disastertrace.monitoring_v1.providers.versions import current_taf
from disastertrace.monitoring_v1.regional_calibration import fit_monotone
from disastertrace.monitoring_v1.targets import canonical_hash

ROOT = Path(__file__).resolve().parents[1]


def load(p):
    return json.loads(p.read_text())


def save(p, d):
    with p.open('x') as f:
        json.dump(d, f, indent=2, allow_nan=False)
        f.write('\n')


def examples(dataset, manifest):
    targets = {r['target_id']: r for r in load(dataset / 'public/TARGETS.json')}
    native = load(dataset / 'environment/NATIVE_PRODUCT_INDEX.json')
    candidates = {(r['opportunity_id'], r['source_id']): r for r in load(dataset / 'environment/BASELINE_CANDIDATES.json')}
    catalog = {r['query_id']: r for r in load(dataset / 'public/QUERY_CATALOG.json')}
    results = {r['query_id']: r for r in load(dataset / 'environment/QUERY_RESULTS.json')}
    for row in manifest:
        if row['outcome'] is None:
            continue
        target = targets[row['target_id']]
        dispatch = row['cutoff'] - 600_000_000
        decision = current_taf(native, station=row['station'], cutoff=dispatch,
            start=target['physical_start'], end=target['physical_end'])
        candidate = candidates.get((row['opportunity_id'], decision.get('selected_id')))
        qids = row['query_ids']
        legal = [q for q in qids if catalog[q]['available_at'] + catalog[q]['latency_ms'] * 1000 <= dispatch]
        views = [{q: results[q] for q in subset}
                 for n in range(1, len(legal) + 1) for subset in itertools.combinations(legal, n)]
        yield row, target, candidate, qids, views


def main():
    manifest = load(ROOT / 'reports/process_manifest_02/DATA_PROCESS_MANIFEST.json')['rows']
    out = ROOT / 'reports/regional_baselines_01'
    out.mkdir(exist_ok=False)
    all_stats = []
    for region in ['bay', 'new_york', 'chicago', 'denver']:
        directory = out / region
        directory.mkdir()
        regional = [r for r in manifest if r['region'] == region]
        dataset = ROOT / 'regional_training_02' / region / 'dataset_v2'
        training = [r for r in regional if r['role'] in {'fit', 'calibration'}]
        samples = list(examples(dataset, training))
        cells = defaultdict(lambda: {'n': 0, 'positive': 0})
        fitted = []
        for row, target, candidate, qids, views in samples:
            if row['role'] != 'fit':
                continue
            keys = {json.dumps([target['threshold'], 'pooled'], separators=(',', ':')),
                    feature_key(target, candidate)}
            keys.update(feature_key(target, candidate, qids, view) for view in views)
            for key in keys:
                cells[key]['n'] += 1
                cells[key]['positive'] += row['outcome']
            fitted.append(row['opportunity_id'])
        bank = {'schema': 'disastertrace.monitoring.frequency_bank.v1',
            'mapping_version': 'regional_dec2024_frequency.v1', 'minimum_cell_n': 20,
            'smoothing': '(positive+1)/(n+2)', 'cells': dict(cells),
            'fit_disclosure': {'region': region, 'fit_interval': ['2024-12-01', '2024-12-19'],
                'calibration_interval': ['2024-12-23', '2024-12-29'], 'lead_hours': [1],
                'sample_identity': 'one target at 1h cutoff; evidence variants deduplicated per cell',
                'fit_ids_sha256': canonical_hash(sorted(fitted)), 'development_only': True,
                'availability': 'declared archive latency', 'calibration_guarantee': False}}
        calibrated = copy.deepcopy(bank)
        bins = defaultdict(list)
        cal_ids = []
        for row, target, candidate, qids, views in samples:
            if row['role'] != 'calibration':
                continue
            threshold = str(target['threshold'])
            bins[threshold, 'base'].append((predict(bank, target, candidate)['probability'], row['outcome'], 1))
            for view in views:
                bins[threshold, 'evidence'].append((predict(bank, target, candidate, qids, view)['probability'],
                                                 row['outcome'], 1 / len(views)))
            cal_ids.append(row['opportunity_id'])
        assert set(fitted).isdisjoint(cal_ids)
        calibrated['post_calibration'] = {str(t): {kind: fit_monotone(bins[str(t), kind])
                         for kind in ['base', 'evidence']} for t in [1000, 5000]}
        calibrated['mapping_version'] = 'regional_dec2024_frequency_pav.v1'
        calibrated['fit_disclosure']['calibration_ids_sha256'] = canonical_hash(sorted(cal_ids))
        calibrated['fit_disclosure']['post_mapping'] = 'weighted PAV with one Laplace pair per distinct probability'
        save(directory / 'BANK_RAW.json', bank)
        save(directory / 'BANK.json', calibrated)
        save(directory / 'FIT_IDS.json', fitted)
        save(directory / 'CALIBRATION_IDS.json', cal_ids)
        metrics = defaultdict(lambda: {'n': 0, 'positive': 0, 'B': 0.0, 'fB': 0.0, 'fBE': 0.0})
        forecasts = []
        evaluation = [r for r in regional if r['role'] == 'development_evaluation']
        by_dataset = defaultdict(list)
        for row in evaluation:
            by_dataset[row['dataset']].append(row)
        for path, rows in by_dataset.items():
            for row, target, candidate, qids, views in examples(Path(path), rows):
                known = views[-1] if views else {}
                probs = {'B': predict(bank, target, candidate)['probability'],
                         'fB': predict(calibrated, target, candidate)['probability'],
                         'fBE': predict(calibrated, target, candidate, qids, known)['probability']}
                key = str(target['threshold'])
                m = metrics[key]
                m['n'] += 1
                m['positive'] += row['outcome']
                for name, probability in probs.items():
                    m[name] += (probability - row['outcome']) ** 2
                forecasts.append({'opportunity_id': row['opportunity_id'], 'process_group_id': row['process_group_id'],
                                  'outcome': row['outcome'], 'threshold_m': target['threshold'], **probs})
        for m in metrics.values():
            for name in ['B', 'fB', 'fBE']:
                m[name] /= m['n']
        save(directory / 'EVALUATION_FORECASTS.json', forecasts)
        stats = {'region': region, 'fit_targets': len(fitted), 'calibration_targets': len(cal_ids),
                 'metrics': dict(metrics), 'evaluation_missing': sum(r['outcome'] is None for r in evaluation),
                 'bank_sha256': canonical_hash(calibrated),
                 'scope': 'fixed legal evidence / 10min-before-cutoff snapshots; not continuous same-budget model scores'}
        save(directory / 'VALIDATION.json', stats)
        all_stats.append(stats)
    save(out / 'SUMMARY.json', {'regions': all_stats, 'model_calls': 0, 'confirmation_opened': False,
          'completed_at': dt.datetime.now(dt.timezone.utc).isoformat()})
    print(json.dumps(all_stats), flush=True)


if __name__ == '__main__':
    main()
