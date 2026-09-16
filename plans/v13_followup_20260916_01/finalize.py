"""Bounded, event-driven completion receipts; never launch or retry experiments."""
import argparse
import datetime as dt
import hashlib
import itertools
import json
import math
import os
import time
from collections import Counter, defaultdict
from pathlib import Path

from b00 import RUN, OUT as B00, ARMS, now
from disastertrace.monitoring_v1.spool_backend import digest, publish, read


def metrics(rows):
    settled = [r for r in rows if r["loss"] is not None]
    positive = [r for r in settled if r["outcome"] == 1]
    negative = [r for r in settled if r["outcome"] == 0]
    return {"registered": len(rows), "settled": len(settled), "missing": len(rows)-len(settled),
        "positive": len(positive), "brier": math.fsum(r["loss"] for r in settled)/len(settled) if settled else None,
        "positive_brier": math.fsum(r["loss"] for r in positive)/len(positive) if positive else None,
        "negative_brier": math.fsum(r["loss"] for r in negative)/len(negative) if negative else None,
        "e_statuses": dict(Counter(r.get("e_status") or "not_recorded" for r in rows))}


def paired(rows, left, right, *, method_key="arm"):
    maps = {a: {} for a in (left, right)}
    for row in rows:
        arm = row[method_key]
        if arm not in maps:
            continue
        key = (row["case"], row["opportunity_id"])
        if key in maps[arm]:
            raise ValueError("Duplicate method/opportunity")
        maps[arm][key] = row
    if maps[left].keys() != maps[right].keys() or not maps[left]:
        raise ValueError("Paired outer denominator differs or is empty")
    gains, pos, neg, lower, upper = [], [], [], [], []
    for key, a in maps[left].items():
        b = maps[right][key]
        if a["outcome"] != b["outcome"]:
            raise ValueError("Methods use different result masks")
        if a["outcome"] is None:
            alternatives = [(a["probability"]-y)**2-(b["probability"]-y)**2 for y in (0, 1)]
            lower.append(min(alternatives)); upper.append(max(alternatives))
        else:
            gain = a["loss"] - b["loss"]
            gains.append(gain); lower.append(gain); upper.append(gain)
            (pos if a["outcome"] == 1 else neg).append(gain)
    total = len(maps[left])
    return {"reference": left, "candidate": right, "registered": total, "settled": len(gains),
        "missing": total-len(gains), "gain_positive_is_better": True,
        "settled_mean_gain": math.fsum(gains)/len(gains) if gains else None,
        "positive_mean_gain": math.fsum(pos)/len(pos) if pos else None,
        "negative_mean_gain": math.fsum(neg)/len(neg) if neg else None,
        "all_opportunity_missing_Y_bound": [math.fsum(lower)/total, math.fsum(upper)/total],
        "bound_assumption": "binary Y, method-independent mask, observed predictions; no missing-at-random assumption"}


def summarize_b00():
    reg = read(B00 / "REGISTRATION.json")
    expected = {r["case"] for r in reg["cases"]}
    shards = [read(B00 / f"SHARD_{i}.json") for i in range(3)]
    attempts = [r for s in shards for r in s["results"]]
    names = [r["case"] for r in attempts]
    complete = len(names) == len(expected) and set(names) == expected and all(r["passed"] for r in attempts)
    result = {"passed": complete, "registered_cases": len(expected), "completed_cases": sum(r["passed"] for r in attempts),
        "registered_trajectories": 840, "registered_opportunities": 12096, "registered_method_rows": 60480,
        "missing_cases": sorted(expected-set(names)), "failed_cases": [r for r in attempts if not r["passed"]],
        "confirmation_opened": False, "model_calls": 0, "new_fitting": 0, "finished_at": now()}
    if not complete:
        publish(B00 / "RESULT.json", result)
        return result
    rows = []
    for case in reg["cases"]:
        p = B00 / case["case"]
        receipt = read(p / "RESULT.json")
        if digest(p / "ROWS.json") != receipt["rows_sha256"]:
            raise ValueError("Completed case row hash differs")
        part = read(p / "ROWS.json")
        roster = set(read(p / "ROSTER.json"))
        actual = [(r["arm"], r["opportunity_id"]) for r in part]
        if len(actual) != 360 or set(actual) != set(itertools.product(ARMS, roster)):
            raise ValueError("Full registered method/opportunity matrix differs")
        rows.extend(part)
    if len(rows) != 60480:
        raise ValueError("Full calendar denominator differs")
    groups = defaultdict(list)
    for r in rows:
        for dimension, value in (("all", "all"), ("week", r["week"]), ("region", r["region"]),
                                 ("date", r["date"])):
            groups[(r["threshold"], dimension, value, r["arm"])].append(r)
    scores = {"__".join(map(str,k)): metrics(v) for k,v in groups.items()}
    contrasts = [("F_BASE_ONLY", "B11_BATCH"), ("F_BASE_ONLY", "B11_COVERAGE"),
                 ("B11_BATCH", "B11_COVERAGE"), ("FOLLOW", "F_BASE_ONLY"), ("F_COMMON", "F_BASE_ONLY")]
    comparisons = []
    for threshold in (1000,5000):
        subset = [r for r in rows if r["threshold"] == threshold]
        for left,right in contrasts:
            comparisons.append({"threshold": threshold, "scope": "all", "same_predictor": (left,right) in contrasts[:3],
                                **paired(subset,left,right)})
        for week in sorted({r["week"] for r in subset}):
            for left,right in contrasts[:3]:
                comparisons.append({"threshold":threshold,"scope":week,"same_predictor":True,
                                    **paired([r for r in subset if r["week"]==week],left,right)})
    publish(B00 / "ROWS.json", rows)
    publish(B00 / "METRICS.json", scores)
    publish(B00 / "PAIRED_COMPARISONS.json", comparisons)
    result.update(trajectories=840, method_rows=len(rows), rows_sha256=digest(B00 / "ROWS.json"),
                  global_week_blocks=4, independent_process_count=None,
                  uncertainty="Four exposed week blocks; no independent confirmation or strong significance claim")
    publish(B00 / "RESULT.json", result)
    return result


