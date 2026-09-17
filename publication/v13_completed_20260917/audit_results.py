"""Read-only experiment audit; outputs new publication receipts only."""

import argparse
from collections import Counter
import datetime as dt
import hashlib
import json
import math
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(root):
    plans = root / "plans"
    b = plans / "v13_followup_20260916_01"
    s = plans / "v13_strong_baselines_20260916_01"
    m = plans / "v13_selector_execution_20260916_01"
    bindings = {}
    counts = {}
    all_rows = {}
    for label, folder, receipt, size, arms in [("B00", b / "B00", "RESULT.json", 60480, 5),
            ("B02", s, "FINAL_RESULT.json", 9504, 11), ("M01", m, "FINAL_RESULT.json", 864, 1)]:
        result = read(folder / receipt)
        assert result["passed"] is True
        path = folder / "ROWS.json"
        assert sha(path) == result["rows_sha256"]
        rows = read(path)
        assert len(rows) == size and len({r['arm'] for r in rows}) == arms
        assert len({(r['case'], r['arm'], r['opportunity_id']) for r in rows}) == size
        for row in rows:
            if row['outcome'] is None:
                assert row['loss'] is None
            else:
                assert row['outcome'] in (0, 1)
                assert math.isclose(row['loss'], (row['probability']-row['outcome'])**2, abs_tol=1e-12)
        counts[label] = size
        all_rows[label] = rows
        for name in (receipt, "ROWS.json"):
            p = folder / name
            bindings[str(p.relative_to(root))] = sha(p)
    assert len(list((b / "B00").glob("*/RESULT.json"))) == 168
    parents = [read(p) for p in (b / "C00").glob("*/C00_RESULT.json")]
    assert len(parents) == 12 and all(p['passed'] for p in parents)
    c = read(b / "C00/RESULT.json")
    assert c['passed'] and c['actual_GET_branches'] == 48
    audits = [read(p) for p in (m / "cases").glob("*/API_AUDIT.json")]
    assert len(audits) == 12 and all(a['passed'] for a in audits)
    requests = [r for a in audits for r in a['requests']]
    assert len(requests) == 288
    failed = [r for r in requests if r['failure_receipt']]
    assert len(failed) == 13
    assert all(not r['HTTP_intent'] and r['failure_receipt']['remote_execution'] == 'not_sent'
               and r['failure_receipt']['error_type'] == 'BlockingIOError' for r in failed)
    assert sum(r['HTTP_intent'] for r in requests) == 275
    assert sum(r['contract_valid'] and r['publication_verified'] for r in requests) == 275
    assert sum(a['provider_tokens_known'] for a in audits) == 1119368
    reserved = sum(a['reserved_resources']['tokens'] for a in audits)
    assert reserved == 432640
    model = {(r['case'], r['opportunity_id']): r for r in all_rows['M01']}
    comparisons = read(m / 'COMPARISONS.json')
    checked = 0
    for comp in comparisons['comparisons']:
        scope = comp['scope']
        candidates = {k: r for k, r in model.items() if scope == 'all' or r[scope] == comp['value']}
        refs = {(r['case'], r['opportunity_id']): r for r in all_rows['B02']
                if r['arm'] == comp['reference'] and (scope == 'all' or r[scope] == comp['value'])}
        assert candidates.keys() == refs.keys() and len(candidates) == comp['registered']
        gains, lo, hi = [], [], []
        for key, row in candidates.items():
            ref = refs[key]
            assert ref['outcome'] == row['outcome']
            if row['outcome'] is None:
                possible = [(ref['probability']-y)**2-(row['probability']-y)**2 for y in (0, 1)]
                lo.append(min(possible)); hi.append(max(possible))
            else:
                gain = ref['loss'] - row['loss']
                gains.append(gain); lo.append(gain); hi.append(gain)
        assert len(gains) == comp['settled']
        if gains:
            assert math.isclose(math.fsum(gains)/len(gains), comp['settled_mean_gain'], abs_tol=1e-12)
        for value, bound in zip((math.fsum(lo)/len(candidates), math.fsum(hi)/len(candidates)), comp['all_opportunity_missing_Y_bound']):
            assert math.isclose(value, bound, abs_tol=1e-12)
        checked += 1
    metrics = {}
    for arm in sorted({r['arm'] for r in all_rows['B02'] + all_rows['M01']}):
        rows = [r for r in all_rows['B02'] + all_rows['M01'] if r['arm'] == arm]
        settled = [r for r in rows if r['loss'] is not None]
        metrics[arm] = {'registered': len(rows), 'settled': len(settled),
                        'positive': sum(r['outcome'] == 1 for r in settled),
                        'brier': math.fsum(r['loss'] for r in settled)/len(settled)}
    assert metrics['LLM_SELECTOR_V2']['settled'] == 857 and metrics['LLM_SELECTOR_V2']['positive'] == 3
    assert math.isclose(metrics['LLM_SELECTOR_V2']['brier'], comparisons['model_metrics']['brier'], abs_tol=1e-12)
    for folder in (b, s):
        for path in (folder / 'runtime').glob('*/EXIT.json'):
            exit_info = read(path)
            assert all(v == 0 for k, v in exit_info.items() if k.endswith('exit') or k == 'exit_code')
    assert read(m / 'runtime/EXIT.json')['exit_code'] == 0
    preservation = read(b / 'PRESERVATION.json')
    assert preservation['frozen_source_changed'] == [] and preservation['prior_bindings_changed'] == []
    return {'passed': True, 'at': dt.datetime.now(dt.timezone.utc).isoformat(), 'method_row_counts': counts,
            'model_comparison_groups_recomputed': checked, 'method_metrics': metrics,
            'model_calls_registered': 288, 'HTTP_intents_and_valid_responses': 275,
            'pre_send_failures': 13, 'provider_tokens_known': 1119368, 'tokens_still_reserved': reserved,
            'C00_parents': 12, 'C00_branches': 48, 'files': bindings,
            'preservation': preservation, 'full_scientific_replay': False, 'new_model_calls': 0,
            'scope': 'original result hashes, row arithmetic, paired model comparisons, failure and resource accounting'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=REPO)
    parser.add_argument('--output', type=Path, default=HERE / 'RESULT_VALIDATION.json')
    args = parser.parse_args()
    result = audit(args.root)
    with args.output.open('x') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ['files', 'method_metrics']}))
