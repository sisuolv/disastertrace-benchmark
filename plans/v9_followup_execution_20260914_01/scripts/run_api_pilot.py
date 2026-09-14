"""Freeze and run new continuous historical sessions, with explicit COPY controls."""

import argparse
import concurrent.futures
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from collections import defaultdict

from disastertrace.monitoring_fixed_v1.admission import AdmissionEngine, score_admitted
from disastertrace.monitoring_fixed_v1.outcomes import ComparisonContract, OutcomeRegistry, experiment_spec
from disastertrace.monitoring_fixed_v1.aviation import typed_target
from disastertrace.monitoring_v1.api_capture import ApiBudget, capture
from disastertrace.monitoring_v1.dataset import load_session
from disastertrace.monitoring_v1.execution import bind_execution
from disastertrace.monitoring_v1.production import ProductionSpoolBackend
from disastertrace.monitoring_v1.policies import run_session
from disastertrace.monitoring_v1.session_checkpoint import SessionCoordinator
from disastertrace.monitoring_v1.spool_backend import digest, publish, read
from disastertrace.monitoring_v1.targets import canonical_hash, utc_us

ROOT = Path(os.environ.get('DISASTERTRACE_FOLLOWUP_ROOT', Path(__file__).resolve().parents[1]))
REPO = ROOT.parents[1]
OUT = ROOT / 'api_pilot_01'
MODELS = ['deepseek-flash', 'deepseek-v4-pro']
REGIONS = {'new_york': ['KJFK', 'KLGA', 'KEWR'], 'chicago': ['KORD', 'KMDW', 'KRFD'],
           'denver': ['KDEN', 'KBJC', 'KAPA']}
DAYS = ['2025-01-06', '2025-01-10']


def helper():
    p = OUT / 'source/program_reference.py'
    spec = importlib.util.spec_from_file_location('pilot_program_reference', p)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def backend_for(case, arm):
    spec = read(case / 'BACKENDS.json').get(arm)
    if spec is None:
        return None
    return ProductionSpoolBackend(case / arm / 'spool', spec['contract'], run_id=spec['run_id'],
                                  bound_files=read(case / 'BOUND_FILES.json'))


def service(backend, checkpoint, case, arm):
    payload = checkpoint['payload']
    pending = payload.get('pending_predictor') or payload.get('pending_selector')
    if pending is None:
        return
    call_id = pending['call_id']
    key = backend._key(call_id)
    backend.claim_ready(call_id, worker_id='single_original_api_worker.v1')
    request_path = backend.directory / (key + '.request.json')
    request = read(request_path)
    try:
        raw, details = capture(request['messages'], backend.execution_contract['model'],
             case.name + '/' + arm + '/' + call_id, case / arm / 'captures' / key,
             ApiBudget(OUT / 'BUDGET.json'), max_tokens=512)
        worker = {'call_id': call_id, 'request_sha256': digest(request_path),
             'execution_sha256': request['execution_sha256'], 'raw': raw,
             'raw_sha256': hashlib.sha256(raw.encode()).hexdigest(),
             'input_tokens': details['input_tokens'], 'output_tokens': details['output_tokens'],
             'compute_seconds': details['seconds'], 'ended_with_eos': details['ended_with_eos'],
             'provider_metadata': details}
        worker_path = backend.directory / (key + '.worker.json')
        publish(worker_path, worker)
        fields = ['call_id','request_sha256','execution_sha256','raw','raw_sha256',
                  'input_tokens','output_tokens','compute_seconds','ended_with_eos']
        publish(backend.directory / (key + '.response.json'),
                {'schema': 'disastertrace.spool_response.v1', **{k: worker[k] for k in fields},
                 'worker_receipt_sha256': digest(worker_path)})
    except Exception as exc:
        publish(backend.directory / (key + '.failure.json'), {'call_id': call_id,
            'request_sha256': digest(request_path), 'execution_sha256': request['execution_sha256'],
            'error_type': type(exc).__name__, 'logical_retry': False})


def run_arm(case, arm):
    folder = case / arm
    publish(folder / 'RUN_CLAIM.json', {'started_at': dt.datetime.now(dt.timezone.utc).isoformat()})
    for name, sha in read(case / 'FREEZE.json')['files'].items():
        assert digest(Path(name)) == sha, 'Frozen pilot input changed'
    data, bank, config = read(case / 'DATA.json'), read(case / 'BANK.json'), read(case / 'CONFIGS.json')[arm]
    backend = backend_for(case, arm)
    if backend is None:
        report = run_session(data, bank, config)
    else:
        session = SessionCoordinator(data, bank, config, backend=backend)
        index = 0
        while not session.done:
            session.step()
            checkpoint = session.snapshot()
            session.persist(folder / 'checkpoints' / f'{index:05d}.json')
            service(backend, checkpoint, case, arm)
            index += 1
            if index > 160:
                raise RuntimeError('Pilot exceeded frozen step ceiling')
        report = session.report
    publish(folder / 'REPORT.json', report)
    restored = AdmissionEngine.restore(report['event_replay'])
    restored.write_journal(folder / 'admission.jsonl')
    assert len(report['snapshots']) == len(data['opportunities']) == 72
    comparison = read(case / 'COMPARISON.json')['payload']
    scores = score_admitted(read(case / 'OUTCOMES.json'), {arm: folder / 'admission.jsonl'},
        comparison=ComparisonContract(comparison['invariants'], comparison['allowed_interventions']))
    publish(folder / 'SCORES.json', scores)
    publish(folder / 'COMPLETE.json', {'calls': len(report['calls']), 'model_calls': report['actual_model_calls'],
                                     'snapshots': len(report['snapshots']), 'canonical_scoring': True})


