"""Posthoc descriptive analysis of the complete, independently scored model batch."""

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


HERE = Path(__file__).resolve().parents[1]
INPUT = HERE / "reports/large_model_diagnostic_01"
OUT = HERE / "reports/large_model_analysis_01"
MODELS = ("qwen235b_fp8", "qwen8b_control")
CONDITIONS = ("common_only", "fixed_one", "all_registered")


def load(path):
    return json.loads(path.read_text())


def save(path, value):
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def main():
    OUT.mkdir(exist_ok=False)
    valid = load(INPUT / "VALIDATION.json")
    assert valid["integrity_passed"] and valid["registered"] == valid["committed"] == 1008
    manifest, tables, time_pairs, changes, paired = {}, [], [], [], []
    responses = {}
    for model in MODELS:
        report = load(INPUT / model / "REPORT.json")
        rows = load(INPUT / model / "RECORDS.json")
        responses[model] = {r["call_id"]: r for r in rows}
        assert len(rows) == 504 and report["all_completed"]
        for filename in ("REPORT.json", "RECORDS.json"):
            path = INPUT / model / filename
            manifest[str(path.relative_to(HERE))] = hashlib.sha256(path.read_bytes()).hexdigest()
        for head in ("e_only", "joint"):
            for condition in CONDITIONS:
                group = [r for r in rows if r["input_kind"] == "bundle"
                         and r["head"] == head and r["condition"] == condition]
                assert len(group) == 48
                confusion = Counter((r["e_expected"], r["e_answer"]) for r in group)
                tables.append({"model": model, "head": head, "condition": condition,
                    "n": len(group), "correct": sum(r["e_correct"] for r in group),
                    "always_unknown_correct": sum(r["e_expected"] == "undetermined" for r in group),
                    "unwarranted_determination": sum(r["e_expected"] == "undetermined" and r["e_answer"] in
                        {"supported", "refuted"} for r in group),
                    "confusion": [{"expected": a, "answer": b, "n": n}
                                  for (a, b), n in sorted(confusion.items())]})
        for head in ("taf_coverage", "taf_revision"):
            group = [r for r in report["time_pairs"] if r["head"] == head]
            table = Counter((r["epoch_correct"], r["iso_correct"]) for r in group)
            time_pairs.append({"model": model, "head": head, "pairs": len(group),
                "both_correct": table[True, True], "both_wrong": table[False, False],
                "epoch_only_correct": table[True, False], "iso_only_correct": table[False, True]})
        changes.extend({"model": model, **r} for r in rows if r["input_kind"] == "bundle"
            and r["candidate_probability"] is not None and r["candidate_probability"] != r["baseline_at_dispatch"])
    assert set(responses[MODELS[0]]) == set(responses[MODELS[1]])
    for head in ("e_only", "joint"):
        for condition in CONDITIONS:
            pairs = [(a, responses[MODELS[1]][key]) for key, a in responses[MODELS[0]].items()
                     if a["input_kind"] == "bundle" and a["head"] == head and a["condition"] == condition]
            assert all(a["e_expected"] == b["e_expected"] for a, b in pairs)
            counts = Counter((a["e_correct"], b["e_correct"]) for a, b in pairs)
            paired.append({"head": head, "condition": condition, "n": len(pairs),
                "235B_only_correct": counts[True, False], "8B_only_correct": counts[False, True],
                "both_correct": counts[True, True], "both_wrong": counts[False, False]})
    save(OUT / "E_TABLES.json", tables)
    save(OUT / "TIME_PAIRS.json", time_pairs)
    save(OUT / "MODEL_PAIRS.json", paired)
    save(OUT / "ALL_CHANGED_F_PROPOSALS.json", changes)
    with (OUT / "E_TABLES.csv").open("x", newline="") as handle:
        fields = [k for k in tables[0] if k != "confusion"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({k: row[k] for k in fields} for row in tables)
    save(OUT / "ANALYSIS.json", {"kind": "posthoc_descriptive_full_denominator",
        "validation": valid, "inputs": manifest, "no_new_model_calls": True,
        "independent_weather_process_confirmation": False,
        "limits": ["Repeated evidence conditions and heads share the same48 opportunities.",
                   "One exposed development day: severe threshold0 positives,5km threshold1 positive in24 each.",
                   "235B MoE Instruct FP8 and8B differ beyond parameter count.",
                   "No input or answer has been replaced after observing these results."]})
    print(json.dumps({"tables": len(tables), "changed_F_proposals": len(changes), "output": str(OUT)}))


if __name__ == "__main__":
    main()
