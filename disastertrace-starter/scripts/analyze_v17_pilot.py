"""Offline reconstruction and descriptive analysis for the bounded v17 pilot."""

from __future__ import annotations

from collections import Counter, defaultdict
import json
from pathlib import Path
import statistics


def rows(path):
    path = Path(path)
    return [json.loads(line) for line in path.read_text().splitlines() if line] if path.exists() else []


def fact_equal(actual, expected):
    if actual is None or expected is None:
        return actual == expected
    return (
        sorted(actual.get("active_source_ids", [])) == sorted(expected.get("active_source_ids", []))
        and actual.get("valid_start") == expected.get("valid_start")
        and actual.get("valid_end") == expected.get("valid_end")
        and actual.get("relation_status") == expected.get("relation_status")
    )


def mean(values):
    return sum(values) / len(values) if values else None


def analyze(run):
    run = Path(run)
    protocol = json.loads((run / "protocol.json").read_text())
    episodes = {x["episode_id"]: x for x in rows(run / "episodes.jsonl")}
    references = {x["episode_id"]: x for x in rows(run / "reference_manifest.jsonl")}
    main = rows(run / "main_steps.jsonl")
    diagnostics = rows(run / "paired_diagnostics.jsonl")
    attempts = rows(run / "attempts.jsonl")
    responses = rows(run / "responses.jsonl")
    by_main = {x["logical_id"]: x for x in main}

    main_fact = []
    for row in main:
        expected = references[row["episode_id"]]["checkpoints"][row["checkpoint_index"]]["fact_state"]
        actual = row["after"].get("fact_state")
        main_fact.append({
            "episode_id": row["episode_id"], "model": row["model"], "arm": row["arm"],
            "checkpoint_index": row["checkpoint_index"], "valid_submission": row["validation"]["valid"],
            "fact_correct": fact_equal(actual, expected),
            "actual_source_ids": actual.get("active_source_ids") if actual else None,
            "expected_source_ids": expected.get("active_source_ids") if expected else None,
            "probability": row["after"].get("probability"),
        })

    groups = defaultdict(list)
    for row in main_fact:
        groups[(row["episode_id"], row["model"], row["arm"])].append(row)
    trajectory = []
    stale = []
    for key, values in groups.items():
        values.sort(key=lambda x: x["checkpoint_index"])
        trajectory.append({
            "episode_id": key[0], "model": key[1], "arm": key[2],
            "trajectory_fact_mean": mean([int(x["fact_correct"]) for x in values]),
            "endpoint_fact_correct": values[-1]["fact_correct"],
            "all_checkpoints_correct": all(x["fact_correct"] for x in values),
        })
        expected = references[key[0]]["checkpoints"]
        for index, value in enumerate(values):
            if index and expected[index]["fact_state"] != expected[index - 1]["fact_state"]:
                if value["actual_source_ids"] == expected[index - 1]["fact_state"].get("active_source_ids"):
                    stale.append({**key_to_dict(key), "checkpoint_index": index})

    method_summary = {}
    for model in protocol["enabled_models"]:
        for arm in ("FRESH", "STATEFUL"):
            subset = [x for x in main_fact if x["model"] == model and x["arm"] == arm]
            traj = [x for x in trajectory if x["model"] == model and x["arm"] == arm]
            method_summary[f"{model}|{arm}"] = {
                "opportunities": len(subset), "valid_submissions": sum(x["valid_submission"] for x in subset),
                "fact_correct": sum(x["fact_correct"] for x in subset),
                "fact_accuracy": mean([int(x["fact_correct"]) for x in subset]),
                "endpoint_accuracy": mean([int(x["endpoint_fact_correct"]) for x in traj]),
                "trajectory_mean": mean([x["trajectory_fact_mean"] for x in traj]),
                "trajectory_groups": len(traj),
            }

    paired = []
    by_key = {(x["episode_id"], x["model"], x["arm"], x["checkpoint_index"]): x for x in main_fact}
    for episode in episodes:
        for model in protocol["enabled_models"]:
            for index in range(3):
                fresh = by_key.get((episode, model, "FRESH", index))
                stateful = by_key.get((episode, model, "STATEFUL", index))
                if fresh and stateful:
                    paired.append({
                        "episode_id": episode, "model": model, "checkpoint_index": index,
                        "both_fact_correct": fresh["fact_correct"] and stateful["fact_correct"],
                        "fresh_fact_correct": fresh["fact_correct"],
                        "stateful_fact_correct": stateful["fact_correct"],
                        "same_fact_state": fresh["actual_source_ids"] == stateful["actual_source_ids"],
                    })

    e2_rows = []
    for row in diagnostics:
        anchor = by_main.get(row["input_metadata"]["anchor_logical_id"])
        if not anchor:
            continue
        probability = row["after"].get("probability")
        anchor_probability = anchor["after"].get("probability")
        numeric = isinstance(probability, (int, float)) and not isinstance(probability, bool)
        anchor_numeric = isinstance(anchor_probability, (int, float)) and not isinstance(anchor_probability, bool)
        e2_rows.append({
            "logical_id": row["logical_id"], "model": row["model"], "arm": row["arm"],
            "variant": row["variant"], "valid_submission": row["validation"]["valid"],
            "fact_correct": fact_equal(row["after"].get("fact_state"), anchor["after"].get("fact_state")),
            "probability_abs_drift_from_anchor": abs(probability - anchor_probability) if numeric and anchor_numeric else None,
        })

    response_usage = []
    for response in responses:
        usage = (response.get("provider_response") or {}).get("usage") or {}
        response_usage.append({
            "stage": response["stage"], "model": response["model"],
            "http_status": response.get("http_status"),
            "total_tokens": usage.get("total_tokens"), "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
        })

    errors = Counter(error for row in main + diagnostics for error in row["validation"]["errors"])
    coverage = {
        "attempts_by_stage": dict(Counter(x["stage"] for x in attempts)),
        "responses_by_stage": dict(Counter(x["stage"] for x in responses)),
        "diagnostic_records": len(diagnostics),
        "main_records": len(main),
        "main_expected": len(episodes) * len(protocol["enabled_models"]) * 2 * 3,
        "e2_expected": len(protocol["e2_parent_ids"]) * len(protocol["enabled_models"]) * 2 * 3,
        "e2_captured_and_reconstructed": len(diagnostics),
        "e2_attempts_without_capture": len(rows(run / "audit" / "e2_missing_attempts.jsonl")),
        "errors": dict(errors),
        "http_statuses": dict(Counter(str(x["http_status"]) for x in response_usage)),
        "usage_unknown_responses": sum(x["total_tokens"] is None for x in response_usage),
    }
    metrics = {
        "scope": "Y_BLIND_TAF_SOURCE_STATE_PILOT",
        "main": {
            "method_summary": method_summary,
            "trajectory_records": trajectory,
            "fact_records": main_fact,
            "fresh_stateful_pairs": paired,
            "stale_state_events": stale,
        },
        "e2": {
            "records": e2_rows,
            "by_variant": {
                variant: {
                    "n": len([x for x in e2_rows if x["variant"] == variant]),
                    "valid": sum(x["valid_submission"] for x in e2_rows if x["variant"] == variant),
                    "fact_correct": sum(x["fact_correct"] for x in e2_rows if x["variant"] == variant),
                    "mean_abs_drift": mean([x["probability_abs_drift_from_anchor"] for x in e2_rows if x["variant"] == variant and x["probability_abs_drift_from_anchor"] is not None]),
                } for variant in ("R", "D", "S")
            },
        },
        "coverage": coverage,
        "usage": response_usage,
        "interpretation_limits": [
            "No Y/outcome was read; probability quality, Brier score, calibration, and warning utility are NOT_TESTED.",
            "Program reference and deterministic baseline share parsing/rule dependencies.",
            "E2 branches are paired diagnostics, not independent weather episodes.",
            "Qwen was smoke-only because one smoke request took 429.45 seconds; main comparison is two-model.",
            "AI qualification is not independent human review.",
        ],
    }
    (run / "metrics.json").write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n")
    (run / "coverage_and_failures.json").write_text(json.dumps(coverage, indent=2, sort_keys=True) + "\n")
    write_figures(run, method_summary, e2_rows)
    print(json.dumps({"main": len(main), "main_valid": sum(x["validation"]["valid"] for x in main), "e2": len(e2_rows), "stale": len(stale), "coverage": coverage}, sort_keys=True))


