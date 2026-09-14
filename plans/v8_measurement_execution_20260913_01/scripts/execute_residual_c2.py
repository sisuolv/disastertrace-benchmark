"""Compile and replay real residual E graphs from actual controller checkpoints."""

import json
from dataclasses import asdict
from pathlib import Path

from disastertrace.monitoring_fixed_v1.admission import AdmissionEngine
from disastertrace.monitoring_fixed_v1.aviation import AviationProvider
from disastertrace.monitoring_fixed_v1.contracts import fingerprint
from disastertrace.monitoring_fixed_v1.support_bridge import compile_recipes, native_slot_support
from disastertrace.monitoring_v1.dataset import load_session
from disastertrace.monitoring_v1.reachability import Goal, Query, solve_joint, validate_witness
from disastertrace.monitoring_v1.resources import Cost
from disastertrace.monitoring_v1.session_checkpoint import SessionCoordinator, restore_session

from run_program_calendar import configs, load, save

HERE = Path(__file__).resolve().parents[1]
OUT = HERE / 'reports/residual_c2_01'


def acquire(context, data, qid, begin, end, owner):
    runtime, ledger, store = (context[k] for k in ('runtime', 'ledger', 'store'))
    catalog = {q['query_id']: q for q in data['query_catalog']}
    products = {q['query_id']: q for q in data['query_results']}
    rid = 'residual-source-' + fingerprint([qid, begin])[:24]
    upper = Cost(requests=1, bytes=2048, compute_ms=100)
    assert catalog[qid]['available_at'] <= begin and end == begin + catalog[qid]['latency_ms'] * 1000
    runtime.run([], until=begin)
    ledger.reserve(rid, upper, owner)
    value = products[qid]
    size = len(json.dumps(value, separators=(',', ':')).encode())
    actual = Cost(requests=1, bytes=size, compute_ms=100)
    ledger.settle(rid, actual)
    store.register(qid, value, owner=owner, receipt_id=rid)
    context['source_receipts'].append({'query_id': qid, 'asset_id': qid, 'payer': owner,
        'receipt_id': rid, 'started_at': begin, 'completed_at': end, 'source_status': value['status'],
        'bytes': size, 'timing_basis': 'declared_archive_query_latency'})
    runtime.run([], until=end)


