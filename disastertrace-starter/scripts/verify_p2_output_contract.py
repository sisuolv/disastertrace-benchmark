"""Compare frozen P2 task semantics, opportunities and unsent contract projections."""

import argparse
from copy import deepcopy
from pathlib import Path

from disastertrace.automated.common import (
    canonical,
    file_hash,
    fingerprint,
    write_json,
    write_jsonl,
)
from disastertrace.automated.provider import ProviderConfig
from disastertrace.automated.run_store import read_events
from disastertrace.controlled.execution import contract_version, read, verify_execution
from disastertrace.controlled.output_contract import V1, V2, identity, system_message
from disastertrace.controlled.provider_adapter import prepare
from disastertrace.controlled.scorer import METRICS

SEMANTIC_FILES = (
    "episodes.jsonl",
    "micro_fixtures.jsonl",
    "schedule.jsonl",
    "private/gold.jsonl",
    "public/initial_requests.jsonl",
    "parent_sources.jsonl",
)
SEMANTIC_MODULES = (
    "compiler.py",
    "generator.py",
    "renderer.py",
    "schema.py",
    "scorer.py",
    "public_oracle.py",
    "runtime.py",
)


def identical_files(old, new, names, *, json_content=False):
    rows = {}
    for name in names:
        before, after = file_hash(old / name), file_hash(new / name)
        if json_content:
            if canonical(read(old / name)) != canonical(read(new / name)):
                raise ValueError("score JSON content changed: " + name)
        elif before != after:
            raise ValueError("semantic bytes changed: " + name)
        rows[name] = {
            "old_sha256": before,
            "new_sha256": after,
            "comparison": "canonical_json_content" if json_content else "exact_bytes",
            **({"canonical_sha256": fingerprint(read(old / name))} if json_content else {}),
        }
    return rows


