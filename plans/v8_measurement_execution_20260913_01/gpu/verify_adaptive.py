"""Independently audit original adaptive transports and all registered sessions."""

import argparse
import hashlib
import inspect
import json
import math
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from disastertrace.monitoring_fixed_v1.admission import AdmissionEngine, score_admitted
from disastertrace.monitoring_fixed_v1.contracts import EvidenceBundle, fingerprint
from disastertrace.monitoring_fixed_v1.heads import model_messages, parse_response
from disastertrace.monitoring_fixed_v1.outcomes import ComparisonContract
from disastertrace.monitoring_fixed_v1.support_bridge import native_slot_support
from disastertrace.monitoring_v1.evidence import exists_report_support
from disastertrace.monitoring_v1.selection import SELECTOR_SYSTEM, parse_selection
from disastertrace.monitoring_v1.session_checkpoint import restore_session
from disastertrace.monitoring_v1.spool_backend import digest, publish, read


def verify_files(batch):
    plan = read(batch / "PLAN.json")
    for name, expected in plan["files"].items():
        assert digest(batch / name) == expected, name
    assert Path(inspect.getfile(AdmissionEngine)).is_relative_to(
        batch.resolve() / "source"
    )
    return plan


def check_response(request, response, worker, delivered, tokenizer, *, rehearsal):
    """Integrity failures differ from validly recorded wrong or unfinished answers."""
    fields = {
        "call_id",
        "request_sha256",
        "execution_sha256",
        "raw",
        "raw_sha256",
        "input_tokens",
        "output_tokens",
        "compute_seconds",
        "ended_with_eos",
    }
    assert set(response) == fields | {"schema", "worker_receipt_sha256"}
    assert response["schema"] == "disastertrace.spool_response.v1"
    assert all(worker.get(key) == response[key] for key in fields)
    assert response["call_id"] == request["call_id"]
    assert response["execution_sha256"] == request["execution_sha256"]
    assert (
        hashlib.sha256(response["raw"].encode()).hexdigest() == response["raw_sha256"]
    )
    assert type(response["ended_with_eos"]) is bool
    for field in ("input_tokens", "output_tokens"):
        assert type(response[field]) is int and response[field] >= 0
    seconds = response["compute_seconds"]
    assert type(seconds) in (int, float) and math.isfinite(seconds) and seconds > 0
    assert (
        delivered["observed_wall_ns"]
        >= worker["wall_started_ns"]
        >= request["dispatched_wall_ns"]
    )
    elapsed = (delivered["observed_wall_ns"] - request["dispatched_wall_ns"]) / 1e9
    assert elapsed >= seconds
    if rehearsal:
        assert worker["origin"] == "engineering_program_rehearsal"
        assert worker["input_ids"] == worker["output_ids"] == []
        assert response["input_tokens"] == response["output_tokens"] == 0
    else:
        assert worker["origin"] == "actual_local_vllm_TP4"
        input_ids = tokenizer.apply_chat_template(
            request["messages"],
            tokenize=True,
            add_generation_prompt=True,
            enable_thinking=False,
        )
        assert input_ids == worker["input_ids"]
        assert len(input_ids) == response["input_tokens"]
        assert len(worker["output_ids"]) == response["output_tokens"]
        assert (
            tokenizer.decode(worker["output_ids"], skip_special_tokens=True)
            == response["raw"]
        )
        eos = tokenizer.eos_token_id
        ended = worker["finish_reason"] == "stop" and (
            worker["stop_reason"] == eos
            or bool(worker["output_ids"])
            and worker["output_ids"][-1] == eos
        )
        assert ended == response["ended_with_eos"]
    return elapsed


