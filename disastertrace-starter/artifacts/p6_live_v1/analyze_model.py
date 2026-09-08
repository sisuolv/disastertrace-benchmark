"""Read-only attribution of the audited paired model run; no scoring-rule changes."""

from collections import Counter, defaultdict
from pathlib import Path

from disastertrace.automated.common import canonical, fingerprint
from disastertrace.controlled.compiler import reference_at
from disastertrace.controlled.schema import FIELDS, parse_decision
from disastertrace.local_eval.storage import digest, inventory, read, seal, verify_seal, write
from disastertrace.post_p5.citations import classify_field
from disastertrace.repeat_live import package

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]


def main():
    execution, run = HERE / "execution_live_02", PROJECT / "work/p6-live-v1/model"
    report = HERE / "reports/model_review_v2"
    verify_seal(report)
    audited, scores, traces = (
        read(report / (name + ".json")) for name in ("audit", "scores", "trace")
    )
    plan, datasets, slots = package.verify(execution)
    if (
        not audited["model_result"]
        or audited["execution_id"] != plan["execution_id"]
        or inventory(run) != audited["run_files"]
    ):
        raise ValueError("model report is not bound to the current raw evidence")
    episodes = {(c, e["episode_id"]): e for c, eps in datasets.items() for e in eps}
    seen, previous, earlier_gold = defaultdict(list), {}, defaultdict(lambda: defaultdict(list))
    rows, examples, counts, categories = [], [], Counter(), Counter()
    by_cell = defaultdict(Counter)
    for trace in traces:
        ep = episodes[trace["condition"], trace["episode_id"]]
        gold = reference_at(ep, trace["checkpoint_id"])
        prediction = parse_decision(trace["raw_response"]) if trace["status"] == "ok" else None
        identity = {
            k: trace[k]
            for k in (
                "slot_id",
                "slot_index",
                "condition",
                "repeat",
                "method",
                "base_episode_id",
                "checkpoint_id",
                "trajectory_id",
                "pair_id",
            )
        }
        cell = (trace["condition"], trace["repeat"], trace["method"])
        for field in FIELDS:
            prior = previous.get(trace["trajectory_id"])
            attribution = classify_field(
                trace["request"],
                field,
                prediction["state"][field] if prediction else None,
                gold["state"][field],
                all_record_ids=[r["record_id"] for r in ep["records"]],
                previous=prior["state"][field] if prior else None,
                earlier_correct_refs=earlier_gold[trace["trajectory_id"]][field],
                status=trace["status"],
            )
            row = {
                **identity,
                "field": field,
                "expected": gold["state"][field],
                "predicted": prediction["state"][field] if prediction else None,
                **attribution,
            }
            rows.append(row)
            counts.update(
                fields=1,
                value_correct=int(attribution["legacy_value_correct"]),
                grounded_correct=int(attribution["legacy_grounded_correct"]),
                citation_only_errors=int(attribution["citation_only_error"]),
                value_status_or_invalid_errors=int(not attribution["legacy_value_correct"]),
            )
            if attribution["primary_error"]:
                categories[attribution["primary_error"]] += 1
                by_cell[cell][attribution["primary_error"]] += 1
                if len(examples) < 12:
                    examples.append(row)
            earlier_gold[trace["trajectory_id"]][field].extend(gold["state"][field]["evidence"])
        if prediction:
            previous[trace["trajectory_id"]] = prediction
        seen[trace["pair_id"]].append(trace)
    if counts["grounded_correct"] != scores["counts"]["grounded_correct"]:
        raise ValueError("attribution does not reconcile to the frozen primary field score")
    agreement = defaultdict(Counter)
    for pair in seen.values():
        if len(pair) != 2:
            continue
        left, right = pair
        agreement[left["checkpoint_id"]].update(
            pairs=1,
            identical_requests=int(left["request"] == right["request"]),
            identical_final_text=int(left["raw_response"] == right["raw_response"]),
        )
    summary = {
        "execution_id": plan["execution_id"],
        "audit_id": audited["audit_id"],
        "counts": dict(counts),
        "primary_error_categories": dict(categories),
        "by_condition_repeat_method": [
            {"condition": c, "repeat": r, "method": m, "errors": dict(v)}
            for (c, r, m), v in sorted(by_cell.items())
        ],
        "paired_request_and_final_agreement_by_checkpoint": dict(agreement),
        "planned_field_opportunities": len(slots) * 4,
        "received_field_opportunities": len(rows),
        "example_selection": "first twelve erroneous fields in frozen schedule order",
        "changes_primary_scores": False,
        "additional_model_calls": 0,
        "analysis_script_sha256": digest(__file__),
    }
    summary["analysis_id"] = fingerprint(summary)
    output = HERE / "analysis"
    output.mkdir(parents=True, exist_ok=False)
    with (output / "fields.jsonl").open("x") as stream:
        for row in rows:
            stream.write(canonical(row) + "\n")
    write(output / "summary.json", summary)
    write(output / "examples.json", examples)
    seal(output)
    print({k: v for k, v in summary.items() if k != "by_condition_repeat_method"}, flush=True)


if __name__ == "__main__":
    main()
