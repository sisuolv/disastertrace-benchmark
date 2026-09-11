"""Post-result diagnostic of public numerical representation and arithmetic aid."""

from copy import deepcopy
from datetime import datetime, timezone
import json
import shutil

from common import ROOT, digest, dump
from model_adapter import load_frontend, prepare, sha_file


def main():
    import torch

    torch.set_num_threads(4)
    old = ROOT / "gpu/wave6_natural_coverage"
    prior = json.loads((old / "PLAN.json").read_text())
    public_prior = json.loads((old / "PUBLIC.json").read_text())
    batch = ROOT / "gpu/wave7_natural_assistance"
    batch.mkdir(exist_ok=False)
    (batch / "source").mkdir()
    (batch / "assets").mkdir()
    public = {}
    conditions = {name: {"mode": "full", "representation": "text", "budget": 4, "max_calls": 1}
                  for name in ["compact_counts", "computed_bounds"]}
    for eid, variants in public_prior.items():
        state = deepcopy(variants["full_text"]["initial"])
        query = state["public"]
        target = query["target"]
        query["question"] = (
            "For the fixed SEVIR frame and its entire147456pixel region, is the fraction of pixels "
            "with encoded VIL at least160 greater than or equal to0.01? Missing pixels have unknown "
            "VIL values. Answer yes only if every completion of missing pixels meets the threshold; "
            "answer no only if every completion falls below it; otherwise answer unknown. "
            "The four quadrant sizes sum to the full-frame denominator."
        )
        compact, positive, negative, missing = [], 0, 0, 0
        for card in query["evidence"]:
            record = card["records"][0]
            total = target["support_sizes"][record["support"]]
            pos, neg = record["value"]["positive"], record["value"]["negative"]
            absent = total - pos - neg
            if min(pos, neg, absent) < 0:
                raise ValueError("invalid public count partition")
            compact.append({"id": card["id"], "support": record["support"],
                "pixels_at_or_above_160": pos, "pixels_below_160": neg,
                "pixels_with_unknown_VIL": absent, "total_pixels": total})
            positive += pos
            negative += neg
            missing += absent
        query["evidence"] = compact
        query["representation_note"] = "Counts are a deterministic reformatting of the archived public product measurements; all four cards have been read."
        public[eid] = {"compact_counts": {"initial": deepcopy(state), "states": {}}}
        query["deterministic_arithmetic_aid"] = {
            "minimum_possible_exceeding_pixels": positive,
            "maximum_possible_exceeding_pixels": positive + missing,
            "known_nonexceeding_pixels": negative,
            "full_region_pixels": target["total_pixels"],
            "threshold_in_pixels": target["fraction_threshold"] * target["total_pixels"],
            "rule": "yes if minimum >= threshold_in_pixels; no if maximum < threshold_in_pixels; otherwise unknown",
            "source": "Computed solely from the displayed acquired counts; no reference answer supplied."
        }
        public[eid]["computed_bounds"] = {"initial": state, "states": {}}
    dump(batch / "PUBLIC.json", public)
    tasks, workers = {}, {}
    for model, ids in [("qwen3vl_8b", ["0", "1"]), ("qwen3vl_32b", ["2", "3"])]:
        for worker in ids:
            workers[worker] = {"model": model, "tasks": [], "max_calls": 0}
        for index, eid in enumerate(sorted(public)):
            worker = ids[index % 2]
            for name, condition in conditions.items():
                tid = "a" + digest((model + eid + name).encode())[:16]
                tasks[tid] = {"id": tid, "episode": eid, "model": model, "condition": name, **condition}
                workers[worker]["tasks"].append(tid)
                workers[worker]["max_calls"] += 1
    checks = []
    for model, spec in prior["models"].items():
        frontend = load_frontend(spec, prior["settings"])
        rows = []
        for eid, variants in public.items():
            for name, bundle in variants.items():
                _, record = prepare(frontend, "vl", bundle["initial"], batch, prior["settings"])
                rows.append({"episode": eid, "condition": name, **record})
        dump(batch / ("CPU_PREFLIGHT_" + model + ".json"), rows)
        checks.append({"model": model, "profiles": len(rows), "max_input_tokens": max(r["input_tokens"] for r in rows)})
    for name in ["model_adapter.py", "gpu_worker.py"]:
        shutil.copy2(ROOT / "code" / name, batch / "source" / name)
    plan = {k: prior[k] for k in ["models", "settings", "deadline_unix", "runtime_files", "runtime_versions",
                                "private_data_file", "private_data_sha256", "scope_amendment_sha256"]}
    plan.update({"created_at": datetime.now(timezone.utc).isoformat(), "wave": "wave7-natural-assistance",
        "conditions": conditions, "tasks": tasks, "workers": workers, "max_requests": 48,
        "max_worker_seconds": 7200, "max_concurrent_gpus": 4, "episodes": len(public), "preflight": checks,
        "bound_files": {str(p.relative_to(batch)): sha_file(p) for p in batch.rglob("*") if p.is_file()},
        "source_sha256": {"freeze_natural_assistance.py": sha_file(ROOT / "code/freeze_natural_assistance.py")},
        "basis": "Triggered after wave6: low full-count performance and all-unknown8B native outputs; all12episodes and both models retained.",
        "interpretation": "Exploratory interface/arithmetic-aid diagnostic. Compact reformats and clarifies semantics; bounds additionally compute redundant public arithmetic. No isolated one-factor causal claim or replacement of prior scores.",
        "development_only": True, "model_supplied_private_references": False})
    if len(public) != 12 or sum(w["max_calls"] for w in workers.values()) != 48:
        raise ValueError("diagnostic denominator differs")
    dump(batch / "PLAN.json", plan)
    print(json.dumps({"tasks": len(tasks), "max_calls": 48, "preflight": checks, "plan_sha256": sha_file(batch / "PLAN.json")}))


if __name__ == "__main__":
    main()
