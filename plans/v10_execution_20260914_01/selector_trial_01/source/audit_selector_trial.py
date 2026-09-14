"""Replay every selector trajectory and original strong control without inference."""

import argparse
import datetime as dt
import hashlib
import json
import math
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from disastertrace.monitoring_fixed_v1.outcomes import ComparisonContract
from disastertrace.monitoring_v1.audit_contracts import require_exact_ids
from disastertrace.monitoring_v1.formal_session import score_formal
from disastertrace.monitoring_v1.selection import parse_selection
from disastertrace.monitoring_v1.spool_backend import digest, publish, read


def case_audit(pair):
    batch, name = pair
    case = batch / name
    parent = Path(read(case / "CONTROL_INPUTS.json")["parent"])
    controls = read(case / "CONTROL_INPUTS.json")
    if digest(parent / "DATA.json") != digest(case / "DATA.json") or digest(parent / "BANK.json") != digest(case / "BANK.json"):
        raise ValueError("Reused program controls changed inputs")
    comp = read(case / "COMPARISON.json")["payload"]
    comparison = ComparisonContract(comp["invariants"], comp["allowed_interventions"])
    outcomes = read(case / "OUTCOMES.json")
    arms = {a: parent / a for a in controls["arms"]}
    arms["B11_LLM"] = case / "B11_LLM"
    scored = score_formal(outcomes, {a: p / "admission.jsonl" for a, p in arms.items()}, comparison=comparison)
    reference = {r["opportunity_id"]: r for r in outcomes}
    reports = {a: read(p / "REPORT.json") for a, p in arms.items()}
    expected_times = {c["opportunity_id"]: (c["started_at"], c["persisted_at"]) for c in reports["B11_COVERAGE"]["calls"]}
    rows, details = [], {}
    for arm, report in reports.items():
        require_exact_ids(reference, [r["opportunity_id"] for r in report["snapshots"]], scope=name + "/" + arm)
        for call in report["calls"]:
            if (call["started_at"], call["persisted_at"]) != expected_times[call["opportunity_id"]]:
                raise ValueError("Forecast time changed rather than preserving the public slot")
        e = {oid: status for f in report["frames"] for oid, status in f["e_statuses"].items()}
        for snapshot in report["snapshots"]:
            oid = snapshot["opportunity_id"]
            y = reference[oid]["value"]
            p, base = snapshot["forecast"]["value"], snapshot["base_forecast"]["value"]
            rows.append({"case": name, "arm": arm, "opportunity_id": oid,
                "threshold": int(name.rsplit("__", 1)[1]), "probability": p, "baseline": base, "outcome": y,
                "loss": None if y is None else (p-y)**2, "baseline_loss": None if y is None else (base-y)**2,
                "E": e.get(oid, "not_yet_resolved")})
        selected = [r for r in rows if r["arm"] == arm and r["loss"] is not None]
        assert math.isclose(scored["scores"]["arms"][arm]["loss_sum"], math.fsum(r["loss"] for r in selected), abs_tol=1e-10)
        details[arm] = {"source_requests": report["resource_spent"]["requests"], "spent": report["resource_spent"],
            "reserved": report["resource_reserved"], "forecast_calls": len(report["calls"]),
            "selector_calls": len(report["selector_calls"]), "E": dict(Counter(e.values())),
            "missed_forecast_slots": len(reference)-len(report["calls"]) if arm != "FOLLOW" else 0}
    llm = reports["B11_LLM"]
    requests = list((case / "spool").glob("*.request.json"))
    assert len(requests) == len(llm["selector_calls"])
    assert not any(r["execution_status"] for r in llm["selector_calls"])
    return {"case": name, "rows": rows, "details": details,
        "invalid_selectors": sum(r["response_error"] is not None for r in llm["selector_calls"]),
        "full_journal_replay": True, "source_and_program_identity": True}


