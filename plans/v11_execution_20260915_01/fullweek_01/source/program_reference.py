"""Full-denominator, predeclared program comparisons under canonical outcomes."""

import argparse
import datetime
import hashlib
import json
import os
import shutil
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path

from disastertrace.monitoring_fixed_v1.admission import AdmissionEngine, TypedOpportunity, score_admitted
from disastertrace.monitoring_fixed_v1.aviation import typed_target
from disastertrace.monitoring_fixed_v1.contracts import fingerprint
from disastertrace.monitoring_fixed_v1.outcomes import ComparisonContract, OutcomeRegistry, experiment_spec
from disastertrace.monitoring_v1.dataset import load_session
from disastertrace.monitoring_v1.execution import bind_execution
from disastertrace.monitoring_v1.journal import EventJournal
from disastertrace.monitoring_v1.policies import run_session
from disastertrace.monitoring_v1.resources import BudgetLedger
from disastertrace.monitoring_v1.targets import utc_us

HERE = Path(os.environ.get('DISASTERTRACE_V8_EXECUTION_ROOT', Path(__file__).resolve().parents[1]))
REPO = HERE.parents[1]


def load(path):
    return json.loads(path.read_text())


def save(path, value):
    with path.open('x') as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write('\n')
        handle.flush()
        os.fsync(handle.fileno())


def configs(hours, protocol):
    base = {'seed': 20260913, 'request_budget': hours * 3,
            'forecast_call_cap': hours * 9, 'model_call_budget': hours * 9,
            'per_tick_forecast_cap': 9, 'input_token_cap': 8192, 'output_token_cap': 384,
            'call_compute_cap_ms': 120000, 'wakeup_seconds': 600,
            'token_cap': hours * 9 * 8576, 'compute_ms_cap': hours * 9 * 120100,
            'selector_kind': 'round_robin', 'isolation_mode': 'public_schedule',
            'public_call_slot_ms': 30000, 'allocation_mode': 'global_budget',
            'authorization_mode': 'session_shared', 'protocol': protocol,
            'session_runtime': 'typed_admission_v1', 'typed_head': 'joint',
            'persistence_latency_ms': 1, 'acquire': True, 'predict': True,
            'query_limit_per_tick': None}
    arms = {'P00_follow': dict(base, acquire=False, predict=False),
            'P01_base_only': dict(base, acquire=False),
            'P02_one_read': dict(base, query_limit_per_tick=1),
            'P03_batch_shared': dict(base, selector_kind='batch_complete'),
            'P04_risk_shared': dict(base, selector_kind='risk'),
            'P05_coverage_shared': dict(base, selector_kind='coverage')}
    for alloc, short_a in [('fixed_quota', 'q'), ('global_budget', 'g')]:
        for auth, short_s in [('target_private', 'p'), ('session_shared', 's')]:
            arms['P06_' + short_a + short_s] = dict(base, allocation_mode=alloc, authorization_mode=auth)
    return {key: bind_execution(value, None) for key, value in arms.items()}


def outcomes(dataset, data, out):
    target_by_id = {t['target_id']: typed_target(t) for t in data['targets']}
    original = {r['target_id']: r for r in load(dataset / 'private/OUTCOMES.json')}
    sources = load(dataset / 'SOURCES.json')
    decoded = {(r['source_id'], r['source_line']): r for r in load(dataset / 'private/DECODED_REPORTS.json')}
    registry = OutcomeRegistry(target_by_id.values())
    resolved = utc_us(datetime.datetime.now(datetime.timezone.utc).isoformat())
    for tid, target in target_by_id.items():
        row = original[tid]
        bindings = []
        fetched, observed = [], []
        for reference in row['references']:
            source = sources[reference['source_id']]
            path = Path(source['path'])
            receipt = load(Path(source['receipt_path']))
            assert hashlib.sha256(path.read_bytes()).hexdigest() == source['sha256'] == receipt['sha256']
            report = decoded[reference['source_id'], reference['source_line']]
            bindings.append(dict(reference, source_sha256=source['sha256'], native_report_sha256=fingerprint(report)))
            fetched.append(utc_us(receipt['finished_at']))
            if report.get('observation_time') is not None:
                observed.append(report['observation_time'])
        registry.register({'target_contract_hash': target.contract_hash, 'resolution_version': 'native_final_archive.v2',
                           'value': row['outcome'], 'status': 'mature' if row['outcome'] is not None else 'missing',
                           'source_revision': fingerprint(bindings) if bindings else None,
                           'source_sha256': bindings[0]['source_sha256'] if len(bindings) == 1 else fingerprint(bindings),
                           'physical_start': target.physical_start, 'physical_end': target.physical_end,
                           'units': target.units, 'quality_status': row['status'],
                           'observed_at': max(observed) if observed else None, 'published_at': None,
                           'fetched_at': max(fetched) if fetched else None, 'resolved_at': resolved,
                           'availability_basis': 'declared_archive_scenario', 'references': bindings,
                           'reference_kind': 'final_archived_routine_report_not_continuous_physical_truth'})
    opportunities = [TypedOpportunity(o['opportunity_id'], target_by_id[o['target_id']], o['cutoff']) for o in data['opportunities']]
    rows = registry.opportunity_rows(opportunities, {o.opportunity_id: 'native_final_archive.v2' for o in opportunities})
    save(out / 'OUTCOME_REGISTRY.json', registry.export())
    save(out / 'OUTCOMES.json', rows)
    return rows


