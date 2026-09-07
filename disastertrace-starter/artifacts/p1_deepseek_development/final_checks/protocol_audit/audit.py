"""Independent read-only identity and budget arithmetic checks for the P1 run."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
ARTIFACTS = ROOT / "artifacts/p1_deepseek_development"
LIVE = ROOT / "work/p1-deepseek-development-v1"


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fingerprint(value):
    content = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    return hashlib.sha256(content.encode()).hexdigest()


def decimal(value):
    return Decimal(str(value))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("initial", "final"), required=True)
    args = parser.parse_args()
    destination = Path(__file__).with_name(args.stage + ".json")
    if destination.exists():
        raise ValueError("audit output exists")
    checks = []

    def check(name, actual, expected):
        checks.append({"name": name, "actual": actual, "expected": expected, "passed": actual == expected})

    protected = read(ARTIFACTS / "historical_inventory_before.json")["files"]
    check("protected_file_count", len(protected), 177)
    for path, expected in protected.items():
        check("protected:" + path, digest(ROOT / path), expected)

    manifest_path = ARTIFACTS / "experiment.json"
    manifest = read(manifest_path)
    check("manifest_fingerprint", fingerprint({k: v for k, v in manifest.items() if k != "experiment_id"}), manifest["experiment_id"])
    check("live_manifest_copy", digest(LIVE / "experiment.json"), digest(manifest_path))
    for name, key in (("run_experiment.py", "runner_sha256"), ("report_results.py", "reporter_sha256")):
        check("frozen:" + name, digest(ARTIFACTS / name), manifest[key])
    for label in ("provider_config", "rates"):
        check("frozen:" + label, digest(manifest[label + "_path"]), manifest[label + "_sha256"])
    check("frozen:protocol", digest(manifest["protocol"]["path"]), manifest["protocol"]["sha256"])
    for path, expected in manifest["offline_checks"].items():
        check("frozen:offline:" + path, digest(ROOT / path), expected)
    check("frozen:dataset_audit", digest(ARTIFACTS / "preparation/dataset_audit.json"), manifest["dataset_audit_sha256"])
    check("frozen:data_equality", digest(ARTIFACTS / "preparation/data_equality.json"), manifest["frozen_data_equality_sha256"])
    rates = read(manifest["rates_path"])
    check("official_pricing_source", digest(rates["source"]["path"]), rates["source"]["sha256"])

    build = Path(manifest["build_path"])
    build_manifest = read(build / "manifest.json")
    check("build_identity", build_manifest["build_id"], manifest["build_id"])
    for path, expected in build_manifest["files"].items():
        check("build_artifact:" + path, digest(build / path), expected)
    implementation = read(build / "implementation.json")
    check("implementation_identity", implementation["implementation_id"], manifest["implementation_id"])
    check("implementation_fingerprint", fingerprint({k: v for k, v in implementation.items() if k != "implementation_id"}), manifest["implementation_id"])
    for filename, expected in implementation["files"].items():
        check("current_implementation:" + filename, digest(ROOT / "src/disastertrace/automated" / filename), expected)

    execution = read(LIVE / "execution.json")
    ledger = read(LIVE / "budget_ledger.json")
    check("live_experiment_binding", execution["experiment_id"], manifest["experiment_id"])
    check("live_experiment_file_hash", execution["experiment_file_sha256"], digest(manifest_path))
    check("live_runner_binding", execution["runner_sha256"], manifest["runner_sha256"])
    check("ledger_experiment_binding", ledger["experiment_id"], manifest["experiment_id"])
    check("ledger_budget_binding", ledger["budget"], manifest["budget"])
    check("planned_matrix", execution["planned_checkpoints_total"], 90)

    budget = manifest["budget"]
    attempts = ledger["attempts"]
    input_rate = decimal(budget["peak_input_per_million"])
    output_rate = decimal(budget["peak_output_per_million"])
    reservation = (decimal(budget["prompt_reservation_tokens"]) * input_rate + 4096 * output_rate) / 1000000
    check("pending_reservation_formula", str(reservation), "0.46678016")
    computed_spent = Decimal(0)
    computed_pending = Decimal(0)
    for index, attempt in enumerate(attempts, 1):
        check(f"attempt:{index}:sequence", attempt["attempt_number"], index)
        check(f"attempt:{index}:reservation", decimal(attempt["reserved_usd"]), reservation)
        check(f"attempt:{index}:output_cap", attempt["requested_output_tokens"], 4096)
        check(f"attempt:{index}:request_size", attempt["request_bytes"] <= budget["max_request_bytes"], True)
        if not attempt["reservation_released"]:
            computed_pending += decimal(attempt["reserved_usd"])
        if attempt.get("conservative_reported_cost_usd") is not None:
            usage = attempt["usage"]
            charge = (usage["prompt_tokens"] * input_rate + usage["completion_tokens"] * output_rate) / 1000000
            check(f"attempt:{index}:charge", decimal(attempt["conservative_reported_cost_usd"]), charge)
            computed_spent += charge
    check("ledger_attempts_count", ledger["provider_attempts_started"], len(attempts))
    check("ledger_reserved_output", ledger["requested_output_tokens_reserved_total"], len(attempts) * 4096)
    check("ledger_spent", decimal(ledger["conservative_reported_cost_usd"]), computed_spent)
    check("ledger_pending", decimal(ledger["pending_reservation_usd"]), computed_pending)
    check("ledger_spent_plus_pending", decimal(ledger["spent_plus_pending_usd"]), computed_spent + computed_pending)
    check("ledger_remaining", decimal(ledger["allowance_remaining_after_reservations_usd"]), decimal(budget["allowance"]) - computed_spent - computed_pending)
    check("ledger_within_allowance", computed_spent + computed_pending <= decimal(budget["allowance"]), True)

    observed = {"ledger_snapshot_updated_at": ledger["updated_at"], "attempts": len(attempts), "execution_status": execution["status"]}
    if args.stage == "final":
        check("execution_finished", execution["status"], "completed")
        check("final_attempts", len(attempts), 90)
        check("final_completions", ledger["provider_completions_received"], 90)
        check("final_pending", computed_pending, Decimal(0))
        check("final_not_halted", ledger["halted"], False)
        check("final_assumptions", ledger["conditional_budget_assumptions_satisfied"], True)
        check("final_guard_denials", ledger["guard_denials_before_provider"], 0)
        check("method_attempts", dict(Counter(a["method"] for a in attempts)), {method: 30 for method in manifest["methods"]})
        index = {(a["method"], a["request_sha256"]): a for a in attempts}
        check("unique_admitted_requests", len(index), 90)
        total_usage = Counter()
        total_cost = Decimal(0)
        start = datetime.fromisoformat(rates["window"]["start_utc"]).timestamp()
        end = datetime.fromisoformat(rates["window"]["end_utc"]).timestamp()
        check("registered_before_requests", datetime.fromisoformat(manifest["registered_at"]) <= datetime.fromisoformat(attempts[0]["started_at"]), True)
        for method in manifest["methods"]:
            location = LIVE / "runs" / method
            requests = rows(location / "collection/requests.jsonl")
            outcomes = rows(location / "collection/outcomes.jsonl")
            responses = rows(location / "collection/responses.jsonl")
            trace = rows(location / "imported_run/trace.jsonl")
            check(method + ":counts", [len(requests), len(outcomes), len(responses), len(trace)], [30, 30, 30, 30])
            check(method + ":audit", read(location / "collection_audit.json")["valid"], True)
            check(method + ":unique_checkpoints", len({(r["episode_id"], r["checkpoint_id"]) for r in requests}), 30)
            check(method + ":checkpoint_keys", fingerprint([{"episode_id": r["episode_id"], "checkpoint_id": r["checkpoint_id"]} for r in requests]), manifest["expected_checkpointkeys_sha256"])
            score = read(LIVE / "rescores" / method / "score_v2.json")
            expected_denominators = {"schema_success": 30, "state_accuracy": 150, "known_grounded_accuracy": 96, "unknown_accuracy": 54, "gold_transition_success": 64, "gold_preservation": 56, "provenance_refresh": 8}
            check(method + ":fixed_denominators", {name: score["metrics"][name]["denominator"] for name in expected_denominators}, expected_denominators)
            for row in outcomes:
                meta = row["metadata"]
                admitted = index[(method, row["request_sha256"])]
                usage = meta["usage"]
                label = method + ":" + row["episode_id"] + ":" + row["checkpoint_id"]
                check(label + ":ledger_usage", admitted["usage"], {key: usage[key] for key in ("prompt_tokens", "completion_tokens", "total_tokens")})
                check(label + ":response_hash", admitted["raw_response_sha256"], row["raw_response_sha256"])
                check(label + ":model", meta["response_model"], "deepseek-v4-flash")
                check(label + ":no_retry", meta["automatic_retry"], False)
                check(label + ":attempt_count", meta["attempt_count"], 1)
                check(label + ":output_limit", usage["completion_tokens"] <= 4096, True)
                check(label + ":cache_consistency", usage["prompt_cache_hit_tokens"] + usage["prompt_cache_miss_tokens"], usage["prompt_tokens"])
                wire = json.loads(meta["raw_response_body"])
                check(label + ":pricing_window", start <= wire["created"] < end, True)
                for key in ("prompt_tokens", "completion_tokens", "total_tokens", "prompt_cache_hit_tokens", "prompt_cache_miss_tokens"):
                    total_usage[key] += usage[key]
                total_usage["reasoning_tokens"] += usage["completion_tokens_details"]["reasoning_tokens"]
                price = rates["per_million_tokens"]
                total_cost += (usage["prompt_cache_hit_tokens"] * decimal(price["input_cache_hit"]) + usage["prompt_cache_miss_tokens"] * decimal(price["input_cache_miss"]) + usage["completion_tokens"] * decimal(price["output"])) / 1000000
        observed.update(total_usage=dict(total_usage), actual_window_cache_aware_cost_estimate_usd=str(total_cost), conservative_guard_cost_usd=str(computed_spent))

    result = {"schema_version": "p1_independent_protocol_audit_v1", "stage": args.stage, "recorded_at": datetime.now(timezone.utc).isoformat(), "script_sha256": digest(__file__), "command": [".venv/bin/python", str(Path(__file__).relative_to(ROOT)), "--stage", args.stage], "protected_files": len(protected), "checks": checks, "observed": observed, "passed": all(c["passed"] for c in checks), "new_model_api_calls": 0}
    destination.write_text(json.dumps(result, indent=2, default=str) + "\n")
    print(json.dumps({"passed": result["passed"], "checks": len(checks), "failed": [c["name"] for c in checks if not c["passed"]], "output": str(destination), "observed": observed}))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
