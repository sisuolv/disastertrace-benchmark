"""Freeze the stronger-model comparison and one-factor time diagnostic."""

import hashlib
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from transformers import AutoTokenizer

from disastertrace.monitoring_fixed_v1.aviation import AviationProvider
from disastertrace.monitoring_fixed_v1.contracts import fingerprint
from disastertrace.monitoring_fixed_v1.heads import model_messages
from disastertrace.monitoring_fixed_v1.taf_tasks import TafEvidenceTask, evaluate
from disastertrace.monitoring_fixed_v1.time_representation import time_messages, transform

HERE = Path(__file__).resolve().parent
EXECUTION = HERE.parent
REPO = EXECUTION.parents[1]
OUT = HERE / 'large_diagnostic_02'


def load(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, row):
    with path.open('x') as f:
        json.dump(row, f, indent=2, allow_nan=False)
        f.write('\n')


def main():
    OUT.mkdir(exist_ok=False)
    (OUT / 'policy').mkdir()
    (OUT / 'evaluator').mkdir()
    prior_batch = REPO / 'plans/v7_adaptive_execution_20260913/gpu/development_01'
    prior = load(prior_batch / 'PLAN.json')
    large = load(HERE / 'LARGE_MODEL_FREEZE.json')
    models = {
        'qwen235b_fp8': {'name': large['model'], 'directory': large['destination'],
                       'files': [{'path': r['Path'], 'sha256': r['Sha256'], 'bytes': r['Size'], 'revision': r['Revision']}
                                 for r in large['files']], 'quantization': 'fp8',
                       'description': '235B total / 22B active MoE, Instruct-2507 FP8'},
        'qwen8b_control': {'name': 'Qwen/Qwen3-8B', 'directory': prior['model']['directory'],
                          'files': prior['model']['files'], 'quantization': None,
                          'description': 'fresh matched-input control; non-thinking BF16'}
    }
    tokenizer = {}
    for key, spec in models.items():
        for row in spec['files']:
            if 'safetensors' not in row['path']:
                path = Path(spec['directory']) / row['path']
                assert digest(path) == row['sha256'] and path.stat().st_size == row['bytes']
        tokenizer[key] = AutoTokenizer.from_pretrained(spec['directory'], local_files_only=True)
    tasks, references = [], []

    def add(payload, messages, *, kind, head, condition, identity, logical_start, cutoff, representation):
        cid = fingerprint([kind, head, condition, identity, representation])[:24]
        assert cid not in {r['call_id'] for r in tasks}
        token_data = {}
        for model, tok in tokenizer.items():
            encoded = tok.apply_chat_template(messages, tokenize=True, add_generation_prompt=True,
                                              enable_thinking=False)
            assert len(encoded) + 512 <= 16384, 'Do not truncate a task'
            token_data[model] = {'input_tokens': len(encoded), 'input_ids_sha256': fingerprint(encoded)}
        request = {'schema': 'disastertrace.large_diagnostic_request.v1', 'call_id': cid,
                   'messages': messages, 'input': payload}
        save(OUT / 'policy' / (cid + '.json'), request)
        tasks.append({'call_id': cid, 'input_kind': kind, 'head': head, 'condition': condition,
                      'identity': identity, 'representation': representation,
                      'messages_sha256': fingerprint(messages), 'logical_started_at': logical_start,
                      'logical_cutoff': cutoff, 'models': token_data})

    for worker_rows in prior['workers'].values():
        for row in worker_rows:
            if row.get('input_kind') != 'taf_task':
                continue
            item = TafEvidenceTask.freeze(load(prior_batch / 'policy' / (row['call_id'] + '.json')))
            assert item.task_hash == row['bundle_hash']
            assert transform(transform(item.view()), decode=True) == item.view()
            for encoding in ('epoch_us', 'iso_utc'):
                add(item.view(), time_messages(item, encoding), kind='taf_task', head=row['head'],
                    condition=item.view()['kind'], identity=item.task_hash, representation=encoding,
                    logical_start=row['logical_started_at'], cutoff=row['logical_cutoff'])
            references.append({'kind': 'taf_task', 'identity': item.task_hash, 'reference': evaluate(item),
                               'prior_call_id': row['call_id'], 'factor': 'reversible time encoding only'})
    assert len(tasks) == 72
    bank = load(EXECUTION / 'contracts/BANK.json')
    dataset = EXECUTION / 'development_dataset_v2'
    provider = AviationProvider(dataset, bank)
    cutoffs = sorted({o['cutoff'] for o in provider.opportunities.values()})
    selected = [o for o in provider.opportunities.values() if o['cutoff'] in {cutoffs[i] for i in (0, 6, 12, 18)}
                and o['lead_hours'] in (1, 3)]
    assert len(selected) == 48
    baseline_stream, dispatch_changes = [], []
    for opportunity in sorted(selected, key=lambda o: o['opportunity_id']):
        dispatch = opportunity['cutoff'] - 60_000_000
        initial = provider.freeze(opportunity['opportunity_id'], 'common_only', as_of=dispatch)
        final = provider.freeze(opportunity['opportunity_id'], 'common_only')
        if initial.base_hash != final.base_hash:
            dispatch_changes.append({'opportunity_id': opportunity['opportunity_id'],
                'dispatch_source': initial.policy_view()['baseline']['source_revision'],
                'cutoff_source': final.policy_view()['baseline']['source_revision']})
        times = {dispatch, opportunity['cutoff']}
        times.update(p['issued_at'] + 120_000_000 for p in provider.native_products
            if p['station'] == provider.targets[opportunity['target_id']]['entity']
            and dispatch < p['issued_at'] + 120_000_000 <= opportunity['cutoff'])
        previous = None
        for at in sorted(times):
            common = provider.freeze(opportunity['opportunity_id'], 'common_only', as_of=at)
            if common.base_hash != previous:
                baseline_stream.append({'opportunity_id': opportunity['opportunity_id'],
                    'as_of': at, 'bundle': common.to_dict()})
                previous = common.base_hash
        for condition in ('common_only', 'fixed_one', 'all_registered'):
            bundle = provider.freeze(opportunity['opportunity_id'], condition, as_of=dispatch)
            view = bundle.policy_view()
            assert max([view['baseline']['available_at']] + [a['completed_at'] for a in view['assets']]
                       + [r['completed_at'] for r in view['receipts']]) <= dispatch
            for head in ('e_only', 'f_only', 'joint'):
                add(bundle.to_dict(), model_messages(bundle, head), kind='bundle', head=head,
                    condition=condition, identity=bundle.bundle_hash, representation='full_bundle_with_fit_disclosure.v2',
                    logical_start=opportunity['cutoff'] - 60_000_000, cutoff=opportunity['cutoff'])
    assert len(tasks) == 504
    tasks.sort(key=lambda row: fingerprint(['schedule', row['call_id'], 20260913]))
    package = REPO / 'disastertrace-starter/src/disastertrace'
    for module in ('monitoring_v1', 'monitoring_fixed_v1'):
        shutil.copytree(package / module, OUT / 'source/disastertrace' / module,
                        ignore=shutil.ignore_patterns('__pycache__'))
    (OUT / 'source/disastertrace/__init__.py').write_text('"""Frozen large-model diagnostic package."""\n')
    for filename in ('large_worker.py',):
        shutil.copyfile(HERE / filename, OUT / 'source' / filename)
    save(OUT / 'evaluator/NATIVE_REFERENCES.json', references)
    save(OUT / 'evaluator/OPPORTUNITIES.json', selected)
    save(OUT / 'evaluator/BANK.json', bank)
    save(OUT / 'evaluator/OUTCOMES.json', load(dataset / 'private/OUTCOMES.json'))
    save(OUT / 'evaluator/COMMON_BASELINES.json', baseline_stream)
    save(OUT / 'evaluator/DISPATCH_IMPACT.json', dispatch_changes)
    canonical_outcomes = []
    selected_ids = {o['opportunity_id'] for o in selected}
    for threshold in (1000, 5000):
        path = EXECUTION / 'reports/program_calendar_02' / (str(threshold) + '__base_bound_override/OUTCOMES.json')
        canonical_outcomes.extend(r for r in load(path) if r['opportunity_id'] in selected_ids)
    assert len(canonical_outcomes) == len(selected_ids) == 48
    save(OUT / 'evaluator/CANONICAL_OUTCOMES.json', canonical_outcomes)
    save(OUT / 'EVALUATOR_MANIFEST.json', {str(p.relative_to(OUT)): digest(p)
          for p in (OUT / 'evaluator').glob('*.json')})
    save(OUT / 'PLAN.json', {'schema': 'disastertrace.large_model_fixed_input_diagnostic.v2',
         'frozen_at': datetime.now(timezone.utc).isoformat(), 'models': models,
         'model_order': ['qwen235b_fp8', 'qwen8b_control'], 'expected_benchmark_calls_per_model': 504,
         'compatibility_calls_per_model': 1, 'maximum_total_calls': 1010,
         'tasks': tasks, 'batch_size': 4, 'tensor_parallel_size': 4, 'max_concurrent_gpus': 4,
         'generation': {'temperature': 0.0, 'max_tokens': 512, 'seed': 20260913, 'enable_thinking': False},
         'engine': {'max_model_len': 16384, 'max_num_seqs': 4, 'gpu_memory_utilization': 0.90,
                    'enforce_eager': True, 'enable_prefix_caching': False, 'max_num_batched_tokens': 8192},
         'runtime_versions': {'vllm': '0.10.2', 'torch': '2.8.0', 'transformers': '4.55.2'},
         'retries': 0, 'training': False, 'model_judge': False, 'independent_confirmation': False,
         'adaptive_LLM_comparison': False, 'tools': [], 'online_inference': False,
         'selection': 'Every six hours, both registered thresholds, 1h/3h leads, all three sites; no outcome filtering.',
         'model_comparison_limit': 'Architecture, tuning and FP8 differ; this is a stronger-model comparison, not an isolated parameter-count effect.',
         'files': {str(p.relative_to(OUT)): digest(p) for parent in ('policy', 'source')
                   for p in (OUT / parent).rglob('*') if p.is_file()},
         'dataset_build_sha256': digest(dataset / 'BUILD.json'),
         'evaluator_manifest_sha256': digest(OUT / 'EVALUATOR_MANIFEST.json'),
         'dispatch_rule': 'Current native source and completed evidence at cutoff minus 60s; common updates through cutoff remain active for every method.',
         'adoption_rule': 'typed_auto_propose.v1, base_bound_override; equality is not FOLLOW',
         'replaces_unlaunched_plan_sha256': digest(HERE / 'large_diagnostic_01/PLAN.json'),
         'evaluator_files_not_read_by_worker': True})
    save(OUT / 'CPU_PREFLIGHT.json', {'tasks_per_model': len(tasks),
         'native_time_pair_equivalence': True, 'all_inputs_fit_both_model_contexts': True,
         'all_inputs_visible_at_dispatch': True, 'dispatch_baselines_differ_from_cutoff': len(dispatch_changes),
         'counts': dict(Counter(t['input_kind'] + ':' + t['head'] for t in tasks)),
         'new_model_calls': 0, 'plan_sha256': digest(OUT / 'PLAN.json')})
    print(json.dumps(load(OUT / 'CPU_PREFLIGHT.json'), indent=2))


if __name__ == '__main__':
    main()
