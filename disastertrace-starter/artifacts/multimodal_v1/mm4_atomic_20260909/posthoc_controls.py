"""Descriptive trivial controls, explicitly added after observing this development run."""

from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "source/src"))

from disastertrace.multimodal_atomic_v1.scoring import parse
from disastertrace.multimodal_v1.storage import read, write


def main():
    plan, refs = read(ROOT / "REQUEST_PLAN.json"), read(ROOT / "references.json")
    workers = {tid: w for w, ids in plan["assignments"].items() for tid in ids}
    rows = []
    for task in plan["tasks"]:
        family, tid = task["family"], task["task_id"]
        if family not in {"spatial", "watch"}:
            continue
        slot = ROOT / "gpu_runs" / workers[tid] / "live" / tid
        actual = parse((slot / "raw.txt").read_text(), family)["state"]
        for query in task["inputs"]["queries"]:
            sid = query["site_id"]
            if family == "spatial":
                field = "relation"
                public_guess = "inside" if task["inputs"]["evidence"] else "unknown"
            else:
                field = "watched"
                has_list = any(e["meta"]["target"] == task["inputs"]["target"]
                               for e in task["inputs"]["evidence"])
                public_guess = True if has_list else None
            expected = refs[tid]["state"][sid][field]
            rows.append({"task_id": tid, "family": family, "field": field, "reference": expected,
                         "model_value": actual[sid][field], "public_presence_guess": public_guess,
                         "guess_correct": public_guess == expected,
                         "model_matches_guess": actual[sid][field] == public_guess})
    by_family = {}
    for family in ("spatial", "watch"):
        selected = [r for r in rows if r["family"] == family]
        by_family[family] = {"denominator": len(selected), "guess_value_correct": sum(r["guess_correct"] for r in selected),
                             "model_values_matching_guess": sum(r["model_matches_guess"] for r in selected),
                             "reference_value_counts": dict(Counter(str(r["reference"]) for r in selected))}
    write(ROOT / "POSTHOC_PRESENCE_CONTROLS.json", {
          "origin": "posthoc_program_diagnostic", "generations": 0,
          "declaration": "added after model observations; not a preregistered model arm",
          "spatial_policy": "inside whenever map present, else unknown; no pixel inspection",
          "watch_policy": "true whenever matching watch list present, else null; no line reading",
          "by_family": by_family, "rows": rows,
          "limitation": "matching output patterns do not establish the model's internal decision rule"})


if __name__ == "__main__":
    main()