def summarize_c00():
    folder = RUN / "C00"
    result = read(folder / "RESULT.json")
    rows, attempted, aliases = [], 0, 0
    for parent in result["parents"]:
        attempted += sum(b.get("attempted",False) for b in parent.get("branches",[]))
        aliases += sum("alias_of" in b for b in parent.get("branches",[]))
        if parent["passed"]:
            part = read(folder / parent["case"] / "RESIDUAL_ROWS.json")
            if len(part) != parent["remaining_opportunities"]*4:
                raise ValueError("C00 residual outer denominator differs")
            rows.extend(part)
    comparisons = [paired(rows,a,b,method_key="rule") for a,b in itertools.combinations(
        ["none","first_new","second_new","all_new"],2)] if rows else []
    summary = {"passed":result["passed"],"registered_parents":12,"qualified_parents":sum(r["passed"] for r in result["parents"]),
        "registered_GET_rules":48,"executed_unique_branches":attempted,"explicit_aliases":aliases,
        "residual_method_rows":len(rows),"comparisons":comparisons,
        "all_parent_effect_claim_allowed":result["passed"],
        "source_state_strata": "not inferred from dates; inspect legal checkpoints, source receipts and baseline products",
        "PROCESS_and_WAIT": "not executed in this GET batch"}
    publish(folder / "ANALYSIS.json", summary)
    return summary


def snapshot():
    reg = read(B00 / "REGISTRATION.json")
    completed, failed, stopped = 0, 0, 0
    for row in reg["cases"]:
        case = B00 / row["case"]
        p = case / "RESULT.json"
        if p.exists():
            r = read(p); completed += r["passed"]; failed += not r["passed"]
        stopped += sum((case/a/"STOP.json").exists() for a in ARMS)
    return {"at":now(),"B00":{"registered_cases":168,"verified_cases":completed,"failed_cases":failed,
        "terminal_arm_files":stopped,"registered_arms":840,"summary_ready":(B00/'RESULT.json').exists()},
        "C00_result_ready":(RUN/'C00/RESULT.json').exists(),"M00_result_ready":(RUN/'M00/RESULT.json').exists(),
        "confirmation_opened":False}


def write_status(value):
    p = RUN / "STATUS.json"
    temp = p.with_suffix(".tmp")
    temp.write_text(json.dumps(value,indent=2,sort_keys=True)+"\n")
    os.replace(temp,p)