def audit_case(batch, case, output, tokenizer, *, plan=None):
    plan = read(batch / "PLAN.json") if plan is None else plan
    run = batch / "runs" / case["id"]
    output.mkdir(parents=True, exist_ok=False)
    config = read(batch / case["config"])
    group = batch / "cases" / case["data_case"]
    data, bank = read(group / "DATA.json"), read(batch / "BANK.json")
    expected_ids = {o["opportunity_id"] for o in data["opportunities"]}
    assert len(expected_ids) == case["opportunities"]
    request_paths = sorted((run / "spool").glob("*.request.json"))
    inventory = [
        {
            "request": p.name,
            "request_sha256": digest(p),
            "has_response": p.with_name(
                p.name.replace(".request.json", ".response.json")
            ).exists(),
        }
        for p in request_paths
    ]
    publish(output / "INVENTORY.json", inventory)
    complete = (run / "COMPLETE.json").exists() and (run / "REPORT.json").exists()
    if not complete:
        checkpoints = sorted(run.glob("checkpoint_*.json"))
        seen = set()
        unresolved = []
        if checkpoints:
            cp = read(checkpoints[-1])
            context = restore_session(cp, data, bank, config)
            seen = set(context["runtime"].snapshots)
            unresolved = [
                key
                for key, value in context["ledger"].entries.items()
                if not value["settled"]
            ]
        row = {
            "case": case["id"],
            "status": "partial_or_unstarted",
            "expected_opportunities": len(expected_ids),
            "sealed_prefix_opportunities": len(seen),
            "unsealed_opportunity_ids": sorted(expected_ids - seen),
            "staged_requests": len(inventory),
            "received_responses": sum(r["has_response"] for r in inventory),
            "unresolved_receipt_ids": unresolved,
            "formal_score": None,
            "reason": "Incomplete sessions retain the complete registered denominator; no fabricated continuation.",
        }
        publish(output / "VALIDATION.json", row)
        return row

    report, checkpoint = read(run / "REPORT.json"), read(run / "FINAL_CHECKPOINT.json")
    assert report["config"] == config == checkpoint["payload"]["config"]
    context = restore_session(checkpoint, data, bank, config)
    engine, ledger = context["runtime"].engine, context["ledger"]
    assert engine.export() == report["event_replay"]
    assert set(engine.snapshots) == expected_ids
    assert list(engine.snapshots.values()) == report["snapshots"]
    assert engine.attempts == report["attempts"]
    assert ledger.events == report["resource_events"]
    assert asdict(ledger.spent) == report["resource_spent"]
    assert asdict(ledger.reserved) == report["resource_reserved"]
    assert context["call_records"] == report["calls"]
    assert context["selector_records"] == report["selector_calls"]
    assert context["source_receipts"] == report["source_receipts"]
    assert context["frames"] == report["frames"]
    assert not report["outcome_table_accessed_by_policy"]
    source_completion = {
        r["receipt_id"]: r["completed_at"] for r in report["source_receipts"]
    }
    pairs = {r["opportunity_id"]: r for r in data["e_f_pairs"]}
    opportunity_map = {r["opportunity_id"]: r for r in data["opportunities"]}
    recovered_e = Counter()
    for frame in report["frames"]:
        assert set(frame["e_statuses"]) == {
            oid
            for oid, row in opportunity_map.items()
            if row["cutoff"] == frame["cutoff"]
        }
        for oid, status in frame["e_statuses"].items():
            available = {
                a["content"]["query_id"]: a["content"]
                for a in context["store"].view(opportunity_map[oid]["target_id"])
                if all(
                    source_completion[rid] <= frame["cutoff"]
                    for rid in context["store"].assets[a["asset_id"]]["receipt_ids"]
                )
            }
            expected = exists_report_support(
                pairs[oid]["query_ids"], available, opportunity_map[oid]["threshold_m"]
            )
            assert expected == status
            recovered_e[expected] += 1
    assert dict(recovered_e) == report["e_counts"]
    calls = {r["call_id"]: r for r in report["calls"] + report["selector_calls"]}
    assert len(calls) == len(report["calls"]) + len(report["selector_calls"])
    model_calls = {
        cid: r
        for cid, r in calls.items()
        if cid.startswith("select-") or r["head"] != "program"
    }
    assert len(request_paths) == len(model_calls) == report["actual_model_calls"]
    assert len(model_calls) <= case["max_model_calls"]
    assert report["actual_program_forecast_calls"] == len(calls) - len(model_calls)
    seen_calls, receipts = set(), []
    history = report["event_replay"]["payload"]["history"]
    for request_path in request_paths:
        key = request_path.name.removesuffix(".request.json")
        path = lambda suffix, request_path=request_path, key=key: (
            request_path.with_name(key + suffix + ".json")
        )
        request = read(request_path)
        cid = request["call_id"]
        assert cid not in seen_calls and cid in model_calls
        seen_calls.add(cid)
        assert key == fingerprint({"run_id": case["id"], "call_id": cid})
        ready, claim = read(path(".ready")), read(path(".claim"))
        response, worker, delivered = (
            read(path(".response")),
            read(path(".worker")),
            read(path(".delivery")),
        )
        original_checkpoint = Path(ready["checkpoint_path"])
        assert original_checkpoint.parent == run.resolve()
        pending_checkpoint = read(original_checkpoint)
        payload = pending_checkpoint["payload"]
        assert (
            fingerprint(payload)
            == pending_checkpoint["sha256"]
            == ready["checkpoint_payload_sha256"]
        )
        assert digest(original_checkpoint) == ready["checkpoint_file_sha256"]
        assert payload["data_sha256"] == fingerprint(data) and payload[
            "bank_sha256"
        ] == fingerprint(bank)
        assert payload["config"] == config
        prefix = payload["runtime"]["payload"]["history"]
        assert prefix == history[: len(prefix)]
        assert (
            payload["ledger"]["events"]
            == ledger.events[: len(payload["ledger"]["events"])]
        )
        field = "pending_selector" if cid.startswith("select-") else "pending_predictor"
        pending = payload[field]
        assert pending["call_id"] == cid
        assert pending["ticket"] == {
            "remote_id": key,
            "request_sha256": digest(request_path),
        }
        assert pending["binding"] == ledger.entries[cid]["binding"]
        assert request["run_id"] == case["id"]
        assert request["execution_sha256"] == ready["execution_sha256"]
        assert ready["call_id"] == claim["call_id"] == cid
        assert (
            ready["request_sha256"]
            == claim["request_sha256"]
            == response["request_sha256"]
            == digest(request_path)
        )
        assert claim["ready_sha256"] == digest(path(".ready"))
        assert response["worker_receipt_sha256"] == digest(path(".worker"))
        assert delivered["response_sha256"] == digest(path(".response"))
        assert delivered["request_sha256"] == digest(request_path)
        assert (
            request["dispatched_wall_ns"]
            <= claim["claimed_wall_ns"]
            <= worker["wall_started_ns"]
        )
        elapsed = check_response(
            request,
            response,
            worker,
            delivered,
            tokenizer,
            rehearsal=plan["engineering_rehearsal"],
        )
        actual = model_calls[cid]
        batch_complete = read(
            batch / f"BATCH_{worker['batch_index']:04d}_COMPLETE.json"
        )
        assert batch_complete["compute_seconds"] == worker["compute_seconds"]
        assert batch_complete["requests"] == worker["batch_size"]
        if not plan["engineering_rehearsal"]:
            intent = read(batch / f"BATCH_{worker['batch_index']:04d}_INTENT.json")
            assert {"case": case["id"], "call_id": cid} in intent["calls"]
            assert len(intent["calls"]) == worker["batch_size"]
            assert intent["wall_started_ns"] == worker["wall_started_ns"]
        assert actual["raw"] == response["raw"]
        details = actual["details"]
        assert details["input_tokens"] == response["input_tokens"]
        assert details["output_tokens"] == response["output_tokens"]
        assert details["seconds"] == response["compute_seconds"]
        assert details["elapsed_seconds"] == elapsed
        assert actual["completed_at"] == actual["started_at"] + max(
            1, math.ceil(elapsed * 1e6)
        )
        if not actual.get("execution_status"):
            assert asdict(ledger.entries[cid]["actual"]) == {
                "requests": 0,
                "bytes": 0,
                "tokens": response["input_tokens"] + response["output_tokens"],
                "compute_ms": math.ceil(
                    max(1, math.ceil(response["compute_seconds"] * 1e6)) / 1000
                )
                if not cid.startswith("select-")
                else math.ceil(response["compute_seconds"] * 1000),
            }
        assert response["input_tokens"] <= plan["input_token_cap"]
        assert response["output_tokens"] <= plan["generation"]["max_tokens"]
        if cid.startswith("select-"):
            assert request["system"] == SELECTOR_SYSTEM
            assert request["request"] == pending["request"]
            assert pending["binding"]["request_sha256"] == fingerprint(
                {"system": SELECTOR_SYSTEM, "request": request["request"]}
            )
            assert all(
                q["metadata"]["available_at"] <= request["request"]["clock"]
                for q in request["request"]["queries"].values()
            )
            try:
                decoded = parse_selection(
                    response["raw"],
                    query_handles=set(request["request"]["queries"]),
                    target_handles=set(request["request"]["targets"]),
                    forecast_cap=config["per_tick_forecast_cap"],
                )
            except (ValueError, TypeError):
                assert actual["response_error"] is not None
            else:
                if response["ended_with_eos"] and not actual.get("execution_status"):
                    assert (
                        actual["response_error"] is None
                        and actual["selection"] == decoded
                    )
        else:
            bundle = EvidenceBundle.restore(actual["bundle"])
            assert request["request"] == bundle.policy_view()
            assert request["messages"] == model_messages(bundle, actual["head"])
            assert pending["binding"]["request_sha256"] == fingerprint(
                request["messages"]
            )
            assert (
                actual["expected_e_from_disclosed_products"]
                == native_slot_support(bundle, at=actual["started_at"])["status"]
            )
            try:
                decoded = parse_response(response["raw"], bundle, actual["head"])
            except (ValueError, TypeError, OverflowError):
                assert actual["response_error"] is not None
            else:
                if response["ended_with_eos"] and not actual.get("execution_status"):
                    assert (
                        actual["response_error"] is None
                        and actual["reported_e"] == decoded.e_status
                    )
                    assert actual["proposed_probability"] == decoded.forecast.value
        receipts.append(
            {
                "call_id": cid,
                "batch_index": worker["batch_index"],
                "input_tokens": response["input_tokens"],
                "output_tokens": response["output_tokens"],
                "compute_seconds": response["compute_seconds"],
                "elapsed_seconds": elapsed,
                "ended_with_eos": response["ended_with_eos"],
                "response_error": actual.get("response_error"),
                "request_sha256": digest(request_path),
                "response_sha256": digest(path(".response")),
            }
        )

    e_calls = [r for r in report["calls"] if r["head"] != "program"]
    e_correct = sum(
        r["response_error"] is None
        and r["admission_status"] == "accepted"
        and r["reported_e"] == r["expected_e_from_disclosed_products"]
        for r in e_calls
    )
    engine.write_journal(output / "admission_reconstructed.jsonl")
    comparison_row = read(group / "COMPARISON.json")["payload"]
    comparison = ComparisonContract(
        comparison_row["invariants"], comparison_row["allowed_interventions"]
    )
    spec = engine.contract["experiment"]
    comparison.validate(spec["invariants"], engine.active_interventions)
    summary = {
        "case": case["id"],
        "status": "qualified",
        "expected_opportunities": len(expected_ids),
        "sealed_opportunities": len(engine.snapshots),
        "actual_model_calls": 0 if plan["engineering_rehearsal"] else len(model_calls),
        "processor_callbacks": len(model_calls),
        "program_forecasts": report["actual_program_forecast_calls"],
        "selector_calls": len(report["selector_calls"]),
        "forecast_calls": len(report["calls"]),
        "source_queries": len(report["source_receipts"]),
        "spent": report["resource_spent"],
        "reserved": report["resource_reserved"],
        "E_availability": report["e_counts"],
        "E_correct_timely_model_answers": e_correct,
        "E_model_answer_denominator": len(e_calls),
        "E_opportunity_denominator": len(expected_ids),
        "E_no_model_submission": len(expected_ids) - len(e_calls),
        "F_changed_from_dispatch_base": sum(
            r["proposed_probability"] is not None
            and r["proposed_probability"]
            != r["bundle"]["payload"]["baseline"]["forecast"]["value"]
            for r in report["calls"]
        ),
        "forecast_admission_statuses": dict(
            Counter(r["admission_status"] for r in report["calls"])
        ),
        "selector_parse_failures": sum(
            r["response_error"] is not None for r in report["selector_calls"]
        ),
        "unfinished_answers": sum(not r["ended_with_eos"] for r in receipts),
        "source_report_sha256": digest(run / "REPORT.json"),
        "checkpoint_sha256": digest(run / "FINAL_CHECKPOINT.json"),
        "admission_journal_sha256": digest(output / "admission_reconstructed.jsonl"),
        "journal_origin": "Offline reconstruction of the committed controller event prefix; no new model calls.",
    }
    publish(output / "RECEIPTS.json", receipts)
    publish(output / "VALIDATION.json", summary)
    return summary


