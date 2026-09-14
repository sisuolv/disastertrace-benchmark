"""Full seven-day information controls, with independent snapshot admission units."""

import datetime
import hashlib
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path

from disastertrace.monitoring_fixed_v1.admission import AdmissionEngine, AdmissionEvent, TypedOpportunity
from disastertrace.monitoring_fixed_v1.aviation import AviationProvider, FrozenFrequencyPredictor, visible_e_status
from disastertrace.monitoring_fixed_v1.contracts import Forecast, Target, canonical, fingerprint, paired_scores
from disastertrace.monitoring_v1.calibration import predict

from run_program_calendar import outcomes

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
DATASET = HERE / 'calendar_extension_01/dataset_v2_complete_02'
OUT = HERE / 'reports/calendar_information_controls_01'


def load(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open('x') as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write('\n')


def main():
    repair = load(HERE / 'calendar_extension_01/COMPLETENESS_REPAIR_IMPACT.json')
    assert repair['native_bulletins'] == 207 and repair['opportunities'] == 3024
    for rel, sha in load(DATASET / 'BUILD.json')['files'].items():
        assert digest(DATASET / rel) == sha, rel
    bank = load(HERE / 'contracts/BANK.json')
    provider = AviationProvider(DATASET, bank)
    predictor = FrozenFrequencyPredictor(bank)
    OUT.mkdir(parents=True, exist_ok=False)
    save(OUT / 'CONTRACT.json', {'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'dataset_build_sha256': digest(DATASET / 'BUILD.json'), 'calendar_sha256': digest(HERE / 'calendar_extension_01/CALENDAR.json'),
        'bank_sha256': fingerprint(bank), 'opportunities': 3024, 'model_calls': 0,
        'unit': 'Independent opportunity snapshot; no predictor state carried across lead times.',
        'dispatch': 'cutoff minus 60 seconds, legal source current at dispatch; full common updates through cutoff',
        'processing': 'declared 1ms computation plus 1ms persistence; deterministic program only',
        'conditions': ['common_only', 'fixed_one', 'all_registered'],
        'selection': 'All registered 2025-02-04 through 2025-02-10 cutoffs, 3 stations, 3 leads, both thresholds.',
        'limitations': ['Information comparator; not a shared-budget adaptive session.',
                        'Days/sites/lead-times are correlated; no independent-process confidence intervals.',
                        'The 1km and 5km thresholds are reported separately; 5km is not automatically severe fog.',
                        'December 2023 Bay bank is unchanged; no fit on this outcome calendar.',
                        'Archive availability is a declared timing scenario, not proven historical first-seen.']})
    package = REPO / 'disastertrace-starter/src/disastertrace'
    for module in ('monitoring_v1', 'monitoring_fixed_v1'):
        shutil.copytree(package / module, OUT / 'source/disastertrace' / module, ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copyfile(Path(__file__), OUT / 'source/evaluate_calendar_controls.py')
    shutil.copyfile(Path(__file__).with_name('run_program_calendar.py'), OUT / 'source/run_program_calendar.py')
    save(OUT / 'SOURCE_MANIFEST.json', {str(p.relative_to(OUT)): digest(p) for p in (OUT / 'source').rglob('*.py')})
    canonical_rows = outcomes(DATASET, {'targets': list(provider.targets.values()),
                             'opportunities': list(provider.opportunities.values())}, OUT)
    outcome_by_id = {r['opportunity_id']: r for r in canonical_rows}
    all_predictions = {k: {} for k in ('follow', 'program_common_only', 'program_fixed_one', 'program_all_registered')}
    records, replay_rows = [], []
    for index, legacy_opportunity in enumerate(provider.opportunities.values()):
        oid = legacy_opportunity['opportunity_id']
        cutoff = legacy_opportunity['cutoff']
        dispatch = cutoff - 60_000_000
        legacy = provider.targets[legacy_opportunity['target_id']]
        target = Target(**provider.freeze(oid, 'common_only').policy_view()['target'])
        opportunity = TypedOpportunity(oid, target, cutoff)
        fallback = Forecast(target.contract_hash, 'event_probability', 'probability', predict(bank, legacy, None)['probability'])
        times = {dispatch, cutoff}
        times.update(p['issued_at'] + 120_000_000 for p in provider.native_products
                     if p['station'] == legacy['entity'] and dispatch < p['issued_at'] + 120_000_000 <= cutoff)
        common, previous = [], None
        for at in sorted(times):
            common_bundle = provider.freeze(oid, 'common_only', as_of=at)
            if common_bundle.base_hash == previous:
                continue
            common.append(AdmissionEvent('common-' + str(len(common)), common_bundle.policy_view()['baseline']['available_at'],
                                        'baseline', {'bundle': common_bundle.to_dict()}))
            previous = common_bundle.base_hash
        follow = AdmissionEngine([opportunity], fallbacks={target.target_id: fallback.to_dict()})
        follow.run(common, until=cutoff)
        all_predictions['follow'][oid] = follow.snapshots[oid]['forecast']
        for condition in ('common_only', 'fixed_one', 'all_registered'):
            bundle = provider.freeze(oid, condition, as_of=dispatch)
            row = bundle.policy_view()
            assert max([row['baseline']['available_at']] + [a['completed_at'] for a in row['assets']]) <= dispatch
            candidate, details = predictor.predict_with_details(bundle)
            raw = canonical(candidate.to_dict())
            events = [*common, AdmissionEvent('begin', dispatch, 'begin', {'call_id': 'call',
                        'bundle': bundle.to_dict(), 'head': 'program', 'executor': 'frozen_frequency'}),
                AdmissionEvent('complete', dispatch + 2000, 'completion', {'call_id': 'call', 'bundle_hash': bundle.bundle_hash,
                    'raw': raw, 'raw_sha256': hashlib.sha256(raw.encode()).hexdigest(), 'started_at': dispatch,
                    'completed_at': dispatch + 1000, 'persisted_at': dispatch + 2000, 'expires_at': cutoff,
                    'cost': {'requests': 0, 'bytes': len(raw.encode()), 'tokens': 0, 'compute_ms': 1},
                    'ended_with_eos': True, 'head': 'program', 'executor': 'frozen_frequency'})]
            engine = AdmissionEngine([opportunity], fallbacks={target.target_id: fallback.to_dict()})
            engine.run(events, until=cutoff)
            envelope = engine.export()
            # JSON roundtrip and the engine's history replay cover every unit, not a sample.
            restored = AdmissionEngine.restore(json.loads(json.dumps(envelope)))
            assert restored.export() == envelope and len(engine.calls) == 1
            assert not any(r['status'] == 'invalid_begin' for r in engine.attempts)
            snapshot = engine.snapshots[oid]
            all_predictions['program_' + condition][oid] = snapshot['forecast']
            e_status = visible_e_status(bundle)
            final = snapshot['forecast']['value']
            record = {'opportunity_id': oid, 'condition': condition, 'threshold_m': legacy['threshold'],
                'station': legacy['entity'], 'lead_hours': legacy_opportunity['lead_hours'],
                'cutoff': cutoff, 'dispatch': dispatch, 'target_id': target.target_id,
                'outcome_record_sha256': fingerprint(outcome_by_id[oid]),
                'outcome': outcome_by_id[oid]['value'], 'outcome_status': outcome_by_id[oid]['status'],
                'E_status': e_status, 'query_count': len(row['receipts']), 'bundle_hash': bundle.bundle_hash,
                'candidate_probability': candidate.value, 'mapping_details': details,
                'dispatch_baseline_probability': row['baseline']['forecast']['value'],
                'cutoff_baseline_probability': all_predictions['follow'][oid]['value'],
                'effective_probability': final, 'effective_mode': snapshot['mode'],
                'candidate_action': 'OVERRIDE', 'shared_budget_comparison': False,
                'source_statuses': [a['missingness'] for a in row['assets']],
                'replay_sha256': fingerprint(envelope)}
            records.append(record)
            replay_rows.append({'opportunity_id': oid, 'condition': condition, 'engine': envelope})
        if (index + 1) % 216 == 0:
            print(json.dumps({'opportunities_evaluated': index + 1, 'expected': 3024}), flush=True)
    save(OUT / 'RECORDS.json', records)
    with (OUT / 'ADMISSION_REPLAYS.jsonl').open('x') as handle:
        for row in replay_rows:
            handle.write(canonical(row) + '\n')
    summaries = {}
    for threshold in (1000, 5000):
        opps = [o for o in provider.opportunities.values() if o['threshold_m'] == threshold]
        typed = [{'opportunity_id': o['opportunity_id'],
                  'target': provider.freeze(o['opportunity_id'], 'common_only').policy_view()['target'],
                  'outcome': outcome_by_id[o['opportunity_id']]['value']
                     if outcome_by_id[o['opportunity_id']]['status'] == 'mature' else None} for o in opps]
        score = paired_scores(typed, {arm: {r['opportunity_id']: values[r['opportunity_id']] for r in typed}
                                     for arm, values in all_predictions.items()})
        by_target = {o['target_id']: outcome_by_id[o['opportunity_id']]['value'] for o in opps}
        evidence = defaultdict(Counter)
        for r in records:
            if r['threshold_m'] != threshold:
                continue
            group = evidence[r['condition']]
            group['registered'] += 1
            group[r['E_status']] += 1
            group['candidate_changed'] += r['candidate_probability'] != r['dispatch_baseline_probability']
            group['effective_changed_from_follow'] += r['effective_probability'] != r['cutoff_baseline_probability']
            if r['outcome_status'] == 'mature':
                delta = (r['effective_probability'] - r['outcome']) ** 2 - (r['cutoff_baseline_probability'] - r['outcome']) ** 2
                group['improved'] += delta < 0
                group['worsened'] += delta > 0
                group['unchanged'] += delta == 0
        summaries[str(threshold)] = {'F': score, 'E_and_changes': dict(evidence),
            'positive_opportunities': sum(r['outcome'] == 1 for r in typed),
            'unique_targets': len(by_target), 'unique_positive_targets': sum(y == 1 for y in by_target.values()),
            'independent_process_count': None}
    save(OUT / 'REPORT.json', {'schema': 'disastertrace.seven_day_information_controls.v1', 'by_threshold_m': summaries,
         'opportunities': 3024, 'program_unit_replays': len(replay_rows), 'model_calls': 0,
         'all_opportunities_retained': True, 'full_shared_budget_session': False,
         'independent_confirmation': False, 'completed_at': datetime.datetime.now(datetime.timezone.utc).isoformat()})
    save(OUT / 'VALIDATION.json', {'passed': True, 'registered': 3024, 'replayed_program_units': len(replay_rows),
         'no_fit_on_evaluation_outcomes': True, 'all_native_files_verified': True})
    print(json.dumps(summaries), flush=True)


if __name__ == '__main__':
    main()