def closeout():
    b = read(B00 / "RESULT.json") if (B00/'RESULT.json').exists() else summarize_b00()
    c = read(RUN/'C00/ANALYSIS.json') if (RUN/'C00/ANALYSIS.json').exists() else summarize_c00()
    m = read(RUN/'M00/RESULT.json')
    a = read(RUN/'AUTHORIZATION.json')
    changed = [p for p,sha in a['prior_bindings'].items() if digest(Path(p))!=sha]
    source_changed = [p for p,sha in a['source_files'].items() if digest(Path(p))!=sha]
    index = Path('/mnt/afs/260010168/extreme_weather_benchmark/github_review/disastertrace-benchmark/.git/worktrees/disastertrace-next/index')
    preservation = {'prior_bindings_changed':changed,'frozen_source_changed':source_changed,
        'index_unchanged':digest(index)==a['git_index_sha256'],
        'scope':'prior final receipts/proposals and375frozen source files; not a raw archive rehash'}
    publish(RUN/'PRESERVATION.json',preservation)
    result = {'closed_at':now(),'B00_passed':b['passed'],'C00_passed':c['passed'],'M00_passed':m['passed'],
        'B00_verified_cases':b['completed_cases'],'C00_qualified_parents':c['qualified_parents'],
        'M00_valid_outputs':m.get('valid_outputs',0),'M00_http_attempts':m.get('http_attempts',0),
        'M00_provider_tokens':m.get('provider_tokens',0),'confirmation_opened':False,'new_fitting':0,
        'next_experiments_launched':False,'git_push_performed':False,
        'scientific_claim':'Exposed development comparisons and legal GET interventions; interface smoke is not forecast gain',
        'preservation_passed':not changed and not source_changed and preservation['index_unchanged']}
    publish(RUN/'FINAL_RESULT.json',result)
    lines=['# v13 B00 / C00 / M00 运行结果','',f"完成时间：{result['closed_at']}",'',
        f"- B00：验收 {b['completed_cases']}/168 个日历单元，完整通过：{b['passed']}。",
        f"- C00：合格父状态 {c['qualified_parents']}/12，执行 {c['executed_unique_branches']} 条不同 GET 分支，{c['explicit_aliases']} 个明确别名。",
        f"- M00：真实请求 {m.get('http_attempts',0)}/12，输出合同通过 {m.get('valid_outputs',0)}/12，提供方 tokens {m.get('provider_tokens',0)}。",
        '', '## B00 的完整日历结果','']
    if b['passed']:
        scores=read(B00/'METRICS.json')
        lines += ['| 阈值 | 方法 | Brier | 可结算/登记 | 阳性 | 缺失 |','|---|---|---:|---:|---:|---:|']
        for t in (1000,5000):
            for arm in ARMS:
                x=scores[f'{t}__all__all__{arm}']
                lines.append(f"| {t}m | {arm} | {x['brier']:.9f} | {x['settled']}/{x['registered']} | {x['positive']} | {x['missing']} |")
        lines += ['', '同 values 预测器的比较及缺失结果界见 B00/PAIRED_COMPARISONS.json。FOLLOW 和 F_COMMON 改变了实际消费者，单独解释。']
    lines += ['', '## 解释边界与后续','',
        '四个已暴露开发周不等同于独立天气过程；多个阈值及同一站点的重复机会不可当独立样本。',
        'M00 仅运行每个天气日的首个真实控制器 tick；旧中途请求、模拟 HTTP 预检和真实接口结果分别保留。',
        'C00 的 none 会继续公共基线更新和固定预测，不能等同于停止所有预测。失败及别名保留在登记分母中。',
        '下一步结合完整日历收益、缺失界、实际 GET 差异及接口结果决定 B01/B02 和 M01。该脚本不会自动启动重拟合、288 次正式模型实验或独立确认。','']
    (RUN/'RESULT_SUMMARY_CN.md').write_text('\n'.join(lines))
    print(json.dumps(result),flush=True)


def watch():
    publish(RUN/'FINALIZER_CLAIM.json',{'at':now(),'deadline':'2026-09-16T23:00:00+00:00',
        'no_experiment_dispatch':True,'poll_seconds':60,'source_sha256':digest(Path(__file__))})
    deadline=dt.datetime(2026,9,16,23,tzinfo=dt.timezone.utc).timestamp()
    while time.time()<deadline:
        status=snapshot();write_status(status)
        if not (B00/'RESULT.json').exists() and all((B00/f'SHARD_{i}.json').exists() for i in range(3)):
            summarize_b00()
        if all((RUN/n/'RESULT.json').exists() for n in ('B00','C00','M00')):
            closeout();write_status({**snapshot(),'batch_closed':True});return
        time.sleep(60)
    publish(RUN/'FINALIZER_TIMEOUT.json',{'at':now(),'status':snapshot(),'unfinished_work_retained':True})


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['watch','status','closeout']);a=p.parse_args()
    if a.mode=='watch':watch()
    elif a.mode=='status':print(json.dumps(snapshot()))
    else:closeout()