def token_audit(batch):
    from transformers import AutoTokenizer

    model = read(batch / "MODEL_MANIFEST.json")
    tokenizer = AutoTokenizer.from_pretrained(model["directory"], local_files_only=True, trust_remote_code=False)
    count, invalid = 0, 0
    for name in read(batch / "PLAN.json")["cases"]:
        for path in sorted((batch / name / "spool").glob("*.request.json")):
            key = path.name.removesuffix(".request.json")
            request, tokens = read(path), read(path.parent / (key + ".tokens.json"))
            worker, response = read(path.parent / (key + ".worker.json")), read(path.parent / (key + ".response.json"))
            ids = tokenizer.apply_chat_template(request["messages"], tokenize=True, add_generation_prompt=True, enable_thinking=False)
            assert ids == tokens["input_ids"] and tokens["request_sha256"] == digest(path)
            assert worker["input_tokens"] == len(ids) and worker["output_tokens"] == len(worker["output_ids"])
            assert tokenizer.decode(worker["output_ids"], skip_special_tokens=True) == worker["raw"]
            assert hashlib.sha256(worker["raw"].encode()).hexdigest() == worker["raw_sha256"]
            assert digest(path.parent / (key + ".worker.json")) == response["worker_receipt_sha256"]
            assert read(path.parent / (key + ".ready.json"))["checkpoint_file_sha256"] == digest(Path(read(path.parent / (key + ".ready.json"))["checkpoint_path"]))
            assert (path.parent / (key + ".claim.json")).exists()
            view = request["request"]
            assert view["forecast_handles_are_ignored"] and view["forecast_model_call_cost"] == 0
            assert not {"outcomes", "gold", "reference_answers"}.intersection(view)
            try:
                parse_selection(worker["raw"], query_handles=view["queries"], target_handles=view["targets"], forecast_cap=view["per_tick_forecast_cap"])
                assert worker["ended_with_eos"]
            except (ValueError, AssertionError):
                invalid += 1
            count += 1
    return {"passed": True, "captured_selector_calls": count, "invalid_selectors": invalid, "no_new_inference": True}


def main(args):
    args.out.mkdir(exist_ok=False)
    deadline = time.monotonic() + args.wait_seconds
    parent = Path(read(args.batch / "PLAN.json")["control_batch"])
    while not all((p / "COMPLETE.json").exists() for p in (args.batch, parent)) and time.monotonic() < deadline:
        time.sleep(20)
    complete, plan = read(args.batch / "COMPLETE.json"), read(args.batch / "PLAN.json")
    require_exact_ids(plan["cases"], [r["case"] for r in complete["cases"]], scope="selector cases")
    tokens = token_audit(args.batch)
    publish(args.out / "TOKEN_AUDIT.json", tokens)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        cases = list(pool.map(case_audit, [(args.batch, name) for name in plan["cases"]]))
    rows = [r for c in cases for r in c["rows"]]
    with (args.out / "ROWS.jsonl").open("x") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True) + "\n")
    groups, metrics = defaultdict(list), {}
    for row in rows:
        groups[str(row["threshold"]) + "__" + row["arm"]].append(row)
    for key, group in groups.items():
        valid = [r for r in group if r["loss"] is not None]
        metrics[key] = {"registered": len(group), "scored": len(valid), "positive": sum(r["outcome"] for r in valid),
            "brier": math.fsum(r["loss"] for r in valid)/len(valid),
            "baseline_brier": math.fsum(r["baseline_loss"] for r in valid)/len(valid), "E": dict(Counter(r["E"] for r in group))}
    publish(args.out / "CASE_AUDIT.json", [{k: v for k, v in c.items() if k != "rows"} for c in cases])
    publish(args.out / "RESULT.json", {"passed": True, "cases": len(cases), "method_opportunity_rows": len(rows),
        "captured_selector_calls": tokens["captured_selector_calls"], "invalid_selectors": tokens["invalid_selectors"],
        "metrics": metrics, "at": dt.datetime.now(dt.timezone.utc).isoformat(), "confirmation_opened": False,
        "scope": "exposed development selection-only comparison; fixed native probability map and forecast schedule"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--wait-seconds", type=int, default=0)
    parser.add_argument("--workers", type=int, default=12)
    main(parser.parse_args())