def freeze(dataset, out, threshold, protocol):
    data = load_session(dataset, stations=['KSFO', 'KOAK', 'KSJC'], threshold=threshold)
    hours = len({o['cutoff'] for o in data['opportunities']})
    bank = load(HERE / 'contracts/BANK.json')
    arms = configs(hours, protocol)
    hashes = [fingerprint(settings) for settings in arms.values()]
    assert len(hashes) == len(set(hashes)), 'Alias must be frozen before running'
    spec = experiment_spec(data, bank, next(iter(arms.values())))
    allowed = defaultdict(list)
    for settings in arms.values():
        current = experiment_spec(data, bank, settings)
        assert spec['invariants'] == current['invariants']
        for key, value in current['interventions'].items():
            if value not in allowed[key]:
                allowed[key].append(value)
    comparison = ComparisonContract(spec['invariants'], allowed)
    out.mkdir(parents=True, exist_ok=False)
    save(out / 'DATA.json', data)
    save(out / 'BANK.json', bank)
    save(out / 'CONFIGS.json', arms)
    save(out / 'COMPARISON.json', comparison.export())
    rows = outcomes(dataset, data, out)
    package = REPO / 'disastertrace-starter/src/disastertrace'
    source = {str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest()
              for module in ('monitoring_v1', 'monitoring_fixed_v1') for p in (package / module).rglob('*.py')}
    for module in ('monitoring_v1', 'monitoring_fixed_v1'):
        shutil.copytree(package / module, out / 'source/disastertrace' / module,
                        ignore=shutil.ignore_patterns('__pycache__'))
    (out / 'source/disastertrace/__init__.py').write_text('"""Frozen v8 program comparison package."""\n')
    shutil.copyfile(Path(__file__), out / 'source/run_program_calendar.py')
    save(out / 'FREEZE.json', {'frozen_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
         'hours': hours, 'opportunities': len(rows), 'threshold_m': threshold, 'protocol': protocol,
         'unique_targets': len(data['targets']), 'arms': list(arms), 'aliases': {},
         'one_read_definition': 'at most one fixed-order legal source acquisition per public tick; unused credit carries',
         'batch_definition': 'wait until all currently eligible pending queries fit released credit; never unlimited',
         'processing_timing': 'declared 1ms program + 1ms persistence, fixed public 30s slot; no historical wall-time claim',
         'source': source, 'files': {name: fingerprint(load(out / name)) for name in
                   ('DATA.json', 'BANK.json', 'CONFIGS.json', 'COMPARISON.json', 'OUTCOMES.json')},
         'confirmation': False, 'independent_process_count': None,
         'outcome_statuses': dict(Counter(r['quality_status'] for r in rows)),
         'positive_opportunities': sum(r['value'] == 1 for r in rows)})
    print(json.dumps({'frozen': str(out), 'hours': hours, 'opportunities': len(rows), 'arms': len(arms)}))


def verify(out):
    frozen = load(out / 'FREEZE.json')
    for rel, expected in frozen['source'].items():
        path = out / 'source' / Path(rel).relative_to('disastertrace-starter/src')
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, rel
    import inspect
    assert Path(inspect.getfile(AdmissionEngine)).is_relative_to(out.resolve() / 'source'), 'Use the frozen package PYTHONPATH'
    for name, expected in frozen['files'].items():
        assert fingerprint(load(out / name)) == expected, name


def run(out, arm):
    verify(out)
    data, bank = load(out / 'DATA.json'), load(out / 'BANK.json')
    settings = load(out / 'CONFIGS.json')[arm]
    target = out / arm
    target.mkdir(exist_ok=False)
    with EventJournal(target / 'admission.jsonl') as journal, EventJournal(target / 'resources.jsonl') as resources:
        report = run_session(data, bank, settings, journal=journal, resource_journal=resources)
    save(target / 'REPORT.json', report)
    restored = AdmissionEngine.from_journal(target / 'admission.jsonl')
    assert restored.export() == report['event_replay']
    with EventJournal(target / 'resources.jsonl') as journal:
        ledger = BudgetLedger.restore(journal)
        assert asdict(ledger.spent) == report['resource_spent']
        assert asdict(ledger.reserved) == report['resource_reserved']
    assert len(restored.snapshots) == len(data['opportunities'])
    result = {'arm': arm, 'snapshots': len(restored.snapshots), 'program_calls': len(report['calls']),
              'spent': report['resource_spent'], 'reserved': report['resource_reserved'],
              'calls_admitted': dict(Counter(r['admission_status'] for r in report['calls'])),
              'E': report['e_counts'], 'new_model_calls': 0, 'replay_equal': True}
    save(target / 'VALIDATION.json', result)
    print(json.dumps(result))


def score(out):
    verify(out)
    spec = load(out / 'COMPARISON.json')['payload']
    comparison = ComparisonContract(spec['invariants'], spec['allowed_interventions'])
    arms = load(out / 'CONFIGS.json')
    for arm in arms:
        assert load(out / arm / 'VALIDATION.json')['replay_equal']
    rows = load(out / 'OUTCOMES.json')
    report = score_admitted(rows, {arm: out / arm / 'admission.jsonl' for arm in arms}, comparison=comparison)
    report['interpretation'] = 'One exposed historical development day; report descriptive losses, no independent-process CI.'
    report['missingness'] = {'quality': dict(Counter(r['quality_status'] for r in rows)),
                             'bounds_assumption': 'No exchangeability or missing-at-random assumption.'}
    save(out / 'SCORES.json', report)
    print(json.dumps(report['scores'], indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['freeze', 'run', 'score'])
    parser.add_argument('--dataset', type=Path, default=HERE / 'development_dataset_v2')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--threshold', type=int, default=5000)
    parser.add_argument('--protocol', default='base_bound_override')
    parser.add_argument('--arm')
    args = parser.parse_args()
    if args.mode == 'freeze':
        freeze(args.dataset, args.out, args.threshold, args.protocol)
    elif args.mode == 'run':
        run(args.out, args.arm)
    else:
        score(args.out)
