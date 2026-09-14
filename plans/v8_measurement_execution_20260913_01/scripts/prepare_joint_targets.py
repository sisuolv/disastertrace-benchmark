"""Prepare X09 shared-input pairs, references and token-checked unsent requests."""

import argparse
import copy
import datetime
import hashlib
import json
import random
import shutil
from collections import defaultdict
from pathlib import Path

from analyze_evidence_witnesses import interval_witness
from disastertrace.monitoring_fixed_v1.contracts import EvidenceBundle, fingerprint
from disastertrace.monitoring_fixed_v1.joint_targets import (
    build_joint_context,
    joint_messages,
    parse_joint_response,
)


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def main():
    from transformers import AutoTokenizer

    parser = argparse.ArgumentParser()
    parser.add_argument("--execution", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    execution, output = args.execution.resolve(), args.output.resolve()
    original = execution / "gpu/large_diagnostic_02"
    old_plan = read(original / "PLAN.json")
    model = old_plan["models"]["qwen235b_fp8"]
    records = read(
        execution / "reports/large_model_diagnostic_01/qwen235b_fp8/RECORDS.json"
    )
    qualified = read(execution / "reports/large_model_diagnostic_01/VALIDATION.json")
    assert qualified["integrity_passed"] and qualified["all_planned_completed"]
    output.mkdir(parents=True, exist_ok=False)
    policy_dir, reference_dir = output / "policy", output / "evaluator"
    policy_dir.mkdir()
    reference_dir.mkdir()
    source = output / "source"
    for module in ("monitoring_fixed_v1", "monitoring_v1"):
        shutil.copytree(
            execution.parents[1] / "disastertrace-starter/src/disastertrace" / module,
            source / "disastertrace" / module,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
    (source / "disastertrace/__init__.py").write_text(
        '"""Frozen X09 development contracts."""\n'
    )
    shutil.copyfile(Path(__file__), source / Path(__file__).name)
    shutil.copyfile(
        Path(__file__).with_name("analyze_evidence_witnesses.py"),
        source / "analyze_evidence_witnesses.py",
    )
    groups = defaultdict(list)
    original_bindings = {}
    for record in records:
        if (
            record["input_kind"] != "bundle"
            or record["head"] != "e_only"
            or record["condition"] not in {"common_only", "all_registered"}
        ):
            continue
        path = original / "policy" / (record["call_id"] + ".json")
        request = read(path)
        bundle = EvidenceBundle.restore(request["input"])
        row = bundle.policy_view()
        key = (
            row["cutoff"],
            row["target"]["physical_start"],
            row["target"]["threshold"],
            record["condition"],
        )
        groups[key].append((record, bundle))
        original_bindings[str(path.relative_to(execution))] = sha(path)
    assert len(groups) == 32 and all(len(rows) == 3 for rows in groups.values())
    tokenizer = AutoTokenizer.from_pretrained(model["directory"], local_files_only=True)
    tasks, reference, cohorts, program_checks = [], {}, [], []
    total_tokens = 0
    for key, records_and_bundles in sorted(groups.items()):
        context = build_joint_context(
            [b for _, b in records_and_bundles], access_mode="shared_disclosed_union"
        )
        group_id = fingerprint({"cohort": key, "context": context["context_sha256"]})[
            :24
        ]
        by_target = {r["target_id"]: r for r, _ in records_and_bundles}
        expected = {}
        for row in context["targets"]:
            tid = row["target"]["target_id"]
            registered = row["baseline"]["content"]["E_question"]["query_ids"]
            witness = interval_witness(
                {
                    "baseline": row["baseline"],
                    "assets": [
                        a
                        for a in context["shared_sources"]
                        if a["content"]["query_id"] in registered
                    ],
                }
            )
            assert witness["independent_expected_E"] == by_target[tid]["e_expected"]
            expected[tid] = {
                "opportunity_id": row["opportunity_id"],
                "expected_E": witness["independent_expected_E"],
                "baseline_probability": row["baseline"]["forecast"]["value"],
                "target_contract_hash": row["baseline"]["forecast"][
                    "target_contract_hash"
                ],
                "disclosed_witness": witness,
            }
        tids = sorted(expected)
        reference[group_id] = expected
        cohorts.append(
            {
                "group_id": group_id,
                "cutoff": key[0],
                "physical_start": key[1],
                "threshold_m": key[2],
                "condition": key[3],
                "target_ids": tids,
                "context_sha256": context["context_sha256"],
                "shared_sources": len(context["shared_sources"]),
            }
        )
        for head in ("e_only", "f_only", "joint"):
            control_context = None
            for scope, wanted in [
                ("multi", tids),
                *[("single", [tid]) for tid in tids],
            ]:
                call_id = fingerprint(
                    {"group_id": group_id, "head": head, "targets": wanted}
                )[:24]
                messages = joint_messages(context, wanted, head=head)
                visible = json.loads(messages[1]["content"])["context"]
                if control_context is None:
                    control_context = visible
                assert visible == control_context
                token_ids = tokenizer.apply_chat_template(
                    messages,
                    tokenize=True,
                    add_generation_prompt=True,
                    enable_thinking=False,
                )
                assert len(token_ids) <= 15360
                total_tokens += len(token_ids)
                task = {
                    "call_id": call_id,
                    "group_id": group_id,
                    "input_kind": "joint_target_packet",
                    "head": head,
                    "scope": scope,
                    "answer_target_ids": wanted,
                    "messages_sha256": fingerprint(messages),
                    "context_sha256": context["context_sha256"],
                    "logical_started_at": key[0] - 60_000_000,
                    "logical_cutoff": key[0],
                    "models": {
                        "qwen235b_fp8": {
                            "input_tokens": len(token_ids),
                            "input_ids_sha256": fingerprint(token_ids),
                        }
                    },
                }
                assert (
                    max(
                        [r["baseline"]["available_at"] for r in context["targets"]]
                        + [a["completed_at"] for a in context["shared_sources"]]
                    )
                    <= task["logical_started_at"]
                )
                save(
                    policy_dir / (call_id + ".json"),
                    {
                        "schema": "disastertrace.joint_target_request.v1",
                        "call_id": call_id,
                        "messages": messages,
                        "context": context,
                        "answer_target_ids": wanted,
                        "head": head,
                    },
                )
                answer = []
                for tid in wanted:
                    item = {"target_id": tid}
                    if head in {"e_only", "joint"}:
                        item["fact_truth"] = {
                            "supported": "true",
                            "refuted": "false",
                            "undetermined": "unknown",
                            "inconsistent": "conflict",
                        }[expected[tid]["expected_E"]]
                    if head in {"f_only", "joint"}:
                        item["probability"] = expected[tid]["baseline_probability"]
                    answer.append(item)
                raw = json.dumps({"answers": answer})
                parsed = parse_joint_response(raw, context, wanted, head=head)
                assert set(parsed) == set(wanted)
                program_checks.append(
                    {
                        "call_id": call_id,
                        "origin": "program_contract_rehearsal",
                        "target_count": len(parsed),
                        "raw": raw,
                    }
                )
                tasks.append(task)
    assert len(tasks) == 384 and len({row["call_id"] for row in tasks}) == 384
    random.Random(20260913).shuffle(tasks)
    save(reference_dir / "E_REFERENCES.json", reference)
    save(reference_dir / "COHORTS.json", cohorts)
    save(reference_dir / "ORIGINAL_INPUT_HASHES.json", original_bindings)
    shutil.copyfile(
        original / "evaluator/CANONICAL_OUTCOMES.json",
        reference_dir / "CANONICAL_OUTCOMES.json",
    )
    save(output / "PROGRAM_REHEARSAL.json", program_checks)
    plan = {
        "schema": "disastertrace.joint_targets_offline_candidate.v1",
        "frozen_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "models": {"qwen235b_fp8": copy.deepcopy(model)},
        "tasks": tasks,
        "batch_size": 4,
        "max_concurrent_gpus": 4,
        "generation": old_plan["generation"],
        "engine": old_plan["engine"],
        "runtime_versions": old_plan["runtime_versions"],
        "expected_benchmark_calls_per_model": 384,
        "compatibility_calls_per_model": 1,
        "maximum_total_calls": 385,
        "unique_opportunities": 48,
        "cohorts_per_condition": 16,
        "denominators": "Each scope/head/condition has48 target answers; multi96 calls versus single288 calls across all cells. These remain48 repeated development opportunities.",
        "information_control": "Same whole context and same system instruction within each head/cohort; only answer_target_ids changes between the three separate requests and one multi-target request.",
        "authorization": "Explicit new shared-disclosed-union fixed-input condition; not a private-session sharing effect or a new paid source retrieval.",
        "comparison": "X09 multi-target computation/input repetition and answer quality; no adaptive allocation, operational speedup or joint-probability-calibration claim.",
        "scoring_policy": "Strict per-request schema; an invalid multi-target response fails every requested E target and keeps each registered F baseline. Late/unfinished responses retain all requested target denominators. No retries or selective replacement.",
        "source_data": "Reuses the exposed2025-02-03 fixed-input native Bay data; no reserved confirmation is opened.",
        "generation_enabled": False,
        "launch_gate": "Separate one-use live freeze and launch; current adaptive job must terminate first, four-GPU maximum, and enough time must remain for independent scoring before02:45:50UTC.",
        "new_model_calls": 0,
        "files": {
            str(p.relative_to(output)): sha(p)
            for p in sorted(output.rglob("*"))
            if p.is_file()
        },
    }
    save(output / "PLAN.json", plan)
    save(
        output / "VALIDATION.json",
        {
            "passed": True,
            "plan_sha256": sha(output / "PLAN.json"),
            "unsent_requests": 384,
            "program_rehearsals": len(program_checks),
            "unique_opportunities": 48,
            "context_pairs_checked": 96,
            "maximum_input_tokens": max(
                t["models"]["qwen235b_fp8"]["input_tokens"] for t in tasks
            ),
            "total_proposed_input_tokens": total_tokens,
            "maximum_requested_output_tokens": 384 * 512,
            "new_model_calls": 0,
            "new_source_requests": 0,
            "all_three_single_requests_and_one_multi_request_share_context": True,
            "native_E_references_match_original_scorer": True,
            "live_launch_performed": False,
        },
    )
    print(json.dumps(read(output / "VALIDATION.json")))


if __name__ == "__main__":
    main()
