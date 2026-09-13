"""Reconcile raw tokens, entitlement receipts, costs and every frozen opportunity."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from gpu_worker import digest, save


def main(args):
    batch, output = args.batch.resolve(), args.output.resolve()
    output.mkdir(exist_ok=False)
    (output / "verify_gpu.py").write_bytes(Path(__file__).read_bytes())
    plan = json.loads((batch / "PLAN.json").read_text())
    for name, expected in plan["files"].items():
        if digest(batch / name) != expected:
            raise ValueError("Frozen input changed: " + name)
    sys.path.insert(0, str(batch / "source"))
    from disastertrace.monitoring_v1.journal import read_journal
    from disastertrace.monitoring_v1.scoring import brier_report
    from disastertrace.monitoring_v1.state import MonitoringEngine
    from disastertrace.monitoring_v1.targets import canonical_hash
    from transformers import AutoProcessor, AutoTokenizer

    tokenizers, reports, eos_ids, processors = {}, {}, {}, {}
    for key, spec in plan["models"].items():
        tokenizers[key] = AutoTokenizer.from_pretrained(
            spec["directory"], local_files_only=True
        )
        eos = json.loads(
            (Path(spec["directory"]) / "generation_config.json").read_text()
        )["eos_token_id"]
        eos_ids[key] = eos if isinstance(eos, list) else [eos]
        if "scenes" in plan:
            processors[key] = AutoProcessor.from_pretrained(
                spec["directory"],
                local_files_only=True,
                min_pixels=256 * 32 * 32,
                max_pixels=1024 * 32 * 32,
            )
    total_calls, actual_tokens = 0, 0
    for worker, tasks in plan["workers"].items():
        worker_dir = batch / ("worker-" + worker)
        complete = json.loads((worker_dir / "COMPLETE.json").read_text())
        hardware = json.loads((worker_dir / "HARDWARE.json").read_text())
        if complete["plan_sha256"] != digest(batch / "PLAN.json"):
            raise ValueError("Completion plan identity mismatch")
        if (
            hardware["count"] != 1
            or "H100" not in hardware["name"]
            or hardware["hostname"] == plan["cci_hostname"]
        ):
            raise ValueError("Actual worker hardware mismatch")
        job_id = (batch / "submissions" / worker / "job-id.txt").read_text().strip()
        result = subprocess.run(
            [
                "/mnt/afs/260010168/bin/sco",
                "acp",
                "jobs",
                "describe",
                "--workspace-name=share-space",
                "--format=json",
                job_id,
            ],
            capture_output=True,
            text=True,
            timeout=45,
            check=True,
        )
        job = json.loads(result.stdout)
        save(output / ("JOB-" + worker + ".json"), job)
        if job["state"] != "SUCCEEDED":
            raise ValueError("Actual ACP job has not succeeded: " + job_id)
        tokenizer = tokenizers[plan["worker_models"][worker]]
        worker_calls = 0
        for task in tasks:
            directory = worker_dir / task["run_id"]
            trace = json.loads((directory / "TRACE.json").read_text())
            data = json.loads((batch / task["data_file"]).read_text())
            if trace["config"] != task["config"]:
                raise ValueError("Trace configuration changed")
            expected_ids = {o["opportunity_id"] for o in data["opportunities"]}
            if {r["opportunity_id"] for r in trace["snapshots"]} != expected_ids or len(
                trace["snapshots"]
            ) != len(expected_ids):
                raise ValueError("Opportunity denominator mismatch")
            engine = MonitoringEngine.restore(trace["event_replay"])
            if list(engine.snapshots.values()) != trace["snapshots"]:
                raise ValueError("Event replay failed")
            journal = read_journal(directory / "EVENTS.jsonl")
            if (
                journal.incomplete_tail
                or [r["payload"] for r in journal.records]
                != trace["event_replay"]["payload"]["events"]
            ):
                raise ValueError("Durable event receipts differ")
            if (directory / "RESOURCES.jsonl").exists():
                resource_journal = read_journal(directory / "RESOURCES.jsonl")
                if (
                    resource_journal.incomplete_tail
                    or [r["payload"] for r in resource_journal.records[1:]]
                    != trace["resource_events"]
                ):
                    raise ValueError("Durable resource receipts differ")
            reserve, spent = {}, {key: 0 for key in trace["resource_spent"]}
            limits = {
                "requests": task["config"]["request_budget"],
                "bytes": task["config"]["request_budget"] * 2048,
                "tokens": task["config"].get("token_cap"),
                "compute_ms": task["config"].get("compute_ms_cap"),
            }
            for event in trace["resource_events"]:
                ident = event["receipt_id"]
                if event["event"] == "reserve":
                    if ident in reserve:
                        raise ValueError("Duplicate reservation")
                    reserve[ident] = event["upper"]
                else:
                    upper = reserve.pop(ident)
                    for dimension, value in event["actual"].items():
                        if value < 0 or value > upper[dimension]:
                            raise ValueError("Actual resource exceeds its reservation")
                        spent[dimension] += value
                for dimension, limit in limits.items():
                    reserved = sum(v[dimension] for v in reserve.values())
                    if limit is not None and spent[dimension] + reserved > limit:
                        raise ValueError(
                            "Global resource limit was exceeded before settlement"
                        )
            if (
                reserve
                or spent != trace["resource_spent"]
                or any(trace["resource_reserved"].values())
            ):
                raise ValueError("Final resources do not reconcile")
            products = {q["query_id"]: q for q in data["query_results"]}
            opportunity_map = {o["opportunity_id"]: o for o in data["opportunities"]}
            target_map = {t["target_id"]: t for t in data["targets"]}
            receipts = {r["asset_id"]: r for r in trace["source_receipts"]}
            prompt_token_sum = 0
            processor_visual_tokens = []
            all_calls = sorted(
                trace["calls"] + trace.get("selector_calls", []),
                key=lambda c: (c["started_at"], c["call_id"]),
            )
            prefix_replay = deepcopy(trace["event_replay"])
            prefix_replay["payload"]["processed_through"] = min(
                (c["started_at"] for c in all_calls),
                default=trace["event_replay"]["payload"]["processed_through"],
            )
            prefix_replay["sha256"] = canonical_hash(prefix_replay["payload"])
            at_start = MonitoringEngine.restore(prefix_replay)
            for call in all_calls:
                at_start.run([], until=call["started_at"])
                prefix = call["call_id"]
                request = json.loads(
                    (directory / (prefix + "-request.json")).read_text()
                )
                response = json.loads(
                    (directory / (prefix + "-response.json")).read_text()
                )
                raw = (directory / (prefix + "-raw.txt")).read_text()
                if "scenes" in plan:
                    from disastertrace.monitoring_v1.policies import FORECAST_SYSTEM
                    from mm_inputs import prepare_inputs

                    prompt = request["base_request"]
                    processor = processors[plan["worker_models"][worker]]
                    _, actual = prepare_inputs(
                        processor,
                        FORECAST_SYSTEM,
                        prompt,
                        task["representation"],
                        plan["scenes"][str(prompt["cutoff"])],
                        batch,
                    )
                    if any(request[k] != v for k, v in actual.items()):
                        raise ValueError(
                            "Actual processor tensor/image/message replay differs"
                        )
                    processor_visual_tokens.append(actual["visual_tokens"])
                    ids = actual["input_ids"]
                    rendered = processor.apply_chat_template(
                        request["messages"], tokenize=False, add_generation_prompt=True
                    )
                else:
                    prompt = json.loads(request["messages"][1]["content"])
                    rendered = tokenizer.apply_chat_template(
                        request["messages"],
                        tokenize=False,
                        add_generation_prompt=True,
                        enable_thinking=False,
                    )
                    ids = tokenizer(rendered, add_special_tokens=False)["input_ids"]
                if ids != request["input_ids"] or len(ids) != response["input_tokens"]:
                    raise ValueError("Input token replay mismatch")
                if (
                    hashlib.sha256(rendered.encode()).hexdigest()
                    != request["rendered_sha256"]
                ):
                    raise ValueError("Rendered request changed")
                if (
                    tokenizer.decode(response["output_ids"], skip_special_tokens=True)
                    != raw
                    or raw != call["raw"]
                ):
                    raise ValueError("Raw output/token/trace mismatch")
                if hashlib.sha256(raw.encode()).hexdigest() != response["raw_sha256"]:
                    raise ValueError("Raw response changed")
                if len(response["output_ids"]) != response["output_tokens"]:
                    raise ValueError("Output token count mismatch")
                ended = bool(
                    response["output_ids"]
                    and response["output_ids"][-1]
                    in eos_ids[plan["worker_models"][worker]]
                )
                if ended != response["ended_with_eos"]:
                    raise ValueError(
                        "EOS finish flag differs from raw generated token IDs"
                    )
                if any(
                    call["details"].get(k) != v
                    for k, v in response.items()
                    if k != "output_ids"
                ):
                    raise ValueError("Captured cost details differ from charged trace")
                prompt_token_sum += response["input_tokens"] + response["output_tokens"]
                if prefix.startswith("select-"):
                    if (
                        task["config"]["authorization_mode"] != "session_shared"
                        or canonical_hash(prompt) != call["request_sha256"]
                    ):
                        raise ValueError("Selector scope or request identity changed")
                    if prompt["clock"] != call["started_at"]:
                        raise ValueError("Selector clock mismatch")
                    expected_products = {}
                    for row in prompt["targets"].values():
                        target_id = row["target"]["target_id"]
                        if row["target"] != target_map[target_id]:
                            raise ValueError("Selector target changed")
                        if (
                            row["common"]["baseline_probability"]
                            != at_start._base(target_id, call["started_at"])[
                                "probability"
                            ]
                        ):
                            raise ValueError(
                                "Selector was given a non-current baseline"
                            )
                        if "current_state" in row and row[
                            "current_state"
                        ] != at_start.policy_state(target_id, call["started_at"]):
                            raise ValueError(
                                "Selector current target state differs from replay"
                            )
                        if (
                            task["config"].get("selector_contract")
                            == "shared_target_state_resources.v2"
                            and "current_state" not in row
                        ):
                            raise ValueError(
                                "Explicit-state selector omitted target state"
                            )
                        revision = at_start._base(target_id, call["started_at"])[
                            "product_revision_id"
                        ]
                        applicable = [
                            c
                            for c in data["baseline_candidates"]
                            if c["target_id"] == target_id
                            and c["source_id"] == revision
                        ]
                        if applicable:
                            expected_products[revision] = applicable[0]["raw"]
                    if prompt["common_full_taf_products"] != expected_products:
                        raise ValueError("Selector current full native TAF set differs")
                    catalog = {q["query_id"]: q for q in data["query_catalog"]}
                    for query in prompt["queries"].values():
                        qid = query["query_id"]
                        if (
                            query["metadata"] != catalog[qid]
                            or catalog[qid]["available_at"] > call["started_at"]
                        ):
                            raise ValueError(
                                "Selector query metadata is changed or unavailable"
                            )
                    for asset in prompt["shared_recent_products"]:
                        qid = asset["content"]["query_id"]
                        if (
                            asset["content"] != products[qid]
                            or receipts[asset["asset_id"]]["completed_at"]
                            > call["started_at"]
                        ):
                            raise ValueError(
                                "Selector received unacquired or future evidence"
                            )
                    continue
                opportunity = opportunity_map[call["opportunity_id"]]
                target_id = opportunity["target_id"]
                if (
                    prompt["target"] != target_map[target_id]
                    or prompt["cutoff"] != opportunity["cutoff"]
                ):
                    raise ValueError("Target or cutoff drift")
                if (
                    prompt["common_baseline"]
                    != engine.calls[prefix]["baseline_snapshot"]
                ):
                    raise ValueError("Begin-time common baseline mismatch")
                if "current_state" in prompt and prompt[
                    "current_state"
                ] != at_start.policy_state(target_id, call["started_at"]):
                    raise ValueError("Forecast current state differs from legal replay")
                if (
                    task["config"].get("prompt_contract")
                    == "explicit_target_state_actions.v2"
                    and "current_state" not in prompt
                ):
                    raise ValueError("Explicit-state forecaster omitted current state")
                revision = prompt["common_baseline"]["product_revision_id"]
                candidates = [
                    c
                    for c in data["baseline_candidates"]
                    if c["target_id"] == target_id and c["source_id"] == revision
                ]
                expected_taf = candidates[0]["raw"] if candidates else None
                if prompt["full_native_taf"] != expected_taf:
                    raise ValueError("Full native common TAF was changed or omitted")
                for asset in prompt["read_evidence"]:
                    qid = asset["content"]["query_id"]
                    receipt = receipts[asset["asset_id"]]
                    if (
                        asset["content"] != products[qid]
                        or receipt["completed_at"] > call["started_at"]
                    ):
                        raise ValueError("Undisclosed or future source contents")
                    if (
                        task["config"]["authorization_mode"] == "target_private"
                        and receipt["payer"] != target_id
                    ):
                        raise ValueError("Private evidence crossed a target boundary")
            if prompt_token_sum != spent["tokens"]:
                raise ValueError("Token charges differ from actual processor receipts")
            worker_calls += len(all_calls)
            total_calls += len(all_calls)
            if len(all_calls) > task["config"].get(
                "model_call_budget", task["config"]["forecast_call_cap"]
            ):
                raise ValueError("Combined selector/forecast model budget exceeded")
            actual_tokens += prompt_token_sum
            # Outcome reads occur after all source/entitlement/token checks.
            outcome_path = args.outcomes.resolve()
            if plan["evaluation_bindings"].get(str(outcome_path)) != digest(
                outcome_path
            ):
                raise ValueError(
                    "Evaluation outcome file does not match frozen binding"
                )
            outcomes = {r["target_id"]: r for r in json.loads(outcome_path.read_text())}

            def score(snapshots, outcomes=outcomes):
                rows = [
                    {
                        "opportunity_id": r["opportunity_id"],
                        "base": r["base_probability"],
                        "prediction": r["probability"],
                        "outcome": outcomes[r["target_id"]]["outcome"],
                        "region": args.region,
                        "period": str(r["cutoff"] // 86_400_000_000),
                        "source": "native_metar",
                        "quality": outcomes[r["target_id"]]["status"],
                        "maturity": "final_archive",
                        "baseline_kind": r["baseline_kind"],
                    }
                    for r in snapshots
                ]
                return brier_report(rows)

            alternate = deepcopy(trace["event_replay"])
            alternate["payload"]["protocol"] = (
                "persistent_override"
                if task["config"]["protocol"] == "base_bound_override"
                else "base_bound_override"
            )
            alternate["sha256"] = canonical_hash(alternate["payload"])
            other = MonitoringEngine.restore(alternate)
            reports[worker + ":" + task["run_id"]] = {
                "config": task["config"],
                "calls": len(trace["calls"]),
                "selector_calls": len(trace.get("selector_calls", [])),
                "actual_model_calls": len(all_calls),
                "selector_invalid_responses": sum(
                    c["response_error"] is not None
                    for c in trace.get("selector_calls", [])
                ),
                "scores": score(trace["snapshots"]),
                "e_correct": sum(
                    c["reported_e"] == c["expected_e_from_disclosed_products"]
                    for c in trace["calls"]
                ),
                "invalid_responses": sum(
                    c["response_error"] is not None for c in trace["calls"]
                ),
                "citation_error_calls": sum(
                    bool(c["citation_errors"]) for c in trace["calls"]
                ),
                "attempt_statuses": dict(
                    Counter(a["status"] for a in trace["attempts"])
                ),
                "e_counts": trace["e_counts"],
                "e_confusion": dict(
                    Counter(
                        str(c["expected_e_from_disclosed_products"])
                        + " -> "
                        + str(c["reported_e"])
                        for c in trace["calls"]
                    )
                ),
                "common_mapped_full_taf_opportunities": sum(
                    r["baseline_kind"] == "research" for r in trace["snapshots"]
                ),
                "positive_opportunities": sum(
                    outcomes[r["target_id"]]["outcome"] == 1 for r in trace["snapshots"]
                ),
                "costs": spent,
                "actual_processor_visual_tokens": processor_visual_tokens,
                "fixed_sensor_collection": plan.get("fixed_sensor_collection"),
                "alternate_fixed_candidate_protocol": alternate["payload"]["protocol"],
                "alternate_fixed_candidate_scores": score(
                    list(other.snapshots.values())
                ),
                "fixed_trace_interpretation": "direct wrapper comparison; no separately adapted policy inference",
            }
        if (
            worker_calls != complete["model_calls"]
            or worker_calls > plan["max_calls_per_worker"]
        ):
            raise ValueError("Worker call count mismatch")
    if total_calls > plan["maximum_model_calls"]:
        raise ValueError("Batch cap exceeded")
    report = {
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "validator_sha256": digest(output / "verify_gpu.py"),
        "batch": str(batch),
        "plan_sha256": digest(batch / "PLAN.json"),
        "actual_calls": total_calls,
        "actual_tokens": actual_tokens,
        "verified_workers": len(plan["workers"]),
        "reports": reports,
        "interpretation": plan["interpretation"],
        "checks": [
            "source hashes",
            "actual ACP success and H100",
            "input/output tokenizer replay",
            "durable events",
            "deterministic opportunity reconstruction",
            "native evidence entitlement",
            "independent resource receipt reconciliation",
            "frozen outcome binding",
        ],
    }
    save(output / "VERIFIED.json", report)
    print(
        json.dumps(
            {
                "actual_calls": total_calls,
                "actual_tokens": actual_tokens,
                "verified_workers": len(plan["workers"]),
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--outcomes", type=Path, required=True)
    parser.add_argument("--region", default="bay_area")
    main(parser.parse_args())