def key_to_dict(key):
    return {"episode_id": key[0], "model": key[1], "arm": key[2]}


def write_figures(run, method_summary, e2_rows):
    try:
        import matplotlib.pyplot as plt
    except Exception:
        write_svg_fallback(run, method_summary, e2_rows)
        return
    labels = list(method_summary)
    endpoint = [method_summary[x]["endpoint_accuracy"] or 0 for x in labels]
    trajectory = [method_summary[x]["trajectory_mean"] or 0 for x in labels]
    fig, ax = plt.subplots(figsize=(10, 4))
    positions = list(range(len(labels)))
    ax.bar([x - 0.18 for x in positions], endpoint, width=0.36, label="endpoint")
    ax.bar([x + 0.18 for x in positions], trajectory, width=0.36, label="trajectory mean")
    ax.set_ylim(0, 1)
    ax.set_ylabel("fact-state accuracy")
    ax.set_xticks(positions, [x.split("|")[-1] + "\n" + x.split("|")[0].split("/")[-1] for x in labels], rotation=20, ha="right")
    ax.legend()
    fig.tight_layout()
    fig.savefig(run / "figures" / "main_endpoint_vs_trajectory.png", dpi=160)
    plt.close(fig)

    variants = ("R", "D", "S")
    data = [[x["probability_abs_drift_from_anchor"] for x in e2_rows if x["variant"] == variant and x["probability_abs_drift_from_anchor"] is not None] for variant in variants]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.boxplot(data, labels=variants, showmeans=True)
    ax.set_ylabel("absolute probability drift from anchor")
    ax.set_title("E2 paired presentation diagnostic")
    fig.tight_layout()
    fig.savefig(run / "figures" / "e2_probability_drift.png", dpi=160)
    plt.close(fig)

    valid = [sum(x["valid_submission"] for x in e2_rows if x["variant"] == variant) for variant in variants]
    fact = [sum(x["fact_correct"] for x in e2_rows if x["variant"] == variant) for variant in variants]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar([x - 0.18 for x in range(3)], valid, width=0.36, label="valid")
    ax.bar([x + 0.18 for x in range(3)], fact, width=0.36, label="fact equals anchor")
    ax.set_xticks(range(3), variants)
    ax.set_ylabel("count")
    ax.legend()
    fig.tight_layout()
    fig.savefig(run / "figures" / "e2_validity_and_fact.png", dpi=160)
    plt.close(fig)


