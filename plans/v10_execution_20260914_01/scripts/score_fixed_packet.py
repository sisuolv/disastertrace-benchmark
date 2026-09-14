"""All-opportunity paired E/F scoring; original and derived systems stay separate."""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from disastertrace.monitoring_fixed_v1.contracts import EvidenceBundle
from disastertrace.monitoring_v1.fixed_packet import parse
from disastertrace.monitoring_v1.regional_calibration_v2 import coherent_cdf
from disastertrace.monitoring_v1.slot_forecast import predict_from_slots
from disastertrace.monitoring_v1.spool_backend import digest, publish, read


def observation(batch, model, cid):
    if model != "Qwen/Qwen3.8-27B":
        p = batch / "api/observations" / (model + "__" + cid + ".json")
        return read(p) if p.exists() else {"state": "MISSING_OBSERVATION"}
    found = list((batch / "gpu").glob("worker_*/" + cid + ".response.json"))
    if len(found) > 1:
        raise ValueError("Duplicate local response for one registered call")
    if not found:
        return {"state": "MISSING_OBSERVATION"}
    r = read(found[0])
    request = found[0].with_name(cid + ".request.json")
    if digest(request) != r["request_sha256"]:
        raise ValueError("Local response/request binding mismatch")
    return {"state": "RECEIVED", "raw": r["raw"], "details": r}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    batch, out = args.batch.absolute(), args.out.absolute()
    out.mkdir(exist_ok=False)
    plan, refs = read(batch / "PLAN.json"), read(batch / "evaluator/REFERENCES.json")
    for rel, sha in plan["files"].items():
        if digest(batch / rel) != sha:
            raise ValueError("Frozen packet study changed")
    models = [*plan["api_models"], "Qwen/Qwen3.8-27B"]
    banks = {
        r: read(batch / "banks" / (r + ".json"))
        for r in ("new_york", "chicago", "denver")
    }
    rows, cdf_groups = [], defaultdict(list)
    for model in models:
        for task in plan["tasks"]:
            reference = refs[task["packet_id"]]
            response = observation(batch, model, task["call_id"])
            row = {
                **task,
                "model": model,
                "capture_state": response["state"],
                "valid": False,
                "E_correct": False,
                "E_composed_correct": False,
                "slots_correct": False,
                "model_F": reference["FOLLOW"],
                "FOLLOW": reference["FOLLOW"],
                "native_program_F": reference["native_program"],
                "model_slots_F": reference["FOLLOW"],
                "future_value": reference["future"]["value"],
                "future_status": reference["future"]["status"],
                "reference_E": reference["fact_truth"],
                "reference_slots": reference["slots"],
            }
            if response["state"] == "RECEIVED":
                details = response["details"]
                row["elapsed_seconds"] = details["seconds"]
                row["ended_with_eos"] = details["ended_with_eos"]
                row["timely"] = details["seconds"] + 0.002 < 600
                try:
                    answer = parse(
                        response["raw"],
                        task["query_ids"],
                        task["acquired_ids"],
                        task["reasoning"],
                    )
                    row["answer"] = answer
                    row["valid"] = bool(row["ended_with_eos"] and row["timely"])
                    if row["valid"]:
                        row["model_F"] = answer["probability"]
                        row["E_correct"] = (
                            answer["fact_truth"] == reference["fact_truth"]
                        )
                        if task["reasoning"] == "slotwise":
                            row["E_composed_correct"] = (
                                answer["composed_aggregate"] == reference["fact_truth"]
                            )
                            row["slots_correct"] = answer["slots"] == reference["slots"]
                            bundle = EvidenceBundle.restore(
                                read(batch / "bundles" / (task["packet_id"] + ".json"))
                            )
                            content = bundle.policy_view()["baseline"]["content"]
                            try:
                                forecast = predict_from_slots(
                                    banks[task["region"]],
                                    content["legacy_target_contract"],
                                    content["native_taf"],
                                    task["query_ids"],
                                    task["acquired_ids"],
                                    answer["slots"],
                                )
                                row["model_slots_F"] = forecast["probability"]
                                row["model_slots_details"] = forecast
                            except ValueError:
                                row["model_slots_rejected"] = (
                                    "unread_slot_or_mapping_contract"
                                )
                except (ValueError, TypeError, KeyError) as exc:
                    row["parse_error"] = type(exc).__name__
            row["F_fallback"] = not row["valid"]
            cdf_groups[
                (
                    model,
                    task["reasoning"],
                    task["cohort"],
                    task["condition"],
                    task["information_id"],
                )
            ].append(row)
            rows.append(row)
    methods = ("FOLLOW", "native_program_F", "model_F", "model_slots_F")
    coherence, incomplete = [], []
    for key, group in cdf_groups.items():
        group.sort(key=lambda r: r["threshold"])
        if len(group) != 2 or [r["threshold"] for r in group] != [1000, 5000]:
            incomplete.append(
                {"group": list(key), "thresholds": [r["threshold"] for r in group]}
            )
            continue
        for method in methods:
            if method == "model_slots_F" and key[1] != "slotwise":
                continue
            values = [r[method] for r in group]
            projected = coherent_cdf(values, [r["information_id"] for r in group])
            coherence.append(
                {
                    "group": list(key),
                    "method": method,
                    "original": values,
                    "projected": projected,
                    "crossing": values[0] > values[1],
                }
            )
            for row, p in zip(group, projected, strict=True):
                row[method + "_coherent"] = p
    groups, totals = defaultdict(list), Counter()
    for row in rows:
        key = "__".join(
            [row["model"], row["reasoning"], row["cohort"], row["condition"]]
        )
        groups[key].append(row)
        totals[row["capture_state"]] += 1
    summaries = {}
    for key, group in groups.items():
        settled = [
            r
            for r in group
            if r["future_status"] == "mature" and r["future_value"] is not None
        ]
        item = {
            "registered": len(group),
            "settled": len(settled),
            "missing_future": len(group) - len(settled),
            "positive": sum(r["future_value"] for r in settled),
            "valid": sum(r["valid"] for r in group),
            "E_correct": sum(r["E_correct"] for r in group),
            "always_unknown_E": sum(r["reference_E"] == "unknown" for r in group),
            "F_fallbacks": sum(r["F_fallback"] for r in group),
            "E_composed_correct": sum(r["E_composed_correct"] for r in group),
            "slots_correct": sum(r["slots_correct"] for r in group),
            "unread_slot_claims": sum(
                bool(r.get("answer", {}).get("unread_slot_claims")) for r in group
            ),
        }
        losses = {}
        for method in methods:
            if method == "model_slots_F" and group[0]["reasoning"] != "slotwise":
                continue
            for suffix in ("", "_coherent"):
                name = method + suffix
                available = [r for r in settled if name in r]
                losses[name] = {
                    "n": len(available),
                    "brier": sum((r[name] - r["future_value"]) ** 2 for r in available)
                    / len(available)
                    if available
                    else None,
                }
        item["losses"] = losses
        summaries[key] = item
    with (out / "ROWS.jsonl").open("x") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
    publish(out / "COHERENCE.json", {"rows": coherence, "incomplete_pairs": incomplete})
    publish(
        out / "RESULT.json",
        {
            "scope": plan["statistical_unit"],
            "capture_states": dict(totals),
            "registered_model_answers": len(rows),
            "underlying_opportunities": plan["underlying_opportunities"],
            "groups": summaries,
            "incomplete_coherence_pairs": len(incomplete),
            "confirmation_opened": False,
            "model_slot_aggregation_is_separate_from_F_count_mapping": True,
            "timing": "same lawful frozen packet with 600s response budget; not end-to-end active session",
        },
    )
    print(
        json.dumps(
            {
                "rows": len(rows),
                "groups": len(groups),
                "states": totals,
                "incomplete_pairs": len(incomplete),
            }
        )
    )


if __name__ == "__main__":
    main()
