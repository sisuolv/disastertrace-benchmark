"""New-bank legal parents, exact continuations and scoped finite GET branches."""
import argparse
import json
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from b00 import RUN, REPO, OUT as B00, now, verify, restore_contract
from disastertrace.monitoring_fixed_v1.outcomes import ComparisonContract
from disastertrace.monitoring_v1 import formal_session
from disastertrace.monitoring_v1.formal_session import FormalSession, score_formal
from disastertrace.monitoring_v1.residual_query_plan import freeze_residual_plan
from disastertrace.monitoring_v1.session_checkpoint import SessionCoordinator
from disastertrace.monitoring_v1.spool_backend import digest, publish, read
from disastertrace.monitoring_v1.targets import canonical_hash

OUT = RUN / "C00"
RULES = ["none", "first_new", "second_new", "all_new"]


def prepare():
    OUT.mkdir(exist_ok=True)
    proposal = read(REPO / "plans/v13_execution_20260916_01/C00_ROSTER_PROPOSAL.json")
    rows = proposal["parent_candidates"]
    assert len(rows) == 12
    publish(OUT / "REGISTRATION.json", {"at": now(), "parents": rows, "rules": RULES,
        "parent_policy": "B11_COVERAGE", "bank": "B00 annual raw values from session start",
        "max_parents": 12, "max_noop": 12, "max_GET_branches": 48,
        "selection_reads_outcomes": False, "main_denominator": "all residual registered opportunities",
        "source_files": read(RUN / "AUTHORIZATION.json")["source_files"],
        "runner_sha256": digest(Path(__file__)), "b00_runner_sha256": digest(RUN / "b00.py"),
        "b00_registration_sha256": digest(B00 / "REGISTRATION.json"),
        "deadline_at": "2026-09-16T21:00:00+00:00", "automatic_retries": 0,
        "PROCESS_paths": 0, "WAIT_TIMING_pairs": 0, "independent_confirmation": False})


