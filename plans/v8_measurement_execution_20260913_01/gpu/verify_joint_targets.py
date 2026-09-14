"""Independently verify fixed X09 captures with every requested target retained."""

import argparse
import inspect
import json
from collections import Counter, defaultdict
from pathlib import Path

from analyze_evidence_witnesses import interval_witness
from disastertrace.monitoring_fixed_v1.contracts import fingerprint
from disastertrace.monitoring_fixed_v1.joint_targets import (
    joint_messages,
    parse_joint_response,
)
from verify_large_diagnostic import digest, load, require, save, verify_capture


def verify(batch, output, allow_unlaunched=False):
    from transformers import AutoTokenizer

    plan = load(batch / "PLAN.json")
    require(
        Path(inspect.getfile(joint_messages)).is_relative_to(batch / "source"),
        "Use the frozen source PYTHONPATH",
    )
    require(
        plan["generation_enabled"] or allow_unlaunched,
        "Unlaunched analysis must be explicitly labelled",
    )
    for rel, expected in plan["files"].items():
        require(digest(batch / rel) == expected, "Changed frozen file: " + rel)
    if (batch / "EVALUATOR_MANIFEST.json").exists():
        require(
            digest(batch / "EVALUATOR_MANIFEST.json")
            == plan["evaluator_manifest_sha256"],
            "Changed evaluator binding",
        )
        for rel, expected in load(batch / "EVALUATOR_MANIFEST.json").items():
            require(digest(batch / rel) == expected, "Changed evaluator file: " + rel)
    output.mkdir(parents=True, exist_ok=False)
    model = "qwen235b_fp8"
    for file in plan["models"][model]["files"]:
        if "safetensors" not in file["path"]:
            require(
                digest(Path(plan["models"][model]["directory"]) / file["path"])
                == file["sha256"],
                "Changed tokenizer/model metadata",
            )
    tokenizer = AutoTokenizer.from_pretrained(
        plan["models"][model]["directory"], local_files_only=True
    )
    references = load(batch / "evaluator/E_REFERENCES.json")
    cohorts = {r["group_id"]: r for r in load(batch / "evaluator/COHORTS.json")}
    outcomes = {
        r["opportunity_id"]: r
        for r in load(batch / "evaluator/CANONICAL_OUTCOMES.json")
    }
    plan_hash = digest(batch / "PLAN.json")
    calls, target_rows, contexts = [], [], {}
    for index, task in enumerate(plan["tasks"]):
        cid = task["call_id"]
        request = load(batch / "policy" / (cid + ".json"))
        context, wanted = request["context"], task["answer_target_ids"]
        messages = joint_messages(context, wanted, head=task["head"])
        require(
            messages == request["messages"]
            and fingerprint(messages) == task["messages_sha256"],
            "Frozen renderer differs",
        )
        require(
            context["context_sha256"] == task["context_sha256"],
            "Context identity differs",
        )
        latest = max(
            [r["baseline"]["available_at"] for r in context["targets"]]
            + [a["completed_at"] for a in context["shared_sources"]]
        )
        require(
            latest
            <= task["logical_started_at"]
            < task["logical_cutoff"]
            == context["cutoff"],
            "Future input or changed dispatch/cutoff",
        )
        key = (task["group_id"], task["head"])
        require(
            contexts.get(key, context) == context, "Single/multi information differs"
        )
        contexts[key] = context
        for row in context["targets"]:
            tids = row["baseline"]["content"]["E_question"]["query_ids"]
            witness = interval_witness(
                {
                    "baseline": row["baseline"],
                    "assets": [
                        a
                        for a in context["shared_sources"]
                        if a["content"]["query_id"] in tids
                    ],
                }
            )
            require(
                witness["independent_expected_E"]
                == references[task["group_id"]][row["target"]["target_id"]][
                    "expected_E"
                ],
                "Native support reference differs",
            )
        size = min(
            plan["batch_size"],
            len(plan["tasks"]) - index // plan["batch_size"] * plan["batch_size"],
        )
        receipt = verify_capture(
            batch / model,
            task,
            model,
            plan_hash,
            tokenizer,
            size,
            index // plan["batch_size"] * plan["batch_size"],
        )
        response, commit = receipt["response"], receipt["commit"]
        timely = (
            commit is not None
            and commit["logical_persisted_at"] <= task["logical_cutoff"]
        )
        eos = response is not None and response["ended_with_eos"]
        parsed, error = {}, None
        if response is not None:
            try:
                parsed = parse_joint_response(
                    response["raw"], context, wanted, head=task["head"]
                )
            except (ValueError, TypeError) as exc:
                error = str(exc)
        admitted = (
            receipt["disposition"] == "committed" and timely and eos and error is None
        )
        cohort = cohorts[task["group_id"]]
        calls.append(
            {
                "call_id": cid,
                "group_id": task["group_id"],
                "head": task["head"],
                "scope": task["scope"],
                "condition": cohort["condition"],
                "threshold_m": cohort["threshold_m"],
                "requested_targets": len(wanted),
                "disposition": receipt["disposition"],
                "timely": timely,
                "ended_with_eos": eos,
                "parse_error": error,
                "admitted": admitted,
                "input_tokens": 0
                if receipt["request"] is None
                else receipt["request"]["input_tokens"],
                "output_tokens": 0 if response is None else response["output_tokens"],
                "batch_offset": index // plan["batch_size"] * plan["batch_size"],
                "batch_elapsed_us": None
                if response is None
                else response["batch_elapsed_us"],
                "persisted_elapsed_us": None
                if commit is None
                else commit["persisted_elapsed_us"],
                "raw": None if response is None else response["raw"],
            }
        )
        for tid in wanted:
            ref = references[task["group_id"]][tid]
            outcome = outcomes[ref["opportunity_id"]]
            require(
                outcome["target_contract_hash"] == ref["target_contract_hash"],
                "Wrong target outcome",
            )
            y = outcome["value"] if outcome["status"] == "mature" else None
            base = ref["baseline_probability"]
            answer = parsed.get(tid, {})
            e_label = {
                "true": "supported",
                "false": "refuted",
                "unknown": "undetermined",
                "conflict": "inconsistent",
            }.get(answer.get("fact_truth"))
            has_F, has_E = task["head"] != "e_only", task["head"] != "f_only"
            proposal = answer.get("probability") if has_F else None
            effective = proposal if has_F and admitted else base
            target_rows.append(
                {
                    "call_id": cid,
                    "target_id": tid,
                    "opportunity_id": ref["opportunity_id"],
                    "group_id": task["group_id"],
                    "head": task["head"],
                    "scope": task["scope"],
                    "condition": cohort["condition"],
                    "threshold_m": cohort["threshold_m"],
                    "expected_E": ref["expected_E"] if has_E else None,
                    "answer_E": e_label,
                    "E_correct_by_cutoff": has_E
                    and admitted
                    and e_label == ref["expected_E"],
                    "E_unsupported_determination": has_E
                    and e_label in {"supported", "refuted"}
                    and ref["expected_E"] in {"undetermined", "inconsistent"},
                    "admitted": admitted,
                    "outcome": y,
                    "baseline_probability": base,
                    "candidate_probability": proposal,
                    "effective_probability": effective if has_F else None,
                    "mode": ("OVERRIDE" if admitted else "FOLLOW")
                    if has_F
                    else "E_ONLY",
                    "F_brier": (effective - y) ** 2
                    if has_F and y is not None
                    else None,
                    "baseline_brier": (base - y) ** 2
                    if has_F and y is not None
                    else None,
                }
            )
    require(
        len(calls) == 384 and len(target_rows) == 576, "Lost registered denominator"
    )
    tables = []
    grouped = defaultdict(list)
    for row in target_rows:
        grouped[
            (row["threshold_m"], row["condition"], row["head"], row["scope"])
        ].append(row)
    for key, rows in sorted(grouped.items()):
        require(len(rows) == 24, "Unequal comparison target denominator")
        f = [r for r in rows if r["F_brier"] is not None]
        tables.append(
            {
                "threshold_m": key[0],
                "condition": key[1],
                "head": key[2],
                "scope": key[3],
                "targets": len(rows),
                "E_correct": sum(r["E_correct_by_cutoff"] for r in rows)
                if key[2] != "f_only"
                else None,
                "E_unsupported_determination": sum(
                    r["E_unsupported_determination"] for r in rows
                )
                if key[2] != "f_only"
                else None,
                "admitted_targets": sum(r["admitted"] for r in rows),
                "F_scored": len(f),
                "F_brier": sum(r["F_brier"] for r in f) / len(f) if f else None,
                "baseline_brier": sum(r["baseline_brier"] for r in f) / len(f)
                if f
                else None,
                "F_changed_probability": sum(
                    r["candidate_probability"] is not None
                    and r["candidate_probability"] != r["baseline_probability"]
                    for r in rows
                ),
            }
        )
    pairing = defaultdict(dict)
    for row in target_rows:
        key = (row["group_id"], row["head"], row["opportunity_id"])
        require(row["scope"] not in pairing[key], "Duplicate target/scope")
        pairing[key][row["scope"]] = row
    require(
        len(pairing) == 288
        and all(set(pair) == {"single", "multi"} for pair in pairing.values()),
        "Incomplete fixed-input pairs",
    )
    pairs = []
    for key, pair in sorted(pairing.items()):
        a, b = pair["single"], pair["multi"]
        pairs.append(
            {
                "group_id": key[0],
                "head": key[1],
                "opportunity_id": key[2],
                "threshold_m": a["threshold_m"],
                "condition": a["condition"],
                "E_correct_multi_minus_single": int(b["E_correct_by_cutoff"])
                - int(a["E_correct_by_cutoff"])
                if key[1] != "f_only"
                else None,
                "F_brier_single_minus_multi": a["F_brier"] - b["F_brier"]
                if a["F_brier"] is not None
                else None,
            }
        )
    started = (batch / model / "STARTED.json").exists()
    hardware_path = batch / model / "HARDWARE.json"
    hardware_ok = False
    if hardware_path.exists():
        hardware = load(hardware_path)
        hardware_ok = (
            hardware["plan_sha256"] == plan_hash
            and hardware["runtime_versions"] == plan["runtime_versions"]
            and hardware["model_files_verified"] == plan["models"][model]["files"]
            and hardware["tensor_parallel_size"] == 4
            and len(hardware["gpus"]) == 4
            and all("H100" in gpu["name"] for gpu in hardware["gpus"])
        )
        require(hardware_ok, "Wrong hardware/model binding")
    committed = sum(r["disposition"] == "committed" for r in calls)
    request_files = list((batch / model).glob("*-request.json"))
    require(
        len(request_files) == sum(r["disposition"] != "unattempted" for r in calls),
        "Unexpected or lost request file",
    )
    known_calls = {task["call_id"] for task in plan["tasks"]}
    for kind in ("request", "response", "commit"):
        require(
            all(
                p.name.removesuffix("-" + kind + ".json") in known_calls
                for p in (batch / model).glob("*-" + kind + ".json")
            ),
            "Unregistered capture file",
        )
    compatibility = int((batch / model / "SMOKE_REQUEST.json").exists())
    smoke_ok = None
    if compatibility:
        smoke = load(batch / model / "SMOKE_REQUEST.json")
        require(
            smoke["plan_sha256"] == plan_hash
            and smoke["prompt_token_ids"]
            == tokenizer.apply_chat_template(
                [{"role": "user", "content": "Return exactly READY."}],
                tokenize=True,
                add_generation_prompt=True,
                enable_thinking=False,
            ),
            "Compatibility request identity differs",
        )
    if (batch / model / "SMOKE_RESPONSE.json").exists():
        require(compatibility == 1, "Compatibility response without request")
        smoke = load(batch / model / "SMOKE_RESPONSE.json")
        require(
            tokenizer.decode(smoke["output_ids"], skip_special_tokens=True)
            == smoke["raw"],
            "Compatibility output tokens differ",
        )
        smoke_ok = smoke["raw"].strip() == "READY" and smoke["finish_reason"] == "stop"
    if committed:
        require(started and hardware_ok, "Committed inference lacks runtime binding")
    if (batch / model / "COMPLETE.json").exists():
        complete = load(batch / model / "COMPLETE.json")
        require(
            complete["plan_sha256"] == plan_hash
            and complete["benchmark_calls"] == committed
            and complete["compatibility_calls"] == compatibility,
            "Worker completion differs from captures",
        )
    require(len(request_files) + compatibility <= 385, "Unregistered extra calls")
    summary = {
        "integrity_passed": True,
        "plan_sha256": plan_hash,
        "registered_calls": 384,
        "registered_target_answers": 576,
        "unique_opportunities": 48,
        "paired_target_head_conditions": 288,
        "actual_benchmark_requests": len(request_files),
        "compatibility_requests": compatibility,
        "committed_calls": committed,
        "all_planned_completed": committed == 384,
        "real_model_results": started and hardware_ok and committed > 0,
        "runtime_hardware_verified": hardware_ok,
        "compatibility_reply_ready": smoke_ok,
        "verification_source_hashes": {
            str(path): digest(path)
            for path in [
                Path(__file__),
                Path(inspect.getfile(verify_capture)),
                Path(inspect.getfile(joint_messages)),
                Path(inspect.getfile(interval_witness)),
            ]
        },
        "dispositions": dict(Counter(r["disposition"] for r in calls)),
        "admitted_calls": sum(r["admitted"] for r in calls),
        "dryrun": not started,
        "new_model_calls": 0,
        "metric_scope": "Strict fixed-input request-level admission, not a full shared-budget SessionCoordinator execution.",
        "limits": [
            "One malformed multi-target response fails every requested E target and leaves their F baselines; no selected salvage.",
            "E-only contributes no F score. All same-value accepted probabilities remain explicit proposals.",
            "Tables retain all planned opportunities including unattempted, unknown, late and invalid calls; zero-response dryruns are not model scores.",
            "Both scopes see all common professional information and the same explicit shared source union. This is not a private/shared allocation experiment.",
            "Per-call timing shares a physical four-request generation batch; do not sum it as unique GPU time or interpret input reuse as reasoning gain.",
            "All48 opportunities are exposed development data, not independent confirmation; thresholds are separate.",
        ],
    }
    for name, value in [
        ("CALLS.json", calls),
        ("TARGETS.json", target_rows),
        ("TABLES.json", tables),
        ("PAIRS.json", pairs),
        ("VALIDATION.json", summary),
    ]:
        save(output / name, value)
    print(json.dumps(summary))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-unlaunched", action="store_true")
    args = parser.parse_args()
    verify(args.batch.resolve(), args.output.resolve(), args.allow_unlaunched)
