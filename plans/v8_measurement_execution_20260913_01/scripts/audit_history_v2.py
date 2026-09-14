"""Re-read original model captures; retain their requests and original results."""

import hashlib
import json
from collections import Counter
from pathlib import Path

from disastertrace.monitoring_fixed_v1.contracts import EvidenceBundle, fingerprint
from disastertrace.monitoring_fixed_v1.heads import parse_response
from disastertrace.monitoring_fixed_v1.support_bridge import native_slot_support
from disastertrace.monitoring_fixed_v1.taf_tasks import TafEvidenceTask, evaluate, score_answer

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1] / 'reports/history_impact_01'


def load(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(batch, prior_report):
    plan = load(batch / 'PLAN.json')
    for rel, value in plan['files'].items():
        assert digest(batch / rel) == value, rel
    old_rows = {r['call_id']: r for r in load(prior_report / 'RECORDS.json')}
    rows = []
    for worker, tasks in plan['workers'].items():
        for task in tasks:
            cid = task['call_id']
            paths = [batch / ('worker-' + worker) / (cid + '-' + suffix + '.json')
                     for suffix in ('request', 'response', 'commit')]
            request, response, commit = map(load, paths)
            assert commit['request_sha256'] == digest(paths[0])
            assert commit['response_sha256'] == digest(paths[1])
            assert fingerprint(request['messages']) == task['messages_sha256']
            assert response['raw_sha256'] == hashlib.sha256(response['raw'].encode()).hexdigest()
            assert response['raw'] == old_rows[cid]['raw']
            assert response['output_tokens'] == len(response['output_ids'])
            assert request['input_tokens'] == response['input_tokens'] == task['input_tokens']
            assert request['plan_sha256'] == response['plan_sha256'] == commit['plan_sha256'] == digest(batch / 'PLAN.json')
            assert request['bundle_hash'] == response['bundle_hash'] == commit['bundle_hash'] == task['bundle_hash']
            assert 0 < commit['completed_elapsed_us'] <= commit['persisted_elapsed_us']
            source = load(batch / 'policy' / (cid + '.json'))
            old = old_rows[cid]
            row = {'call_id': cid, 'head': task['head'], 'worker': worker,
                   'request_sha256': digest(paths[0]), 'response_sha256': digest(paths[1]),
                   'commit_sha256': digest(paths[2]), 'input_tokens': response['input_tokens'],
                   'output_tokens': response['output_tokens'], 'actual_seconds': response['seconds'],
                   'completed_elapsed_us': commit['completed_elapsed_us'],
                   'persisted_elapsed_us': commit['persisted_elapsed_us'],
                   'timely': task['logical_started_at'] + commit['persisted_elapsed_us'] <= task['logical_cutoff'],
                   'ended_with_eos': response['ended_with_eos'], 'status': 'unchanged',
                   'response_prompt_refabricated': False}
            if task.get('input_kind') == 'taf_task':
                item = TafEvidenceTask.freeze(source)
                assert item.task_hash == task['bundle_hash']
                updated = evaluate(item)['answer']
                result = score_answer(response['raw'], item)
                row.update(original_answer_reference=old['expected'], current_answer_reference=updated,
                           original_correct=old['correct'], corrected_correct=result['correct'],
                           status='unchanged' if old['expected'] == updated else 'affected',
                           identifiable_error_fields=[k for k, v in result.get('field_correct', {}).items() if not v],
                           cause_not_identified=['native_time_decoding', 'numeric_comparison', 'coverage_arithmetic'])
            else:
                item = EvidenceBundle.restore(source)
                assert item.bundle_hash == task['bundle_hash']
                parsed = parse_response(response['raw'], item, task['head'])
                support = native_slot_support(item)['status']
                expected = None if task['head'] == 'f_only' else support
                baseline = item.policy_view()['baseline']['forecast']['value']
                row.update(original_e_reference=old['expected_e'], current_e_reference=expected,
                           status='unchanged' if old['expected_e'] == expected else 'affected',
                           proposed_probability=None if parsed.forecast is None else parsed.forecast.value,
                           baseline_probability=baseline,
                           probability_equal_to_baseline=parsed.forecast is not None and parsed.forecast.value == baseline,
                           action_contract='E_only' if parsed.forecast is None else 'typed_auto_propose_override.v1')
            rows.append(row)
    assert len(rows) == plan['expected_calls']
    return {'batch': str(batch.relative_to(ROOT)), 'plan_sha256': digest(batch / 'PLAN.json'),
            'bound_files_checked': len(plan['files']), 'calls': len(rows),
            'impact_counts': dict(Counter(r['status'] for r in rows)),
            'timely': sum(r['timely'] for r in rows),
            'input_tokens': sum(r['input_tokens'] for r in rows),
            'output_tokens': sum(r['output_tokens'] for r in rows),
            'equal_probability_override_proposals': sum(r.get('probability_equal_to_baseline', False) for r in rows),
            'records': rows}


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    reports = []
    for phase, batch, report in [
        ('v7_followup_execution_20260913', 'heads_smoke_01', 'model_smoke_02'),
        ('v7_adaptive_execution_20260913', 'development_01', 'model_development_01')]:
        root = ROOT / 'plans' / phase
        reports.append(audit(root / 'gpu' / batch, root / 'reports' / report))
    value = {'schema': 'disastertrace.history_measurement_impact.v2', 'batches': reports,
             'total_existing_calls_audited': sum(r['calls'] for r in reports), 'new_model_calls': 0,
             'prior_raw_and_original_scores_preserved': True,
             'limits': ['Historical first-seen and calibration guarantees are not established.',
                        'Current parser labels are a derived audit, not a new model experiment.',
                        'The previous representation comparison changed multiple input factors.',
                        'These source/capture checks do not qualify all 16 hazards.']}
    (OUT / 'EXECUTION_IMPACT.json').write_text(json.dumps(value, indent=2) + '\n')
    print(json.dumps({k: v for k, v in value.items() if k != 'batches'}))
    print(json.dumps([{k: v for k, v in r.items() if k != 'records'} for r in reports], indent=2))


if __name__ == '__main__':
    main()