def finalize(batch, output):
    plan = verify_files(batch)
    rows = []
    for case in plan["cases"]:
        path = output / case["id"] / "VALIDATION.json"
        row = (
            read(path)
            if path.exists()
            else {
                "case": case["id"],
                "status": "audit_incomplete",
                "expected_opportunities": case["opportunities"],
                "formal_score": None,
            }
        )
        rows.append(row)
    scores = {}
    for group_id in sorted({case["data_case"] for case in plan["cases"]}):
        cases = [c for c in plan["cases"] if c["data_case"] == group_id]
        qualified = {r["case"] for r in rows if r["status"] == "qualified"}
        group = batch / "cases" / group_id
        contract = read(group / "COMPARISON.json")["payload"]
        paths = {
            c["arm"]: output / c["id"] / "admission_reconstructed.jsonl"
            for c in cases
            if c["id"] in qualified
        }
        scores[group_id] = {
            "expected_arms": [c["arm"] for c in cases],
            "qualified_arms": list(paths),
            "unqualified_arms": [c["arm"] for c in cases if c["id"] not in qualified],
            "full_comparison_qualified": len(paths) == len(cases),
            "scores": score_admitted(
                read(group / "OUTCOMES.json"),
                paths,
                comparison=ComparisonContract(
                    contract["invariants"], contract["allowed_interventions"]
                ),
            )
            if paths
            else None,
        }
        publish(output / (group_id + "_SCORES.json"), scores[group_id])
    actual = sum(r.get("actual_model_calls", 0) for r in rows)
    intents = sorted(batch.glob("BATCH_*_INTENT.json"))
    issued_pairs = [
        (r["case"], r["call_id"]) for p in intents for r in read(p)["calls"]
    ]
    assert len(issued_pairs) == len(set(issued_pairs)), (
        "An original invocation was generated twice"
    )
    issued = len(issued_pairs)
    assert actual <= issued <= plan["model_call_ceiling"]
    complete = all(r["status"] == "qualified" for r in rows)
    if complete:
        completion = read(batch / "COMPLETE.json")
        assert (
            completion["all_controller_exits_zero"]
            and actual == completion["actual_model_calls"] == issued
        )
    summary = {
        "plan_sha256": digest(batch / "PLAN.json"),
        "all_sessions_qualified": complete,
        "registered_sessions": len(plan["cases"]),
        "expected_opportunity_rows": sum(c["opportunities"] for c in plan["cases"]),
        "sessions": rows,
        "audited_actual_model_calls": actual,
        "issued_model_calls": issued,
        "unique_generation_batch_seconds": sum(
            read(p)["compute_seconds"] for p in batch.glob("BATCH_*_COMPLETE.json")
        ),
        "engineering_rehearsal": plan["engineering_rehearsal"],
        "independent_confirmation": False,
        "interpretation": "Complete exposed development calendar, two protocols and thresholds reported separately. Unfinished sessions are explicit unscored rows; no selective response retries or invented outcomes.",
        "timing_limitations": plan["timing"],
    }
    publish(output / "VALIDATION.json", summary)
    print(
        json.dumps(
            {
                k: summary[k]
                for k in (
                    "all_sessions_qualified",
                    "registered_sessions",
                    "audited_actual_model_calls",
                )
            }
        )
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["case", "finalize"])
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case")
    args = parser.parse_args()
    if args.mode == "finalize":
        finalize(args.batch, args.output)
        return
    plan = verify_files(args.batch)
    tokenizer = None
    if not plan["engineering_rehearsal"]:
        from transformers import AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(
            plan["model"]["directory"], local_files_only=True
        )
    case = next(c for c in plan["cases"] if c["id"] == args.case)
    try:
        row = audit_case(
            args.batch, case, args.output / case["id"], tokenizer, plan=plan
        )
    except Exception as exc:
        publish(
            args.output / case["id"] / "AUDIT_FAILED.json",
            {"exception": type(exc).__name__, "message": str(exc)},
        )
        raise
    print(json.dumps(row, separators=(",", ":")))


if __name__ == "__main__":
    main()