def write_svg_fallback(run, method_summary, e2_rows):
    """Keep the three planned plots available in the minimal CPU environment."""
    def svg_bar(path, title, labels, groups, colors, ymax=1.0, suffix=""):
        width, height = 980, 480
        left, bottom, plot_w, plot_h = 90, 80, 820, 310
        max_value = max(ymax, max((value for group in groups for value in group), default=1))
        bar_width = plot_w / max(1, len(labels) * len(groups))
        chunks = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
                  '<style>text{font-family:sans-serif;font-size:14px}.title{font-size:20px;font-weight:bold}</style>',
                  f'<text x="{width/2}" y="28" text-anchor="middle" class="title">{title}</text>',
                  f'<line x1="{left}" y1="{bottom}" x2="{left}" y2="{bottom-plot_h}" stroke="black"/>',
                  f'<line x1="{left}" y1="{bottom}" x2="{left+plot_w}" y2="{bottom}" stroke="black"/>']
        for index, label in enumerate(labels):
            center = left + (index + 0.5) * plot_w / len(labels)
            chunks.append(f'<text x="{center}" y="{bottom+24}" text-anchor="middle">{label}</text>')
            for group_index, group in enumerate(groups):
                value = group[index]
                x = center + (group_index - (len(groups)-1)/2) * bar_width
                h = value / max_value * plot_h
                y = bottom - h
                chunks.append(f'<rect x="{x-bar_width/2:.1f}" y="{y:.1f}" width="{bar_width-3:.1f}" height="{h:.1f}" fill="{colors[group_index]}"/>')
                chunks.append(f'<text x="{x:.1f}" y="{max(45,y-4):.1f}" text-anchor="middle">{value:.3g}{suffix}</text>')
        for group_index, color in enumerate(colors):
            x = left + plot_w - 170 + group_index * 85
            chunks.append(f'<rect x="{x}" y="42" width="14" height="14" fill="{color}"/><text x="{x+19}" y="54">G{group_index+1}</text>')
        chunks.append('</svg>')
        (run / "figures" / path).write_text("\n".join(chunks))

    labels = [x.split("|")[-1] + " / " + x.split("|")[0].split("/")[-1] for x in method_summary]
    svg_bar("main_endpoint_vs_trajectory.svg", "Endpoint versus trajectory fact accuracy", labels,
             [[method_summary[x]["endpoint_accuracy"] or 0 for x in method_summary],
              [method_summary[x]["trajectory_mean"] or 0 for x in method_summary]], ["#2b6cb0", "#c05621"])
    variants = ("R", "D", "S")
    means = [mean([x["probability_abs_drift_from_anchor"] for x in e2_rows if x["variant"] == v and x["probability_abs_drift_from_anchor"] is not None]) or 0 for v in variants]
    svg_bar("e2_probability_drift.svg", "E2 mean absolute probability drift", list(variants), [means], ["#2f855a"], ymax=max(0.05, max(means, default=0)))
    valid = [sum(x["valid_submission"] for x in e2_rows if x["variant"] == v) for v in variants]
    fact = [sum(x["fact_correct"] for x in e2_rows if x["variant"] == v) for v in variants]
    svg_bar("e2_validity_and_fact.svg", "E2 validity and fact agreement", list(variants), [valid, fact], ["#805ad5", "#dd6b20"], ymax=max(valid + fact + [1]), suffix="")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    args = parser.parse_args()
    analyze(args.run)
