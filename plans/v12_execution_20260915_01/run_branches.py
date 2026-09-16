"""Execute the frozen six-parent finite-action roster, without outcome selection."""
import argparse
import datetime as dt
import json
import signal
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from disastertrace.monitoring_fixed_v1.contracts import EvidenceBundle
from disastertrace.monitoring_fixed_v1.outcomes import ComparisonContract
from disastertrace.monitoring_v1.formal_session import FormalSession, required_source_files, score_formal
from disastertrace.monitoring_v1.native_feature_forecast import feature_vector, native_claims
from disastertrace.monitoring_v1.residual_query_plan import freeze_residual_plan
from disastertrace.monitoring_v1.spool_backend import digest, publish, read
from disastertrace.monitoring_v1.targets import canonical_hash

RUN = Path(__file__).resolve().parent
REPO = RUN.parents[1]
RULES = ["no_further_paid_query", "first", "second", "all"]


def prepare():
    rows = []
    for parent in read(RUN / "PARENT_CANDIDATES.json")["parents"]:
        folder = RUN / "parents" / parent["case"]
        cp = read(folder / "PARENT_CHECKPOINT.json")
        case = (REPO / parent["directory"]).parent
        data, bank = read(case / "DATA.json"), read(case / "BANK.json")
        plans = {rule: freeze_residual_plan(data, cp, parent["opportunity_id"], rule) for rule in RULES}
        rows.append({"parent": parent, "plans": plans,
            "U_parent": [o["opportunity_id"] for o in data["opportunities"] if o["cutoff"] > cp["payload"]["clock"]],
            "parent_checkpoint_sha256": digest(folder / "PARENT_CHECKPOINT.json"),
            "data_sha256": canonical_hash(data), "bank_sha256": canonical_hash(bank)})
    publish(RUN / "C2_BRANCH_ROSTER.json", {"parents": rows, "maximum_treatment_attempts": 24,
        "rules": RULES, "new_dates": 0, "selection_reads_outcomes": False,
        "at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "single_activation_window": True, "alias_key": "parent, payer, authorization, planned query order"})


def timeout_handler(*_):
    raise TimeoutError("Registered 2700 second child wall-time cap")


def trace_features(report, bank):
    rows = []
    for call in report["calls"]:
        view = EvidenceBundle.restore(call["bundle"]).policy_view()
        content = view["baseline"]["content"]
        disclosed = {a["content"]["query_id"]: a["content"] for a in view["assets"]}
        qids = content["E_question"]["query_ids"]
        claims = native_claims(qids, disclosed, at=call["started_at"])
        features = feature_vector(content["legacy_target_contract"], content["native_taf"], qids,
            disclosed, at=call["started_at"], mode=bank["mode"])
        rows.append({"opportunity_id": call["opportunity_id"], "call_id": call["call_id"],
            "started_at": call["started_at"], "claims": claims, "features": features,
            "claims_sha256": canonical_hash(claims), "features_sha256": canonical_hash(features),
            "proposed_probability": call["proposed_probability"],
            "baseline_sha256": canonical_hash(content["native_taf"]),
            "receipt": call["receipt"]})
    return rows


def run_parent(row):
    parent = row["parent"]
    folder = RUN / "branches" / parent["case"]
    folder.mkdir(exist_ok=False)
    witness = RUN / "parents" / parent["case"]
    parent_dir = REPO / parent["directory"]
    case = parent_dir.parent
    data, bank = read(case / "DATA.json"), read(case / "BANK.json")
    cp_path = witness / "PARENT_CHECKPOINT.json"
    if digest(cp_path) != row["parent_checkpoint_sha256"] or canonical_hash(data) != row["data_sha256"]:
        raise ValueError("Frozen parent changed")
    original = read(parent_dir / "CONTRACT.json")
    comparison = ComparisonContract(original["comparison"]["payload"]["invariants"], {
        **original["comparison"]["payload"]["allowed_interventions"],
        "residual_query_plan": [None, *row["plans"].values()]})
    files = {str(p): digest(p) for p in required_source_files()}
    files.update({str(RUN / n): digest(RUN / n) for n in
        ("C2_BRANCH_ROSTER.json", "run_branches.py", "BRANCH_SOURCE_FREEZE.json")})
    results, paths, references, aliases = [], {}, {}, {}
    for rule in RULES:
        plan = row["plans"][rule]
        key = canonical_hash({"order": plan["planned_query_order"], "payer": plan["payer_target"], "scope": plan["authorization_scope"]})
        if key in aliases:
            results.append({"rule": rule, "status": "alias", "alias_of": aliases[key], "attempted": False})
            continue
        aliases[key] = rule
        start = time.monotonic()
        publish(folder / (rule + "_CLAIM.json"), {"rule": rule, "at": dt.datetime.now(dt.timezone.utc).isoformat(), "plan_sha256": canonical_hash(plan)})
        result = {"rule": rule, "attempted": True, "passed": False}
        child = None
        try:
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(2700)
            child = FormalSession.fork(cp_path, data, bank, parent_directory=parent_dir,
                witness_directory=witness, comparison=comparison, bound_files=files,
                directory=folder / rule, controls={"residual_query_plan": plan})
            report = child.finish(max_steps=24)
            journal = child.export_journal(child.directory / "admission.jsonl")
            trace = next(f["residual_query_plan"] for f in report["frames"] if "residual_query_plan" in f)
            prefix = read(cp_path)["payload"]
            receipts = report["source_receipts"][len(prefix["controller"]["source_receipts"]):]
            if [r["query_id"] for r in receipts] != trace["executed_query_order"]:
                raise ValueError("Actual receipts differ from declared finite plan")
            if [d["query_id"] for d in trace["dispositions"]] != plan["planned_query_order"]:
                raise ValueError("Finite plan drops an unexecuted item")
            if len(report["snapshots"]) != len(data["opportunities"]):
                raise ValueError("Branch drops a registered opportunity")
            features = trace_features(report, report["config"]["native_feature_bank"])
            publish(child.directory / "FIELD_FEATURE_TRACE.json", features)
            publish(child.directory / "ACTION_TRACE.json", trace)
            paths[rule], references[rule] = journal, child.directory
            result.update(passed=True, status="completed", action_trace=trace,
                source_requests_after_parent=len(receipts), total_resource_spent=report["resource_spent"],
                actual_model_calls=report["actual_model_calls"], feature_trace_sha256=digest(child.directory / "FIELD_FEATURE_TRACE.json"))
        except Exception as exc:
            result.update(status="stopped_time_limit" if isinstance(exc, TimeoutError) else "failed",
                error=type(exc).__name__, message=str(exc), traceback=traceback.format_exc())
            if child is not None and not (child.directory / "STOP.json").exists():
                child.stop(result["status"])
        finally:
            signal.alarm(0)
        result["seconds"] = time.monotonic() - start
        publish(folder / (rule + "_RESULT.json"), result)
        results.append(result)
        print(json.dumps({"case": parent["case"], "rule": rule, "status": result["status"], "seconds": result["seconds"]}), flush=True)
    assessment = {"case": parent["case"], "results": results, "U_parent": row["U_parent"],
        "passed": all(r.get("passed", r["status"] == "alias") for r in results),
        "scientific_scope": "one shared global development date; finite engineering interventions"}
    if paths:
        outcomes = read(case / "OUTCOMES.json")
        score = score_formal(outcomes, paths, comparison=comparison, run_references=references)
        publish(folder / "FORMAL_SCORE.json", score)
        publish(folder / "COMMON_OUTCOMES_BINDING.json", {"path": str(case / "OUTCOMES.json"), "sha256": digest(case / "OUTCOMES.json")})
        assessment["formal_score_passed"] = True
    wakeups = {r["action_trace"]["shared_wakeup_sha256"] for r in results if r.get("passed")}
    assessment["shared_wakeup_equal"] = len(wakeups) == 1
    publish(folder / "RESULT.json", assessment)
    return assessment


def execute(workers):
    freeze = read(RUN / "BRANCH_SOURCE_FREEZE.json")
    for name, sha in freeze["files"].items():
        if digest(Path(name)) != sha:
            raise ValueError("Frozen branch implementation changed")
    if not str(required_source_files()[0]).startswith(str(RUN / "branch_source")):
        raise ValueError("Branch worker must import its frozen implementation")
    publish(RUN / "BRANCH_LAUNCH_CLAIM.json", {"at": dt.datetime.now(dt.timezone.utc).isoformat(), "workers": workers, "max_attempts": 24})
    (RUN / "branches").mkdir(exist_ok=False)
    rows = read(RUN / "C2_BRANCH_ROSTER.json")["parents"]
    results = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(run_parent, row): row["parent"]["case"] for row in rows}
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as exc:
                results.append({"case": futures[future], "passed": False, "error": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()})
    publish(RUN / "C2_BRANCH_EXECUTION_RESULT.json", {"passed": all(r["passed"] for r in results), "parents": results,
        "model_calls": 0, "new_source_HTTP_calls": 0, "maximum_treatment_attempts": 24,
        "actual_treatment_attempts": sum(r.get("attempted", False) for p in results for r in p.get("results", [])),
        "global_dates": 1, "independent_process_claim": False})


if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("mode", choices=["prepare", "execute"])
    p.add_argument("--workers", type=int, default=6); args = p.parse_args()
    prepare() if args.mode == "prepare" else execute(args.workers)
