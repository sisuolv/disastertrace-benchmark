"""Real native inputs, separate program worker, and fresh-process pending recovery."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from disastertrace.monitoring_fixed_v1.aviation import FrozenFrequencyPredictor, TRUTH_TO_SUPPORT, visible_e_status
from disastertrace.monitoring_fixed_v1.contracts import EvidenceBundle, canonical
from disastertrace.monitoring_v1.dataset import load_session
from disastertrace.monitoring_v1.session_checkpoint import SessionCoordinator
from disastertrace.monitoring_v1.spool_backend import SpoolBackend, digest, publish

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
OUT = HERE / 'reports/real_pending_predictor_01'


def load(path):
    return json.loads(path.read_text())


def save(path, row):
    with path.open('x') as handle:
        json.dump(row, handle, indent=2, allow_nan=False)
        handle.write('\n')


def backend(out):
    return SpoolBackend(out / 'spool', load(out / 'BACKEND.json'), run_id='real-native-program-pending.v1')


def worker(out):
    request_path, = (out / 'spool').glob('*.request.json')
    request = load(request_path)
    began = time.perf_counter()
    bundle = EvidenceBundle.freeze(request['request'])
    predictor = FrozenFrequencyPredictor(load(out / 'BANK.json'))
    p = predictor.predict(bundle).value
    e = visible_e_status(bundle)
    reverse = {v: k for k, v in TRUTH_TO_SUPPORT.items()}
    raw = canonical({'fact_truth': reverse[e], 'probability': p})
    seconds = time.perf_counter() - began
    row = {'call_id': request['call_id'], 'request_sha256': digest(request_path),
           'execution_sha256': request['execution_sha256'], 'raw': raw,
           'raw_sha256': hashlib.sha256(raw.encode()).hexdigest(),
           'input_tokens': 0, 'output_tokens': 0, 'compute_seconds': seconds, 'ended_with_eos': True}
    key = request_path.name.removesuffix('.request.json')
    receipt_path = out / 'spool' / (key + '.worker.json')
    publish(receipt_path, {**row, 'origin': 'real native inputs; deterministic program; zero LLM calls', 'pid': os.getpid()})
    publish(out / 'spool' / (key + '.response.json'), {**row, 'schema': 'disastertrace.spool_response.v1',
            'worker_receipt_sha256': digest(receipt_path)})


def restore(out):
    session = SessionCoordinator.restore(load(out / 'PENDING_CHECKPOINT.json'), load(out / 'DATA.json'),
                                        load(out / 'BANK.json'), backend=backend(out))
    report = session.finish()
    assert session.done
    save(out / 'RESTORED_REPORT.json', report)
    save(out / 'RESTORED_CHECKPOINT.json', session.snapshot())


def main():
    from run_program_calendar import configs

    OUT.mkdir(exist_ok=False)
    (OUT / 'spool').mkdir()
    data = load_session(HERE / 'development_dataset_v2', stations=['KSFO', 'KOAK', 'KSJC'], hours=3, threshold=5000)
    bank = load(HERE / 'contracts/BANK.json')
    config = configs(3, 'base_bound_override')['P04_risk_shared']
    config.pop('execution_contract')
    config.update(forecast_call_cap=1, model_call_budget=1, executor_id='program_transport_engineering.v1')
    save(OUT / 'DATA.json', data)
    save(OUT / 'BANK.json', bank)
    save(OUT / 'BACKEND.json', {'model': 'no_model_deterministic_frequency_program', 'weights': 'none', 'tokenizer': 'none',
                              'adapter': 'native_program_transport.v1', 'generation': {}, 'runtime': 'CPU stdlib'})
    source = REPO / 'disastertrace-starter/src/disastertrace'
    for module in ('monitoring_v1', 'monitoring_fixed_v1'):
        shutil.copytree(source / module, OUT / 'source/disastertrace' / module, ignore=shutil.ignore_patterns('__pycache__'))
    (OUT / 'source/disastertrace/__init__.py').write_text('"""Frozen pending recovery package."""\n')
    shutil.copyfile(Path(__file__), OUT / 'source/execute_pending_recovery.py')
    save(OUT / 'SOURCE_MANIFEST.json', {str(p.relative_to(OUT)): digest(p) for p in (OUT / 'source').rglob('*.py')})
    session = SessionCoordinator(data, bank, config, backend=backend(OUT))
    first = session.step()
    checkpoint = session.snapshot()
    assert checkpoint['payload']['schema'] == 'disastertrace.session_inflight_predictor.v3'
    save(OUT / 'PENDING_CHECKPOINT.json', checkpoint)
    session.step()
    assert session.snapshot() == checkpoint
    save(OUT / 'PREFIX_REPORT.json', first)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(OUT / 'source'))
    for stage in ('worker', 'restore'):
        command = [sys.executable, str(OUT / 'source/execute_pending_recovery.py'), stage, '--out', str(OUT)]
        save(OUT / (stage + '.command.json'), {'command': command})
        with (OUT / (stage + '.log')).open('x') as handle:
            result = subprocess.run(command, env=env, stdout=handle, stderr=subprocess.STDOUT)
        save(OUT / (stage + '.exit.json'), {'exit_code': result.returncode})
        assert result.returncode == 0, stage
    reference = session.finish()
    recovered = load(OUT / 'RESTORED_REPORT.json')
    assert reference == recovered
    assert len(recovered['calls']) == 1 and len(recovered['snapshots']) == len(data['opportunities']) == 27
    assert len(list((OUT / 'spool').glob('*.request.json'))) == 1
    assert len([e for e in recovered['resource_events'] if e['event'] == 'reserve' and e['receipt_id'] == 'forecast-0']) == 1
    assert recovered['resource_reserved']['tokens'] == 0
    save(OUT / 'VALIDATION.json', {'passed': True, 'opportunities': 27, 'pending_requests': 1, 'backend_program_invocations': 1,
        'new_model_calls': 0, 'same_captured_response_cross_process_replay_equal': True,
        'pending_reservation_preserved': True, 'unresolved_poll_idempotent': True, 'original_dispatch_only': True,
        'native_source': '2025-02-03 Bay TAF/METAR verified captures',
        'interpretation': 'Real data and actual multi-process transport, but deterministic program reply; no LLM effectiveness claim.',
        'remaining_CP04b': ['pending source request', 'pending selector request', 'receipt/persistence boundary continuation']})
    print(json.dumps(load(OUT / 'VALIDATION.json')))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['main', 'worker', 'restore'])
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if args.mode == 'main':
        main()
    elif args.mode == 'worker':
        worker(args.out)
    else:
        restore(args.out)
