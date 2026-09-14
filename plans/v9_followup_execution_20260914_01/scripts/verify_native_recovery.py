"""Separate CPU processes exercise cumulative waits on existing real H15 inputs."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'disastertrace-starter/tests'))
from test_monitoring_pending_predictor import PendingFixtureBackend, reply
from test_monitoring_pending_selector import SelectorFixtureBackend, reply as selector_reply
from test_monitoring_pending_source import PendingSource, reply as source_reply
from disastertrace.monitoring_v1.session_checkpoint import SessionCoordinator


def read(p):
    return json.loads(p.read_text())


def save(p, d):
    with p.open('x') as f:
        json.dump(d, f, indent=2, allow_nan=False)
        f.write('\n')


def step(folder, role, stage):
    spec = read(folder / 'SPEC.json')
    data, bank, config = spec['data'], spec['bank'], spec['config']
    backend = None if role == 'source' else (SelectorFixtureBackend if role == 'selector' else PendingFixtureBackend)(folder)
    source = PendingSource(folder, data['query_results']) if role == 'source' else None
    if stage == 0:
        session = SessionCoordinator(data, bank, config, backend=backend, source_backend=source)
    else:
        session = SessionCoordinator.restore(read(folder / f'checkpoint_{stage-1}.json'), data, bank,
                                             backend=backend, source_backend=source)
    if stage == 3:
        if role == 'source':
            source_reply(folder, data, session)
        elif role == 'selector':
            selector_reply(folder)
        else:
            reply(folder)
    report = session.step()
    save(folder / f'checkpoint_{stage}.json', session.snapshot())
    if stage == 3:
        assert session.done
        save(folder / 'REPORT.json', report)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--role')
    parser.add_argument('--stage', type=int)
    parser.add_argument('--case-name', default='native_recovery_01')
    parser.add_argument('--roles', nargs='+', default=['predictor', 'selector', 'source'])
    args = parser.parse_args()
    out = ROOT / 'reports' / args.case_name
    if args.role:
        step(out / args.role, args.role, args.stage)
        return
    out.mkdir(exist_ok=False)
    prior = REPO / 'plans/v9_integration_execution_20260914_01/reports/copy_controls_01/5000__base_bound_override'
    data, bank = read(prior / 'DATA.json'), read(prior / 'BANK.json')
    cutoff = min(r['cutoff'] for r in data['opportunities'])
    data['opportunities'] = [r for r in data['opportunities'] if r['cutoff'] == cutoff]
    tids = {r['target_id'] for r in data['opportunities']}
    oids = {r['opportunity_id'] for r in data['opportunities']}
    for name in ['targets', 'baseline_candidates', 'baseline_withdrawals']:
        data[name] = [r for r in data.get(name, []) if r['target_id'] in tids]
    data['e_f_pairs'] = [r for r in data['e_f_pairs'] if r['opportunity_id'] in oids]
    base = next(iter(read(prior / 'CONFIGS.json').values()))
    base.pop('execution_contract', None)
    base.update(predictor_kind='llm', program_prediction='frequency_mapping', execution_mode='test_callback_v1',
                pending_timing_policy='lifecycle_wall_v1', isolation_mode='actual_cost_clock',
                forecast_call_cap=1, model_call_budget=2, per_tick_forecast_cap=1,
                acquire=False, predict=True, selector_kind='round_robin')
    rows = []
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(REPO / 'disastertrace-starter/src'))
    for role in args.roles:
        folder = out / role
        folder.mkdir()
        config = dict(base)
        if role == 'selector':
            config.update(selector_kind='llm')
        if role == 'source':
            config.update(acquire=True, predict=False, request_budget=1, predictor_kind='program')
        save(folder / 'SPEC.json', {'data': data, 'bank': bank, 'config': config})
        for stage in range(4):
            cmd = [sys.executable, str(Path(__file__).resolve()), '--role', role, '--stage', str(stage),
                   '--case-name', args.case_name]
            with (folder / f'stage_{stage}.log').open('x') as log:
                result = subprocess.run(cmd, env=env, stdout=log, stderr=subprocess.STDOUT)
            save(folder / f'stage_{stage}.exit.json', {'exit_code': result.returncode})
            if result.returncode:
                raise RuntimeError(f'{role} stage {stage} failed; original records retained')
            if stage < 3:
                time.sleep(0.15)
        checkpoints = [read(folder / f'checkpoint_{s}.json') for s in range(4)]
        events = checkpoints[-1]['payload']['ledger']['events']
        timing = [r for r in events if r['event'] == 'execution_timing']
        first_id = timing[0]['receipt_id']
        matching = [r for r in timing if r['receipt_id'] == first_id]
        assert len([r for r in matching if r['phase'] == 'dispatch']) == 1
        assert len([r for r in matching if r['phase'] == 'poll']) == 3
        elapsed = matching[-1]['timing']['elapsed_us']
        assert elapsed >= 450_000
        report = read(folder / 'REPORT.json')
        actual = report[{'source': 'source_receipts', 'selector': 'selector_calls', 'predictor': 'calls'}[role]][0]
        assert actual['completed_at'] - actual['started_at'] >= elapsed
        assert all(not p['payload']['ledger']['spent']['tokens'] for p in checkpoints[:3])
        rows.append({'role': role, 'processes': 4, 'dispatches': 1, 'polls': 3, 'elapsed_us': elapsed,
                     'snapshots': len(report['snapshots']), 'compute_ms': report['resource_spent']['compute_ms']})
    save(out / 'VALIDATION.json', {'cases': rows, 'real_native_inputs': True, 'model_calls': 0,
          'response_origin': 'synthetic transport response / copied actual native source for engineering only',
          'claim': 'serial local recovery and cumulative delivery timing; not external exactly-once',
          'input_sha256': hashlib.sha256((prior / 'DATA.json').read_bytes()).hexdigest()})
    print(json.dumps(rows))


if __name__ == '__main__':
    main()