def case(data, bank, provider, *, budget, late=False):
    settings = configs(3, 'base_bound_override')['P06_gs']
    settings.update(request_budget=budget, predict=False)
    session = SessionCoordinator(data, bank, settings)
    session.step()
    checkpoint = session.snapshot()
    context = restore_session(checkpoint, data, bank, session.config)
    deadline = sorted({o['cutoff'] for o in data['opportunities']})[1]
    selected = sorted([o for o in data['opportunities'] if o['cutoff'] == deadline and o['lead_hours'] == 1],
                      key=lambda o: o['target_id'])
    assert len(selected) == 3
    start = deadline - 1 if late else deadline - 600_000_000
    goals, qids, paid = [], set(), set(context['store'].assets)
    original_recipes = {}
    for opportunity in selected:
        bundle = provider.freeze(opportunity['opportunity_id'], 'all_registered')
        recipes = compile_recipes(bundle)
        original_recipes[opportunity['target_id']] = [sorted(r) for r in recipes]
        alternatives = tuple(frozenset(r - paid) for r in recipes)
        goals.append(Goal(opportunity['target_id'], deadline, alternatives))
        qids.update(q for recipe in alternatives for q in recipe)
    catalog = {r['query_id']: r for r in data['query_catalog']}
    queries = [Query(q, Cost(requests=1, bytes=2048, compute_ms=100), catalog[q]['available_at'],
                     catalog[q]['latency_ms'] * 1000) for q in sorted(qids)]
    remaining = budget - context['ledger'].spent.requests - context['ledger'].reserved.requests
    limits = {'requests': remaining, 'bytes': None, 'tokens': None, 'compute_ms': None}
    result = solve_joint(queries, goals, limits, concurrency=1, start=start)
    assert result.exact
    single = {g.target_id: solve_joint(queries, [g], limits, concurrency=1, start=start).lower_bound for g in goals}
    replays = []
    name = 'late' if late else 'remaining_' + str(remaining)
    folder = OUT / name
    folder.mkdir()
    save(folder / 'CHECKPOINT.json', checkpoint)
    for number, witness in enumerate(result.frontier):
        validate_witness(witness, queries, goals, limits, concurrency=1, start=start)
        replay = restore_session(checkpoint, data, bank, session.config)
        replay['runtime'].run([], until=start)
        for qid, begin, finish in sorted(witness.starts, key=lambda row: (row[1], row[0])):
            owners = [g.target_id for g in goals if any(qid in recipe for recipe in g.alternatives)]
            acquire(replay, data, qid, begin, finish, sorted(owners)[0])
        replay['runtime'].run([], until=deadline)
        support = {}
        for opportunity in selected:
            b = replay['runtime'].freeze_acquired(opportunity, deadline, replay['store'], replay['ledger'], replay['source_receipts'])
            support[opportunity['target_id']] = native_slot_support(b, at=deadline)['status']
        actual = tuple(sorted(t for t, status in support.items() if status in {'supported', 'refuted'}))
        assert actual == witness.resolved
        increment = replay['ledger'].spent.requests - context['ledger'].spent.requests
        assert increment == witness.cost.requests <= remaining
        journal = folder / ('witness_' + str(number) + '.jsonl')
        replay['runtime'].engine.write_journal(journal)
        assert AdmissionEngine.from_journal(journal).export() == replay['runtime'].export()
        replays.append({'witness': witness.to_dict(), 'E_from_native_paid_inputs': support,
                        'journal': journal.name, 'source_receipts': replay['source_receipts'],
                        'final_actual_cost': asdict(replay['ledger'].spent), 'engine_replay_equal': True})
    report = {'case': name, 'checkpoint_sha256': checkpoint['sha256'], 'clock': start, 'deadline': deadline,
              'total_source_budget': budget, 'already_spent': asdict(context['ledger'].spent),
              'remaining_source_budget': remaining, 'paid_assets_inherited': sorted(paid),
              'graph_queries': [dict(asdict(q), dependencies=sorted(q.dependencies)) for q in queries],
              'original_recipes_evaluator_only': original_recipes,
              'individual_reachability': single, 'joint_result': result.to_dict(), 'witness_replays': replays,
              'private_scope': False, 'concurrency': 1,
              'scope': 'real quiescent H15 report graph; query-count bottleneck, all other remaining resources verified feasible',
              'inflight_recovery_qualified': False, 'new_model_calls': 0}
    save(folder / 'REPORT.json', report)
    return report


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    dataset = HERE / 'development_dataset_v2'
    data = load_session(dataset, stations=['KSFO', 'KOAK', 'KSJC'], hours=3, threshold=1000)
    bank = load(HERE / 'contracts/BANK.json')
    provider = AviationProvider(dataset, bank)
    reports = [case(data, bank, provider, budget=3), case(data, bank, provider, budget=4),
               case(data, bank, provider, budget=4, late=True)]
    assert all(v == 1 for v in reports[0]['individual_reachability'].values())
    assert reports[0]['joint_result']['upper_bound'] < 3
    assert reports[1]['joint_result']['lower_bound'] == 3
    assert reports[2]['joint_result']['upper_bound'] == 0
    summary = {'cases': [{k: r[k] for k in ('case', 'already_spent', 'remaining_source_budget', 'individual_reachability')}
                        | {'joint_E_upper': r['joint_result']['upper_bound'], 'engine_witnesses': len(r['witness_replays'])}
                        for r in reports], 'all_replayed': True, 'new_model_calls': 0,
               'scientific_scope': 'C2 acquisition sufficiency mechanics on one real regional prefix; no F predictability or LLM gain claim'}
    save(OUT / 'SUMMARY.json', summary)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