def denominators(value, prefix=""):
    result = {}
    if isinstance(value, dict):
        if {"numerator", "denominator", "value"} <= set(value):
            result[prefix] = value["denominator"]
        else:
            for key, child in value.items():
                result.update(denominators(child, prefix + "/" + key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            result.update(denominators(child, prefix + "/" + str(index)))
    return result


def checkpoint_opportunities(methods):
    count_keys = sorted({denominator for _, denominator in METRICS.values()})
    return [
        {
            "method": method,
            **{
                k: row[k]
                for k in ("episode_id", "root_id", "group_id", "family", "branch", "checkpoint_id")
            },
            "fields": sorted(row["slots"]),
            "opportunities": {key: row["counts"][key] for key in count_keys},
        }
        for method, score in sorted(methods.items())
        for row in score["per_checkpoint"]
    ]


def compare(old_execution, new_execution, old_run, old_report, new_report):
    old, new = read(old_execution / "execution.json"), verify_execution(new_execution)
    if contract_version(old) != V1 or contract_version(new) != V2:
        raise ValueError("expected a v1 baseline and v2 candidate")
    changed_keys = {
        "execution_id",
        "schema_version",
        "output_contract",
        "dataset_package_id",
        "dataset_content_id",
        "dataset_manifest",
        "source_identity",
        "registry_path",
    }
    if {k: v for k, v in old.items() if k not in changed_keys} != {
        k: v for k, v in new.items() if k not in changed_keys
    }:
        raise ValueError("non-contract execution settings changed")
    for key in ("execution_id", "dataset_package_id", "dataset_content_id", "registry_path"):
        if old[key] == new[key]:
            raise ValueError("new identity/scope required: " + key)
    if old["source_identity"]["implementation_id"] == new["source_identity"]["implementation_id"]:
        raise ValueError("new implementation identity required")
    old_data, new_data = old_execution / "dataset", new_execution / "dataset"
    semantic_files = identical_files(old_data, new_data, SEMANTIC_FILES)
    modules = identical_files(
        old_data / "implementation_source/src/disastertrace/controlled",
        new_data / "implementation_source/src/disastertrace/controlled",
        SEMANTIC_MODULES,
    )
    scores = sorted(
        str(p.relative_to(old_data)) for p in (old_data / "diagnostics").glob("*/*/score.json")
    )
    if len(scores) != 30:
        raise ValueError("all 30 program score configurations required")
    traces = [name.replace("/score.json", "/trace.jsonl") for name in scores]
    program_files = identical_files(old_data, new_data, scores, json_content=True)
    program_files.update(identical_files(old_data, new_data, traces))
    old_methods = read(old_report / "report.json")["methods"]
    new_methods = read(new_report / "report.json")["methods"]
    old_counts, new_counts = denominators(old_methods), denominators(new_methods)
    if not old_counts or old_counts != new_counts:
        raise ValueError("scoring opportunity denominators changed")
    opportunities = checkpoint_opportunities(old_methods)
    if len(opportunities) != 270 or opportunities != checkpoint_opportunities(new_methods):
        raise ValueError("checkpoint-specific scoring opportunities changed")
    rows = []
    for event in read_events(old_run):
        if event["kind"] != "reserved":
            continue
        data = event["data"]
        config = ProviderConfig.from_dict(data["prepared"]["config"])
        legacy = prepare(data["request"], config, output_contract=V1)
        candidate = prepare(data["request"], config, output_contract=V2)
        if canonical(legacy) != canonical(data["prepared"]):
            raise ValueError("legacy prepared envelope changed")
        projected = deepcopy(candidate["payload"])
        if projected["messages"][0] != {"role": "system", "content": system_message(V2)}:
            raise ValueError("candidate common system mismatch")
        projected["messages"][0] = legacy["payload"]["messages"][0]
        if projected != legacy["payload"]:
            raise ValueError("candidate changed more than the system message")
        candidate_bytes = len(candidate["raw_request"].encode())
        if candidate_bytes > new["budget"]["max_request_bytes"]:
            raise ValueError("historical-carrier projection exceeds request byte guard")
        rows.append(
            {
                "slot_index": data["slot_index"],
                "kind": "unsent_historical_carrier_projection_not_candidate_model_exposure",
                "public_request_sha256": fingerprint(data["request"]),
                "v1_prepared_sha256": legacy["request_sha256"],
                "v2_prepared_sha256": candidate["request_sha256"],
                "v1_wire_sha256": legacy["wire_payload_sha256"],
                "v2_wire_sha256": candidate["wire_payload_sha256"],
                "v1_request_bytes": len(legacy["raw_request"].encode()),
                "v2_request_bytes": candidate_bytes,
                "model_calls": 0,
            }
        )
    if len(rows) != 270 or [r["slot_index"] for r in rows] != list(range(270)):
        raise ValueError("complete ordered historical matrix required")
    result = {
        "status": "passed",
        "schema_version": "p2_output_contract_equivalence_v1",
        "old_execution_id": old["execution_id"],
        "new_execution_id": new["execution_id"],
        "output_contract": identity(V2),
        "model_calls": 0,
        "new_model_exposure": False,
        "semantic_files": semantic_files,
        "semantic_modules": modules,
        "program_files": program_files,
        "program_score_configurations_semantically_equal": len(scores),
        "program_traces_identical": len(traces),
        "metric_denominators": old_counts,
        "metric_denominator_count": len(old_counts),
        "checkpoint_opportunities": opportunities,
        "checkpoint_opportunities_count": len(opportunities),
        "legacy_exact_envelope_comparisons": len(rows),
        "system_only_wire_comparisons": len(rows),
        "projection_sha256": fingerprint(rows),
        "system_byte_increase_per_request": len(system_message(V2).encode())
        - len(system_message(V1).encode()),
        "wire_byte_increase_per_request": sorted(
            {r["v2_request_bytes"] - r["v1_request_bytes"] for r in rows}
        ),
        "largest_projected_request_bytes": max(r["v2_request_bytes"] for r in rows),
        "request_byte_limit": new["budget"]["max_request_bytes"],
        "tokens_and_empirical_v2_reliability": "unmeasured; byte lengths are not token estimates",
    }
    return result, rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("old-execution", "new-execution", "old-run", "old-report", "new-report", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    result, rows = compare(
        args.old_execution, args.new_execution, args.old_run, args.old_report, args.new_report
    )
    if args.verify:
        from disastertrace.automated.common import read_jsonl

        if result != read(args.output / "equivalence.json") or rows != read_jsonl(
            args.output / "request_comparisons.jsonl"
        ):
            raise ValueError("saved contract equivalence differs from recomputation")
    else:
        args.output.mkdir(parents=True, exist_ok=False)
        write_json(args.output / "equivalence.json", result)
        write_jsonl(args.output / "request_comparisons.jsonl", rows)
    print(
        canonical(
            {
                k: v
                for k, v in result.items()
                if k
                not in {
                    "semantic_files",
                    "semantic_modules",
                    "program_files",
                    "metric_denominators",
                    "checkpoint_opportunities",
                }
            }
        )
    )


if __name__ == "__main__":
    main()
