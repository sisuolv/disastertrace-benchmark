"""Resume only uncompleted formal score groups after a recorded worker stop."""
import argparse
import datetime as dt
import json
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from disastertrace.monitoring_fixed_v1.outcomes import ComparisonContract
from disastertrace.monitoring_v1.formal_session import score_formal
from disastertrace.monitoring_v1.spool_backend import digest, publish, read
from stage_c import OUT, RUN, qualified_sources

HANDOFF = RUN / "stage_C_audit_handoff_01"


def inventory():
    intent = read(OUT / "INTENT.json")
    results = []
    for row in intent["cases"]:
        for arm in intent["arms"]:
            result = read(OUT / row["case"] / (arm + "_RESULT.json"))
            if not result["passed"] or result["case"] != row["case"] or result["arm"] != arm:
                raise ValueError("Handoff requires all original method executions complete")
            results.append(result)
    if len(results) != 108 or sum(r["actual_model_calls"] for r in results) != 288:
        raise ValueError("Original execution roster or model dispatch count differs")
    groups = [{"case": row["case"], "group": mode}
              for row in intent["cases"]
              for mode in read(OUT / row["case"] / "COMPARISONS.json")]
    if len(groups) != 24:
        raise ValueError("Formal comparison group roster differs")
    return results, groups


def prepare():
    qualified_sources()
    results, groups = inventory()
    HANDOFF.mkdir(exist_ok=False)
    publish(HANDOFF / "INTENT.json", {
        "at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "reason": "All108 methods complete; replace serial score tail with parallel independent groups.",
        "original_job": "pt-ql97f4xq", "original_stage_intent_sha256": digest(OUT / "INTENT.json"),
        "original_case_freeze_sha256": digest(OUT / "CASE_FREEZE.json"),
        "source_freeze_sha256": digest(RUN / "STAGE_C_SOURCE_FREEZE_02.json"),
        "script_sha256": digest(Path(__file__)),
        "groups": groups, "method_results": results,
        "new_model_calls": 0, "new_policy_executions": 0,
        "reuse_completed_score_files": True,
        "in_progress_verification_may_be_interrupted": True,
        "original_scores_and_logs_preserved": True,
    })
    print(json.dumps({"prepared": True, "methods": len(results), "score_groups": len(groups)}))


def score_one(task):
    case = OUT / task["case"]
    dest = HANDOFF / "scores" / task["case"]
    dest.mkdir(exist_ok=True)
    result = {**task, "passed": False, "reused": False}
    try:
        group = read(case / "COMPARISONS.json")[task["group"]]
        contract = group["contract"]["payload"]
        comparison = ComparisonContract(contract["invariants"], contract["allowed_interventions"])
        arms = {arm: case / arm / "admission.jsonl" for arm in group["arms"]}
        score = score_formal(read(case / "OUTCOMES.json"), arms,
                             comparison=comparison,
                             run_references={arm: case / arm for arm in arms})
        path = dest / ("SCORE_" + task["group"] + ".json")
        publish(path, score)
        result.update(passed=True, score_path=str(path), score_sha256=digest(path))
    except Exception as exc:
        result.update(error_type=type(exc).__name__, traceback=traceback.format_exc())
    publish(dest / (task["group"] + "_RESULT.json"), result)
    print(json.dumps({k: v for k, v in result.items() if k != "traceback"}), flush=True)
    return result


def execute(workers):
    intent = read(HANDOFF / "INTENT.json")
    stop = read(HANDOFF / "ORIGINAL_JOB_TERMINAL.json")
    if stop["job_id"] != intent["original_job"] or stop["state"] not in {"STOPPED", "FAILED", "SUCCEEDED"}:
        raise ValueError("Original serial worker has no terminal observation")
    if (OUT / "RESULT.json").exists():
        raise ValueError("Original worker already published a terminal result; no handoff needed")
    qualified_sources()
    if (digest(Path(__file__)) != intent["script_sha256"]
            or digest(OUT / "INTENT.json") != intent["original_stage_intent_sha256"]
            or digest(OUT / "CASE_FREEZE.json") != intent["original_case_freeze_sha256"]):
        raise ValueError("Handoff registration changed")
    results, groups = inventory()
    if results != intent["method_results"] or groups != intent["groups"]:
        raise ValueError("Execution results changed after handoff preparation")
    publish(HANDOFF / "CLAIM.json", {"at": dt.datetime.now(dt.timezone.utc).isoformat(), "workers": workers})
    scored, remaining, unreadable = [], [], []
    for task in groups:
        path = OUT / task["case"] / ("SCORE_" + task["group"] + ".json")
        if path.exists():
            try:
                read(path)
            except (ValueError, OSError) as exc:
                unreadable.append({**task, "path": str(path), "error_type": type(exc).__name__})
            else:
                scored.append({**task, "passed": True, "reused": True,
                               "score_path": str(path), "score_sha256": digest(path)})
                continue
        remaining.append(task)
    publish(HANDOFF / "REPLAY_ROSTER.json", {"reused": scored, "remaining": remaining,
        "incomplete_original_files_retained": unreadable,
        "verification_replays_are_not_policy_executions": True})
    (HANDOFF / "scores").mkdir()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(score_one, task) for task in remaining]
        for future in as_completed(futures):
            scored.append(future.result())
    passed = len(scored) == 24 and all(r["passed"] for r in scored)
    handoff_result = {"passed": passed, "groups": scored,
        "original_worker_stop": stop, "new_model_calls": 0, "new_policy_executions": 0,
        "reused_score_groups": sum(r["reused"] for r in scored),
        "new_score_groups": sum(not r["reused"] for r in scored)}
    publish(HANDOFF / "RESULT.json", handoff_result)
    publish(OUT / "RESULT.json", {
        "passed": passed, "results": results, "scored": scored,
        "new_model_calls": sum(r["actual_model_calls"] for r in results),
        "http_attempt_intents": len(list(OUT.glob("*/spool/*.api_intent.json"))),
        "confirmation_opened": False,
        "scope": "12 exposed daily development sessions; threshold5000; four global week blocks; one model",
        "finalization_kind": "recorded_parallel_score_handoff",
        "finalizer_receipt": str(HANDOFF / "RESULT.json"),
        "finalizer_receipt_sha256": digest(HANDOFF / "RESULT.json"),
        "original_serial_worker_completed_normally": False,
        "model_count_semantics": "Original completed controller dispatches; this finalizer sends no model requests.",
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["prepare", "execute"])
    parser.add_argument("--workers", type=int, default=12)
    args = parser.parse_args()
    prepare() if args.mode == "prepare" else execute(args.workers)
