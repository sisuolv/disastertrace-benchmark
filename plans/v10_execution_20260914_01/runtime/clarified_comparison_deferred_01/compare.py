"""Audit and compare the complete error-informed prompt clarification study."""

import argparse
import ast
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path


def read(path):
    return json.loads(path.read_text())


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def qualification(parent, fresh):
    original_plan, plan = read(parent / "PLAN.json"), read(fresh / "PLAN.json")
    selected = [t for t in original_plan["tasks"] if t["kind"] == "aviation_features"]
    if [t["call_id"] for t in selected] != [t["call_id"] for t in plan["tasks"]]:
        raise ValueError(
            "Clarification selected different tasks or changed their order"
        )
    suffixes = set()
    for task in selected:
        name = task["call_id"] + ".json"
        old, new = read(parent / "policy" / name), read(fresh / "policy" / name)
        original = old["messages"][0]["content"]
        expanded = new["messages"][0]["content"]
        if old["messages"][1:] != new["messages"][1:] or not expanded.startswith(
            original
        ):
            raise ValueError("Original native evidence or instruction text changed")
        suffixes.add(expanded[len(original) :])
        if (parent / "bundles" / name).read_bytes() != (
            fresh / "bundles" / name
        ).read_bytes():
            raise ValueError("Paired numerical inputs differ")
    if len(suffixes) != 1 or not next(iter(suffixes)).strip():
        raise ValueError("Clarification must be one identical nonempty instruction")
    old_ref, new_ref = (
        read(parent / "evaluator/REFERENCES.json"),
        read(fresh / "evaluator/REFERENCES.json"),
    )
    if new_ref != {t["call_id"]: old_ref[t["call_id"]] for t in selected}:
        raise ValueError("Paired references changed")
    for folder in ["source/disastertrace", "banks"]:
        for path in (parent / folder).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                other = fresh / path.relative_to(parent)
                if path.read_bytes() != other.read_bytes():
                    raise ValueError(
                        "Original decoder, bank or scoring dependency changed"
                    )

    class RemoveDisplayUnits(ast.NodeTransformer):
        def visit_FunctionDef(self, node):
            self.generic_visit(node)
            if node.name != "qualify":
                return node
            names = [
                item
                for item in ast.walk(node)
                if isinstance(item, ast.Name) and item.id == "qid"
            ]
            if len(names) != 1:
                return node
            for item in ast.walk(node):
                if (
                    isinstance(item, ast.For)
                    and isinstance(item.target, ast.Tuple)
                    and [getattr(x, "id", None) for x in item.target.elts]
                    == ["qid", "product"]
                    and isinstance(item.iter, ast.Call)
                    and isinstance(item.iter.func, ast.Attribute)
                    and item.iter.func.attr == "items"
                ):
                    item.target = ast.Name(id="product", ctx=ast.Store())
                    item.iter.func.attr = "values"
            return node

        def visit_Dict(self, node):
            self.generic_visit(node)
            for index, key in enumerate(node.keys):
                if isinstance(key, ast.Constant) and key.value == "units":
                    node.values[index] = ast.Constant(value=None)
            return node

    def normalized(path):
        return ast.dump(
            RemoveDisplayUnits().visit(ast.parse(path.read_text())),
            include_attributes=False,
        )

    if normalized(parent / "source/score_feature_temperature.py") != normalized(
        fresh / "source/score_feature_temperature.py"
    ):
        raise ValueError(
            "Scorer changed beyond display counts and removal of an unused dict key"
        )
    for key in [
        "local_model",
        "gpu_runtime",
        "gpu_engine",
        "max_tokens",
        "input_token_cap",
        "batch_size",
        "scoring",
    ]:
        if original_plan[key] != plan[key]:
            raise ValueError("Paired generation or score contract changed: " + key)
    return {
        "passed": True,
        "tasks": len(selected),
        "common_clarification": True,
        "same_native_inputs_references_banks": True,
        "scorer_scoring_logic_same": True,
        "allowed_scorer_changes": [
            "displayed unit counts",
            "unused dictionary key in native qualification iteration",
        ],
        "prompt_informed_by_prior_errors": True,
        "independent_confirmation": False,
        "parent_plan_sha256": hashlib.sha256(
            (parent / "PLAN.json").read_bytes()
        ).hexdigest(),
        "fresh_plan_sha256": hashlib.sha256(
            (fresh / "PLAN.json").read_bytes()
        ).hexdigest(),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--fresh", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--qualify-only", action="store_true")
    args = parser.parse_args()
    args.out.mkdir(exist_ok=False)
    checked = qualification(args.parent, args.fresh)
    if args.qualify_only:
        (args.out / "RESULT.json").write_text(json.dumps(checked, indent=2) + "\n")
        print(json.dumps(checked), flush=True)
        return
    for batch in (args.parent, args.fresh):
        if not read(batch / "final_audit_01/RESULT.json")["passed"]:
            raise ValueError("Original full token/capture/score audits required")
    left, right = [
        batch / "final_audit_01/scores" for batch in (args.parent, args.fresh)
    ]
    before = {
        (r["call_id"], r["query_id"], r["field"]): r
        for r in lines(left / "FIELDS.jsonl")
    }
    fields = defaultdict(Counter)
    for row in lines(right / "FIELDS.jsonl"):
        prior = before[(row["call_id"], row["query_id"], row["field"])]
        for cohort in (row["cohort"], "all_units_descriptive"):
            count = fields[cohort + "__" + row["field"]]
            count["registered"] += 1
            count["old_correct"] += prior["semantic_exact"]
            count["new_correct"] += row["semantic_exact"]
            count["old_invalid"] += prior["invalid_answer"]
            count["new_invalid"] += row["invalid_answer"]
            count["corrected"] += not prior["semantic_exact"] and row["semantic_exact"]
            count["newly_wrong"] += (
                prior["semantic_exact"] and not row["semantic_exact"]
            )
    originals = {
        (r["call_id"], r["threshold"]): r
        for r in lines(left / "ROWS.jsonl")
        if r["kind"] == "aviation_features"
    }
    forecast = defaultdict(list)
    for row in lines(right / "ROWS.jsonl"):
        prior = originals[(row["call_id"], row["threshold"])]
        for key in ["future_status", "outcome", "threshold", "cohort"]:
            if prior[key] != row[key]:
                raise ValueError("Paired future reference changed")
        key = row["cohort"] + "__" + str(row["threshold"])
        forecast[key].append((prior, row))
    metrics = {}
    for key, pairs in forecast.items():
        settled = [
            (a, b)
            for a, b in pairs
            if b["future_status"] == "mature" and b["outcome"] is not None
        ]
        row = {
            "registered": len(pairs),
            "scored": len(settled),
            "positive": sum(b["outcome"] for _, b in settled),
            "old_valid": sum(a["valid"] for a, _ in pairs),
            "new_valid": sum(b["valid"] for _, b in pairs),
        }
        for label, side, method in [
            ("before", 0, "values_model_raw"),
            ("after", 1, "values_model_raw"),
            ("native", 1, "values_native_raw"),
            ("follow", 1, "FOLLOW"),
        ]:
            row[label + "_brier"] = (
                math.fsum(
                    (pair[side]["probabilities"][method] - pair[side]["outcome"]) ** 2
                    for pair in settled
                )
                / len(settled)
                if settled
                else None
            )
        gains = [
            (a["probabilities"]["values_model_raw"] - a["outcome"]) ** 2
            - (b["probabilities"]["values_model_raw"] - b["outcome"]) ** 2
            for a, b in settled
        ]
        row["improvement_after_clarification"] = (
            math.fsum(gains) / len(gains) if gains else None
        )
        row["g_plus"] = (
            math.fsum(max(0, g) for g in gains) / len(gains) if gains else None
        )
        row["g_minus"] = (
            math.fsum(max(0, -g) for g in gains) / len(gains) if gains else None
        )
        metrics[key] = row
    result = {
        **checked,
        "field_comparisons": dict(fields),
        "forecast_comparisons": metrics,
        "new_inference_from_comparison": 0,
        "claim_limit": "error-informed paired development diagnostic; all84 retained, not independent confirmation or a replacement for original scores",
    }
    (args.out / "RESULT.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "passed": True,
                "paired_tasks": checked["tasks"],
                "forecast_groups": len(metrics),
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