def prepare_case(region, day, threshold, *, bank_path=None):
    ref = helper()
    case = OUT / (region + '__' + day + '__' + str(threshold))
    case.mkdir()
    dataset = ROOT.parent / 'v8_measurement_execution_20260913_01/regional_calendar_extension_01' / region / 'dataset_v2'
    data = load_session(dataset, stations=REGIONS[region], threshold=threshold)
    start = utc_us(day + 'T00:00:00Z')
    data['opportunities'] = [r for r in data['opportunities'] if start <= r['cutoff'] < start + 86_400_000_000 and r['lead_hours'] == 1]
    tids = {r['target_id'] for r in data['opportunities']}
    oids = {r['opportunity_id'] for r in data['opportunities']}
    for name in ['targets', 'baseline_candidates', 'baseline_withdrawals']:
        data[name] = [r for r in data[name] if r['target_id'] in tids]
    data['e_f_pairs'] = [r for r in data['e_f_pairs'] if r['opportunity_id'] in oids]
    bank = read(bank_path or ROOT / 'reports/regional_baselines_01' / region / 'BANK.json')
    publish(case / 'DATA.json', data)
    publish(case / 'BANK.json', bank)
    ref.outcomes(dataset, data, case)
    registry = OutcomeRegistry([typed_target(t) for t in data['targets']])
    for row in read(case / 'OUTCOME_REGISTRY.json')['payload']['records']:
        registry.register({**row, 'resolution_policy': 'h15_routine_archive.v1'})
    # These freshly generated files are still preparation inputs, before FREEZE exists.
    (case / 'OUTCOME_REGISTRY.json').write_text(json.dumps(registry.export(), indent=2)+'\n')
    outcome_rows = [{**r, 'resolution_policy': 'h15_routine_archive.v1'} for r in read(case/'OUTCOMES.json')]
    (case / 'OUTCOMES.json').write_text(json.dumps(outcome_rows, indent=2)+'\n')
    base = ref.configs(24, 'base_bound_override')['P03_batch_shared']
    base.pop('execution_contract')
    base.update(request_budget=48, forecast_call_cap=72, per_tick_forecast_cap=3,
        model_call_budget=96, input_token_cap=32768, output_token_cap=512,
        token_cap=96*33280, compute_ms_cap=96*120000+4800,
        execution_mode='production_bound_v1', pending_timing_policy='lifecycle_wall_v1',
        isolation_mode='actual_cost_clock', failure_continuation_policy='skip_failed_call_continue_v1',
        predictor_kind='program', program_prediction='frequency_mapping')
    arms = {'follow': dict(base, acquire=False, predict=False),
            'copy_current': dict(base, acquire=False, program_prediction='copy_current_state'),
            'copy_baseline': dict(base, acquire=False, program_prediction='copy_latest_baseline'),
            'batch_program': dict(base), 'risk_program': dict(base, selector_kind='risk'),
            'coverage_program': dict(base, selector_kind='coverage')}
    for alloc in ['fixed_quota', 'global_budget']:
        for auth in ['target_private', 'session_shared']:
            arms[alloc + '__' + auth] = dict(base, selector_kind='round_robin', allocation_mode=alloc, authorization_mode=auth)
    specs = {}
    for model in MODELS:
        for role in ['batch_predictor', 'llm_selector_program']:
            arm = model + '__' + role
            arms[arm] = dict(base, predictor_kind='llm' if role == 'batch_predictor' else 'program',
                            selector_kind='batch_complete' if role == 'batch_predictor' else 'llm')
            specs[arm] = {'run_id': case.name + '/' + arm, 'contract': {
                'model': model, 'weights': 'provider managed; exact weight hash unavailable',
                'tokenizer': 'provider managed; conservatively bounded input, actual usage captured',
                'adapter': 'api_capture.v1', 'generation': {'thinking': 'disabled', 'max_tokens':512, 'temperature':0},
                'runtime': {'endpoint':'https://api.deepseek.com', 'server_compute':'unknown',
                            'pricing_sha256': digest(OUT/'PRICING.html')}}}
    for arm in arms:
        for sub in ['spool', 'captures', 'checkpoints']:
            (case / arm / sub).mkdir(parents=True, exist_ok=False)
    publish(case / 'BACKENDS.json', specs)
    bound = {str(p): digest(p) for p in (OUT / 'source').rglob('*.py')}
    for p in [case/'DATA.json', case/'BANK.json', case/'OUTCOMES.json', case/'OUTCOME_REGISTRY.json',
              case/'BACKENDS.json', OUT/'PRICING.html']:
        bound[str(p)] = digest(p)
    publish(case / 'BOUND_FILES.json', bound)
    arms = {a: bind_execution(c, backend_for(case, a)) for a, c in arms.items()}
    allowed = defaultdict(list)
    invariants = None
    for config in arms.values():
        spec = experiment_spec(data, bank, config)
        if invariants is None:
            invariants = spec['invariants']
        assert invariants == spec['invariants']
        for key, value in spec['interventions'].items():
            if value not in allowed[key]:
                allowed[key].append(value)
    publish(case / 'CONFIGS.json', arms)
    publish(case / 'COMPARISON.json', ComparisonContract(invariants, allowed).export())
    files = {**bound, **{str(case/n): digest(case/n) for n in ['CONFIGS.json','COMPARISON.json','BOUND_FILES.json']}}
    publish(case / 'FREEZE.json', {'files': files, 'opportunities':72, 'model_calls_ceiling':192,
             'scope':'exposed multi-region development; base-bound protocol only; no independent confirmation'})
    return case, list(arms)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', type=Path)
    parser.add_argument('--arm')
    args = parser.parse_args()
    if args.case:
        run_arm(args.case, args.arm)
        return
    OUT.mkdir(exist_ok=False)
    for module in ['monitoring_v1','monitoring_fixed_v1']:
        shutil.copytree(REPO/'disastertrace-starter/src/disastertrace'/module,
                        OUT/'source/disastertrace'/module, ignore=shutil.ignore_patterns('__pycache__'))
    (OUT/'source/disastertrace/__init__.py').write_text('"""Frozen API pilot implementation."""\n')
    shutil.copyfile(Path(__file__), OUT/'source/run_api_pilot.py')
    shutil.copyfile(ROOT.parent/'v8_measurement_execution_20260913_01/scripts/run_program_calendar.py', OUT/'source/program_reference.py')
    shutil.copyfile(ROOT/'model_catalog/probe_01/deepseek_pricing.body', OUT/'PRICING.html')
    publish(OUT/'BUDGET.json', {'limit_nanodollars':12_000_000_000,'max_calls':2304,'calls':{}})
    publish(OUT/'PREREGISTRATION.json', {'regions':REGIONS,'days':DAYS,'thresholds':[1000,5000],
        'models':MODELS,'max_api_calls':2304,'fee_upper_usd':12,'http_concurrency':4,'gpu_cards':0,
        'selection':'first and final weekday of registered Jan6-12 calendar; all sites and hourly cutoffs',
        'training':'separate purged December2024 fit/calibration', 'retries':0,'confirmation_opened':False,
        'scope':'base_bound continuous development; both thresholds share underlying station reports',
        'timing':'actual API delivery; declared native-source/program/persistence replay latencies',
        'comparison_limits':'not physical deployment cost parity or independent-process generalization'})
    cases = [prepare_case(r, day, threshold) for r in REGIONS for day in DAYS for threshold in [1000,5000]]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(OUT/'source'), DISASTERTRACE_FOLLOWUP_ROOT=str(ROOT))

    def execute(item):
        case, arm = item
        cmd = [sys.executable,str(OUT/'source/run_api_pilot.py'),'--case',str(case),'--arm',arm]
        with (case/arm/'run.log').open('x') as log:
            result = subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT)
        row={'case':case.name,'arm':arm,'exit_code':result.returncode}
        publish(case/arm/'EXIT.json',row)
        return row

    program = [(c,a) for c,arms in cases for a in arms if not a.startswith('deepseek')]
    models = [(c,a) for c,arms in cases for a in arms if a.startswith('deepseek')]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        program_rows=list(pool.map(execute,program))
    publish(OUT/'PROGRAM_COMPLETE.json',program_rows)
    assert all(r['exit_code']==0 for r in program_rows), 'Program gate failed; no API calls'
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        model_rows=list(pool.map(execute,models))
    publish(OUT/'COMPLETE.json',{'programs':program_rows,'models':model_rows,
        'all_completed':all(r['exit_code']==0 for r in model_rows), 'budget':read(OUT/'BUDGET.json')})
    print(json.dumps({'cases':len(cases),'model_sessions':len(model_rows),'failures':sum(r['exit_code']!=0 for r in model_rows)}))


if __name__ == '__main__':
    main()