def one(row):
    case = B00 / row["case"]
    witness = OUT / row["case"]
    witness.mkdir(exist_ok=False)
    publish(witness / "CLAIM.json", {"at": now(), "one_use": True})
    result = {"case": row["case"], "passed": False, "branches": [], "opportunity_id": row["opportunity_id"]}
    start = time.monotonic()
    try:
        if not read(case / "RESULT.json")["passed"]:
            raise ValueError("New-bank B00 parent case did not qualify")
        parent = case / "B11_COVERAGE"
        data, bank, configs = [read(case / n) for n in ("DATA.json", "BANK.json", "CONFIGS.json")]
        config = configs["B11_COVERAGE"]
        original = read(parent / "FORMAL_REPORT.json")
        parent_contract = read(parent / "CONTRACT.json")
        opportunity = next(o for o in data["opportunities"] if o["opportunity_id"] == row["opportunity_id"])
        cutoffs = sorted({o["cutoff"] for o in data["opportunities"]})
        next_tick = cutoffs.index(opportunity["cutoff"])
        coordinator = SessionCoordinator(data, bank, config)
        for _ in range(next_tick):
            coordinator.step()
        cp = coordinator.persist(witness / "PARENT_CHECKPOINT.json")
        if cp["payload"]["schema"] != "disastertrace.session_quiescent.v1":
            raise ValueError("Candidate is not a quiescent legal parent")
        publish(witness / "PREFIX_REPORT.json", coordinator.report)
        publish(witness / "PARENT_BINDING.json", {
            "original_directory": str(parent), "checkpoint_sha256": digest(witness / "PARENT_CHECKPOINT.json"),
            "checkpoint_payload_sha256": cp["sha256"], "parent_contract_sha256": digest(parent / "CONTRACT.json"),
            "original_report_sha256": digest(parent / "FORMAL_REPORT.json"),
            "source_and_data_hashes": parent_contract["files"],
            "source_file": formal_session.__file__, "source_sha256": digest(Path(formal_session.__file__)),
            "kind": "new_bank_reconstructed_from_session_start", "next_tick": next_tick})
        noop = SessionCoordinator.restore(cp, data, bank).finish()
        publish(witness / "NOOP_REPORT.json", noop)
        differences = [k for k in set(original) | set(noop) if original.get(k) != noop.get(k)]
        publish(witness / "NOOP_EQUIVALENCE.json", {"passed": not differences, "different_fields": differences,
            "original_sha256": canonical_hash(original), "continuation_sha256": canonical_hash(noop)})
        publish(witness / "RESULT.json", {"passed": not differences, "parent_only": True})
        if differences:
            raise ValueError("Original-policy continuation differs: " + repr(differences))
        plans = {r: freeze_residual_plan(data, cp, row["opportunity_id"], r,
                    version="disastertrace.residual_query_plan.v2") for r in RULES}
        residual = [o["opportunity_id"] for o in data["opportunities"] if o["cutoff"] > cp["payload"]["clock"]]
        publish(witness / "BRANCH_ROSTER.json", {"plans": plans, "U_parent": residual,
            "parent_checkpoint_sha256": digest(witness / "PARENT_CHECKPOINT.json"),
            "alias_basis": "same parent, payer, authorization and planned query sequence"})
        oldcomp = parent_contract["comparison"]["payload"]
        comp = ComparisonContract(oldcomp["invariants"], {
            **oldcomp["allowed_interventions"], "residual_query_plan": [None, *plans.values()]})
        reg = read(OUT / "REGISTRATION.json")
        files = {**reg["source_files"], str(Path(__file__)): reg["runner_sha256"],
                 str(OUT / "REGISTRATION.json"): digest(OUT / "REGISTRATION.json"),
                 str(witness / "BRANCH_ROSTER.json"): digest(witness / "BRANCH_ROSTER.json")}
        aliases, journals, references = {}, {}, {}
        for rule in RULES:
            plan = plans[rule]
            key = canonical_hash({"order": plan["planned_query_order"], "payer": plan["payer_target"],
                                  "scope": plan["authorization_scope"]})
            if key in aliases:
                result["branches"].append({"rule": rule, "alias_of": aliases[key], "passed": True, "attempted": False})
                continue
            aliases[key] = rule
            child = FormalSession.fork(witness / "PARENT_CHECKPOINT.json", data, bank,
                parent_directory=parent, comparison=comp, bound_files=files, directory=witness / rule,
                controls={"residual_query_plan": plan}, witness_directory=witness)
            report = child.finish(max_steps=24)
            journals[rule] = child.export_journal(child.directory / "admission.jsonl")
            references[rule] = child.directory
            trace = next(f["residual_query_plan"] for f in report["frames"] if "residual_query_plan" in f)
            receipts = report["source_receipts"][len(cp["payload"]["controller"]["source_receipts"]):]
            if [r["query_id"] for r in receipts] != trace["executed_query_order"]:
                raise ValueError("New source receipt sequence differs from execution trace")
            if [d["query_id"] for d in trace["dispositions"]] != plan["planned_query_order"]:
                raise ValueError("Unexecuted tail is absent")
            if len(report["snapshots"]) != len(data["opportunities"]):
                raise ValueError("A child dropped original opportunities")
            publish(child.directory / "ACTION_TRACE.json", trace)
            result["branches"].append({"rule": rule, "passed": True, "attempted": True,
                                       "new_paid_GET": len(receipts), "action_trace": trace})
        score = score_formal(read(case / "OUTCOMES.json"), journals, comparison=comp, run_references=references)
        publish(witness / "FORMAL_SCORE.json", score)
        outcomes = {o["opportunity_id"]: o for o in read(case / "OUTCOMES.json")}
        branch_rows = []
        for branch in result["branches"]:
            actual = branch.get("alias_of", branch["rule"])
            report = read(witness / actual / "FORMAL_REPORT.json")
            status = {k: v for f in report["frames"] for k, v in f["e_statuses"].items()}
            for s in report["snapshots"]:
                oid = s["opportunity_id"]
                if oid not in residual:
                    continue
                y = outcomes[oid]["value"] if outcomes[oid]["status"] == "mature" else None
                branch_rows.append({"case": row["case"], "rule": branch["rule"], "alias_of": branch.get("alias_of"),
                    "opportunity_id": oid, "probability": s["forecast"]["value"], "outcome": y,
                    "e_status": status.get(oid), "loss": None if y is None else (s["forecast"]["value"] - y)**2})
        publish(witness / "RESIDUAL_ROWS.json", branch_rows)
        result.update(passed=True, exact_noop=True, remaining_opportunities=len(residual),
                      residual_method_rows=len(branch_rows), new_independent_process_claim=False,
                      source_state_strata="legal checkpoint and trace preserved; no inferred coverage by date")
    except Exception as exc:
        result.update(error=type(exc).__name__, message=str(exc), traceback=traceback.format_exc())
    result.update(finished_at=now(), seconds=time.monotonic()-start)
    publish(witness / "C00_RESULT.json", result)
    print(json.dumps({k: v for k, v in result.items() if k not in {"traceback", "branches"}}), flush=True)
    return result


def execute(workers):
    import datetime as dt
    reg = read(OUT / "REGISTRATION.json")
    verify(reg["source_files"])
    verify({str(Path(__file__)): reg["runner_sha256"], str(RUN / "b00.py"): reg["b00_runner_sha256"],
            str(B00 / "REGISTRATION.json"): reg["b00_registration_sha256"]})
    publish(OUT / "CLAIM.json", {"at": now(), "workers": workers})
    deadline = dt.datetime.fromisoformat(reg["deadline_at"]).timestamp()
    waiting, results, pending = list(reg["parents"]), [], {}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        while waiting or pending:
            for row in list(waiting):
                if (B00 / row["case"] / "RESULT.json").exists():
                    pending[pool.submit(one, row)] = row
                    waiting.remove(row)
            for f in list(pending):
                if f.done():
                    row = pending.pop(f)
                    try:
                        results.append(f.result())
                    except Exception as exc:
                        results.append({"case": row["case"], "passed": False, "error": type(exc).__name__})
            if time.time() > deadline and waiting:
                results.extend({"case": r["case"], "passed": False, "status": "parent_unavailable_before_deadline"} for r in waiting)
                waiting.clear()
            if waiting or pending:
                time.sleep(30)
    passed = len(results) == 12 and all(r["passed"] for r in results)
    publish(OUT / "RESULT.json", {"passed": passed, "parents": results, "finished_at": now(),
        "registered_parents": 12, "registered_GET_rules": 48,
        "actual_GET_branches": sum(b.get("attempted", False) for r in results for b in r.get("branches", [])),
        "new_weather_HTTP": 0, "model_calls": 0, "confirmation_opened": False})
    return 0 if passed else 1


if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("mode", choices=["prepare", "execute"])
    p.add_argument("--workers", type=int, default=6); a = p.parse_args()
    if a.mode == "prepare": prepare()
    else: raise SystemExit(execute(a.workers))
