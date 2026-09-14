"""Audit downloaded calendars, native footprints and conservative dependence blocks."""

import argparse
from collections import Counter, defaultdict
import datetime as dt
import hashlib
import json
from pathlib import Path

from disastertrace.monitoring_v1.process_split import chronological_roles, process_components
from disastertrace.monitoring_v1.targets import utc_us

ROOT = Path(__file__).resolve().parents[1]
V8 = ROOT.parent / 'v8_measurement_execution_20260913_01'
HOUR = 3_600_000_000


def load(p):
    return json.loads(p.read_text())


def save(p, value):
    with p.open('x') as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.write('\n')


def dataset_rows(name, region, dataset):
    targets = {r['target_id']: r for r in load(dataset / 'public/TARGETS.json')}
    outcomes = {r['target_id']: r for r in load(dataset / 'private/OUTCOMES.json')}
    pairs = {r['opportunity_id']: r for r in load(dataset / 'public/E_F_PAIRS.json')}
    catalog = {r['query_id']: r for r in load(dataset / 'public/QUERY_CATALOG.json')}
    sources = load(dataset / 'SOURCES.json')
    for binding in sources.values():
        assert hashlib.sha256(Path(binding['path']).read_bytes()).hexdigest() == binding['sha256']
        assert hashlib.sha256(Path(binding['receipt_path']).read_bytes()).hexdigest() == binding['receipt_sha256']
    candidates = defaultdict(list)
    for r in load(dataset / 'environment/BASELINE_CANDIDATES.json'):
        candidates[r['opportunity_id']].append(r)
    rows = []
    for o in load(dataset / 'public/OPPORTUNITIES.json'):
        if o['lead_hours'] != 1:
            continue
        oid, target = o['opportunity_id'], targets[o['target_id']]
        native = [r for r in candidates[oid] if r['available_at'] <= o['cutoff']]
        query = [catalog[q] for q in pairs[oid]['query_ids']]
        first = min([o['cutoff'] - 600_000_000] + [r['issued_at'] for r in native] + [r['slot_start'] for r in query])
        versions = sorted({sources[r['source_id']]['sha256'] for r in native})
        row = {**o, 'calendar': name, 'region': region, 'station': target['entity'],
            'dataset': str(dataset), 'footprint_start': first, 'footprint_end': target['physical_end'],
            'target_start': target['physical_start'], 'target_end': target['physical_end'],
            'native_versions': versions, 'query_ids': pairs[oid]['query_ids'],
            'outcome': outcomes[o['target_id']]['outcome'], 'quality_status': outcomes[o['target_id']]['status'],
            'exposure': 'development', 'availability_basis': 'declared_archive_scenario'}
        assert row['cutoff'] < row['target_start'] < row['target_end']
        assert row['footprint_end'] <= utc_us('2025-02-17T00:00:00Z') or row['footprint_start'] >= utc_us('2025-02-24T00:00:00Z')
        rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--include-training', action='store_true')
    args = parser.parse_args()
    out = ROOT / 'reports' / ('process_manifest_02' if args.include_training else 'process_manifest_01')
    out.mkdir(exist_ok=False)
    datasets = [('bay_initial', 'bay', V8 / 'development_dataset_v2'),
                ('bay_extension', 'bay', V8 / 'calendar_extension_01/dataset_v2_complete_02')]
    datasets += [(r, r, V8 / 'regional_calendar_extension_01' / r / 'dataset_v2')
                 for r in ['new_york', 'chicago', 'denver']]
    if args.include_training:
        training = ROOT / 'regional_training_02'
        assert load(training / 'COMPLETE.json')['all_complete']
        datasets += [(r + '_training', r, training / r / 'dataset_v2')
                     for r in ['bay', 'new_york', 'chicago', 'denver']]
    merged, duplicates = {}, []
    for name, region, dataset in datasets:
        for row in dataset_rows(name, region, dataset):
            key = row['opportunity_id']
            if key in merged:
                previous = merged[key]
                assert (previous['outcome'], previous['target_start']) == (row['outcome'], row['target_start'])
                previous['native_versions'] = sorted(set(previous['native_versions']) | set(row['native_versions']))
                previous['footprint_start'] = min(previous['footprint_start'], row['footprint_start'])
                duplicates.append({'opportunity_id': key, 'calendars': [previous['calendar'], row['calendar']]})
            else:
                merged[key] = row
    rows = sorted(merged.values(), key=lambda r: r['opportunity_id'])
    intervals = {'fit': (utc_us('2024-12-01T00:00:00Z'), utc_us('2024-12-19T00:00:00Z')),
                 'calibration': (utc_us('2024-12-23T00:00:00Z'), utc_us('2024-12-29T00:00:00Z')),
                 'development_evaluation': (utc_us('2025-01-01T00:00:00Z'), utc_us('2025-02-17T00:00:00Z'))}
    roles = chronological_roles(rows, intervals)
    groups = process_components(rows, gap_us=72 * HOUR)
    counts = defaultdict(Counter)
    for row in rows:
        row['role'], row['process_group_id'] = roles[row['opportunity_id']], groups[row['opportunity_id']]
        count = counts[(row['region'], row['role'], row['threshold_m'])]
        count['targets'] += 1
        count['positive'] += int(row['outcome'] == 1)
        count['negative'] += int(row['outcome'] == 0)
        count['missing'] += int(row['outcome'] is None)
    summary = []
    for (region, role, threshold), count in sorted(counts.items()):
        subset = [r for r in rows if (r['region'], r['role'], r['threshold_m']) == (region, role, threshold)]
        summary.append({'region': region, 'role': role, 'threshold_m': threshold, **count,
            'conservative_blocks': len({r['process_group_id'] for r in subset}),
            'positive_blocks': len({r['process_group_id'] for r in subset if r['outcome'] == 1})})
    sensitivity = {str(h): len(set(process_components(rows, gap_us=h*HOUR).values())) for h in [0, 24, 72, 168]}
    save(out / 'DATA_PROCESS_MANIFEST.json', {'rows': rows, 'duplicate_opportunities': duplicates,
         'grouping': 'global interval overlap + 72h gap + native-version union; dependence blocks, not synoptic truth',
         'verified_native_source_hashes': True, 'lead_hours': [1], 'confirmation_opened': False})
    save(out / 'SPLITS.json', {'intervals': intervals, 'assignments': roles,
         'rule': 'entire input/reference footprint within one role; no shared native TAF across roles'})
    save(out / 'COVERAGE.json', {'strata': summary, 'grouping_sensitivity_hours': sensitivity,
         'independent_weather_process_count_established': False, 'model_calls': 0})
    lines = ['# 真实数据覆盖与切分', '', '本表只统计 1h 提前量；阈值共享观测，不能相加作为独立天气过程。',
             '分组是保守时间/版本相关块，尚不是经天气系统识别确认的独立过程。', '',
             '| 区域 | 用途 | 阈值 m | 目标 | 正例 | 负例 | 缺失 | 相关块 | 正例块 |',
             '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for r in summary:
        lines.append('| ' + ' | '.join(str(r.get(k, 0)) for k in ['region','role','threshold_m','targets','positive','negative','missing','conservative_blocks','positive_blocks']) + ' |')
    lines += ['', '全部历史首次可见时间仍采用声明情景。保留确认周未读取。',
              '当前块数不能支持把数千目标作为独立样本。扩展日期须预注册，按完整过程报告。']
    (out / 'COVERAGE_REPORT_CN.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'rows': len(rows), 'strata': summary, 'blocks': sensitivity}))


if __name__ == '__main__':
    main()
