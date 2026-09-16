"""Read completed selector traces without replay, outcome access or API requests."""
import hashlib
import json
import statistics
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STAGE = ROOT / "stage_C"


def read(path):
    return json.loads(path.read_text())


def main():
    inputs = {}

    def bound_read(path):
        raw = path.read_bytes()
        inputs[str(path)] = hashlib.sha256(raw).hexdigest()
        return json.loads(raw)

    intent = bound_read(STAGE / "INTENT.json")
    counts, options, patterns, sources = Counter(), Counter(), Counter(), Counter()
    elapsed, cases = [], []
    for item in intent["cases"]:
        case = STAGE / item["case"]
        result = bound_read(case / "LLM_SELECTOR_RESULT.json")
        if not result["passed"]:
            raise ValueError("Selector case is not complete")
        report = bound_read(case / "LLM_SELECTOR/FORMAL_REPORT.json")
        requests = {}
        for path in (case / "spool").glob("*.request.json"):
            request = bound_read(path)
            if request["call_id"] in requests:
                raise ValueError("Duplicate selector call request")
            requests[request["call_id"]] = request
        calls = report["selector_calls"]
        if set(requests) != {call["call_id"] for call in calls}:
            raise ValueError("Request and completed-call rosters differ")
        legal = 0
        for call in calls:
            request = requests[call["call_id"]]["request"]
            catalog = request["queries"]
            options[len(catalog)] += 1
            counts["all_calls"] += 1
            counts["option_references"] += len(catalog)
            counts["multi_target_option_references"] += sum(
                len(q["serves_target_handles"]) > 1 for q in catalog.values()
            )
            profiles = {
                json.dumps({
                    "cost": q["metadata"]["archive_cost"],
                    "latency_ms": q["metadata"]["latency_ms"],
                    "target_count": len(q["serves_target_handles"]),
                }, sort_keys=True)
                for q in catalog.values()
            }
            counts["nonempty_catalogs_with_same_cost_latency_target_count"] += bool(catalog) and len(profiles) == 1
            elapsed.append((call["completed_at"] - call["started_at"]) / 1e6)
            slots = request["fixed_forecast_slots"].values()
            counts["calls_completing_after_first_fixed_forecast_slot"] += bool(slots) and call["completed_at"] > min(slots)
            if call.get("execution_status") or call.get("response_error"):
                counts["invalid_calls"] += 1
                continue
            legal += 1
            counts["valid_calls"] += 1
            selected = call["selection"]["query_order"]
            if len(selected) != len(set(selected)) or not set(selected) <= set(catalog):
                raise ValueError("A reported valid selection has illegal handles")
            patterns["empty" if not selected else "all_available" if set(selected) == set(catalog) else "proper_subset"] += 1
            counts["valid_selected_handle_references"] += len(selected)
            counts["valid_nonempty_orders_different_from_catalog_order"] += bool(selected) and selected != [h for h in catalog if h in selected]
        receipts = report["source_receipts"]
        sources.update(receipt["source_status"] for receipt in receipts)
        counts["actual_source_receipts"] += len(receipts)
        counts["program_forecasts"] += sum(call["head"] == "program" for call in report["calls"])
        cases.append({
            "case": item["case"], "calls": len(calls), "valid_calls": legal,
            "actual_source_receipts": len(receipts),
            "unique_acquired_query_ids": len({r["query_id"] for r in receipts}),
            "resource_spent": report["resource_spent"],
            "source_statuses": dict(Counter(r["source_status"] for r in receipts)),
        })
    output = {
        "scope": "posthoc behavior diagnostic of existing completed selector traces",
        "registered_cases": len(cases), "counts": dict(counts),
        "option_count_histogram": dict(options), "valid_selection_patterns": dict(patterns),
        "actual_source_statuses": dict(sources), "cases": cases,
        "selector_lifecycle_seconds": {
            "min": min(elapsed), "median": statistics.median(elapsed), "max": max(elapsed),
            "interpretation": "dispatch to observed durable response; not provider compute time",
        },
        "outcomes_accessed": False, "requests_sent": 0, "policy_replays": 0,
        "invalid_answers_reinterpreted": False, "input_sha256": inputs,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "limitations": [
            "Selected handles are intentions, not proof of completed acquisitions.",
            "Equal cost/latency/fanout does not imply equal predictive information.",
            "Valid-only behavior is not a valid-only performance scoreboard.",
            "No causal claim about why a model chose all options or failed schema.",
        ],
    }
    with (ROOT / "SELECTOR_BEHAVIOR_DIAGNOSTIC.json").open("x") as stream:
        json.dump(output, stream, indent=2, allow_nan=False)
    print(json.dumps({k: v for k, v in output.items() if k not in {"input_sha256", "cases"}}, indent=2))


if __name__ == "__main__":
    main()
