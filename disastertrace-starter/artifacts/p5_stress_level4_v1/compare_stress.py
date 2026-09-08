"""Descriptive matched P4/P5 comparison retaining every planned checkpoint."""

import argparse
from collections import Counter, defaultdict
from pathlib import Path

from disastertrace.automated.common import fingerprint, read_jsonl
from disastertrace.controlled import renderer
from disastertrace.controlled.schema import METHODS
from disastertrace.controlled.scorer import METRICS
from disastertrace.local_eval.storage import digest, inventory, read, seal, verify_seal, write
from disastertrace.stress_eval.data import denominators

HERE = Path(__file__).resolve().parent
FACTORS = ("revision_chain", "irrelevant_scope", "late_stale_replay")


def paired_scores(base, stress, mapping, slot_metadata):
    if denominators(base) != denominators(stress):
        raise ValueError("metric denominators differ")

    def indexed(score, remap):
        result = {}
        for row in score["per_checkpoint"]:
            ep = remap.get(row["episode_id"], row["episode_id"])
            key = (ep, row["checkpoint_id"])
            if key in result:
                raise ValueError("duplicate mapped checkpoint")
            result[key] = row
        return result

    before, after = indexed(base, {}), indexed(stress, mapping)
    if set(before) != set(after):
        raise ValueError("matched checkpoint set differs")
    transitions = Counter()
    strata = defaultdict(Counter)
    details = []
    for key, a in before.items():
        b = after[key]
        if a["group_id"] != b["group_id"]:
            raise ValueError("source group differs")
        for name in {d for _, d in METRICS.values()}:
            if a["counts"][name] != b["counts"][name]:
                raise ValueError("checkpoint opportunity differs")
        x, y = bool(a["counts"]["all_correct"]), bool(b["counts"]["all_correct"])
        label = (
            "both_correct"
            if x and y
            else "base_only_correct"
            if x
            else "stress_only_correct"
            if y
            else "neither"
        )
        transitions[label] += 1
        meta = slot_metadata[b["episode_id"], b["checkpoint_id"]]
        for dimension, value in (
            ("source", a["group_id"]),
            ("family", meta["family"]),
            ("case", meta["case"]),
            ("checkpoint", key[1]),
            ("effective", meta["effective_label"]),
        ):
            strata[dimension, value].update(planned=1, base_correct=int(x), stress_correct=int(y))
        details.append(
            {
                "base_episode_id": key[0],
                "stress_episode_id": b["episode_id"],
                "checkpoint_id": key[1],
                "source_group": a["group_id"],
                "base_status": a["status"],
                "stress_status": b["status"],
                "outcome": label,
                "effective_label": meta["effective_label"],
            }
        )
    return {
        "base_metrics": base["metrics"],
        "stress_metrics": stress["metrics"],
        "paired_outcomes": dict(transitions),
        "matched_checkpoints": len(before),
        "metric_denominators_checked": len(denominators(base)),
        "strata": [{"dimension": k[0], "value": k[1], **v} for k, v in sorted(strata.items())],
        "checkpoint_pairs": details,
    }


def audited_input(execution_path, report_path, run, expected_origin):
    verify_seal(execution_path)
    verify_seal(report_path)
    plan = read(execution_path / "execution.json")
    report = read(report_path / "report.json")
    audit = read(report_path / "audit.json")
    if (
        report["origin"] != expected_origin
        or audit["origin"] != expected_origin
        or report["execution_id"] != plan["execution_id"]
        or report["audit_id"] != audit["audit_id"]
    ):
        raise ValueError("matching audited actual model input required")
    if inventory(run) != audit["run_files"]:
        raise ValueError("run changed after independent audit")
    return plan, report


def preparations(run):
    result = {}
    for path in sorted((run / "batches").glob("*.json")):
        batch = read(path)
        for slot, request, prepared in zip(
            batch["slots"], batch["requests"], batch["prepared"], strict=True
        ):
            key = slot["slot_id"]
            if key in result:
                raise ValueError("duplicate prepared slot")
            result[key] = (request, prepared)
    return result


def generate(base_run=None, stress_runs=None):
    base_root = HERE.parent / "p4_constrained_output_v1"
    base_execution = base_root / "execution_live"
    base_plan = read(base_execution / "execution.json")
    base_run = Path(base_run) if base_run else Path(base_plan["run_path"])
    base_plan, base_report = audited_input(
        base_execution, base_root / "model_report", base_run, "local_model_vllm_constrained_v1"
    )
    base_prepared = preparations(base_run)
    base_slots = read_jsonl(base_execution / "dataset/schedule.jsonl")
    base_episodes = {
        ep["episode_id"]: ep for ep in read_jsonl(base_execution / "dataset/episodes.jsonl")
    }
    base_gold = {
        (r["episode_id"], r["checkpoint_id"]): r["reference"]
        for r in read_jsonl(base_execution / "dataset/private/gold.jsonl")
    }
    factors = {}
    for factor in FACTORS:
        unit = HERE / "units" / factor
        path = unit / "execution_live"
        plan = read(path / "execution.json")
        run = Path(stress_runs[factor]) if stress_runs else Path(plan["run_path"])
        plan, report = audited_input(
            path, unit / "model_report", run, "local_model_vllm_stress_constrained_v1"
        )
        if (
            plan["parent_execution_id"] != base_plan["execution_id"]
            or plan["base_dataset_content_id"] != base_plan["dataset_content_id"]
            or plan["base_dataset_package_id"] != base_plan["dataset_package_id"]
            or plan["stress_profile"]["factor"] != factor
        ):
            raise ValueError("stress factor has wrong parent")
        for key in (
            "settings",
            "model_snapshot_sha256",
            "environment_sha256",
            "backend_files",
            "model_config_files",
        ):
            if plan[key] != base_plan[key]:
                raise ValueError("frozen model/decoding settings changed")
        for name, expected in base_plan["implementation_files"].items():
            if plan["implementation_files"][name] != expected:
                raise ValueError("parent source changed")
        effects = read_jsonl(path / "dataset/effective_factor_counts.jsonl")
        mapping = {r["episode_id"]: r["base_episode_id"] for r in effects}
        if len(mapping) != 36 or set(mapping.values()) != set(base_episodes):
            raise ValueError("one-to-one complete episode mapping required")
        zero = {
            r["episode_id"] for r in effects if r["added_records"] == r["added_deliveries"] == 0
        }
        gold = read_jsonl(path / "dataset/private/gold.jsonl")
        normalized = {(mapping[r["episode_id"]], r["checkpoint_id"]): r["reference"] for r in gold}
        if len(gold) != len(normalized) or normalized != base_gold:
            raise ValueError("Gold values/status/citations/actions differ")
        slots = read_jsonl(path / "dataset/schedule.jsonl")
        episodes = {ep["episode_id"]: ep for ep in read_jsonl(path / "dataset/episodes.jsonl")}
        if len(slots) != len(base_slots):
            raise ValueError("schedule length differs")
        metadata, exposure, prepared_counts = {}, [], {m: Counter() for m in METHODS}
        prepared = preparations(run)
        for old_slot, slot in zip(base_slots, slots, strict=True):
            if (
                slot["base_slot_id"] != old_slot["slot_id"]
                or slot["base_episode_id"] != old_slot["episode_id"]
                or any(
                    slot[k] != old_slot[k]
                    for k in ("slot_index", "checkpoint_id", "method", "family", "case")
                )
            ):
                raise ValueError("base cadence or slot mapping changed")
            key = (slot["episode_id"], slot["checkpoint_id"])
            metadata[key] = {
                **slot,
                "effective_label": "zero_effect_control"
                if slot["episode_id"] in zero
                else "transformed",
            }
            a = renderer.render_request(
                base_episodes[old_slot["episode_id"]],
                old_slot["checkpoint_id"],
                method=slot["method"],
            )
            b = renderer.render_request(
                episodes[slot["episode_id"]], slot["checkpoint_id"], method=slot["method"]
            )
            if {k: v for k, v in a.items() if k != "evidence"} != {
                k: v for k, v in b.items() if k != "evidence"
            }:
                raise ValueError("non-evidence public task specification differs")
            exposure.append(
                {
                    "slot_id": slot["slot_id"],
                    "base_slot_id": old_slot["slot_id"],
                    "method": slot["method"],
                    "checkpoint_id": slot["checkpoint_id"],
                    "same_public_evidence": a["evidence"] == b["evidence"],
                    "base_deliveries": len(a["evidence"]),
                    "stress_deliveries": len(b["evidence"]),
                }
            )
            counts = prepared_counts[slot["method"]]
            counts["planned"] += 1
            if slot["slot_id"] in prepared:
                req, p = prepared[slot["slot_id"]]
                req_a, p_a = base_prepared[old_slot["slot_id"]]
                if (
                    req["evidence"] != b["evidence"]
                    or req_a["evidence"] != a["evidence"]
                    or p["messages"][0] != p_a["messages"][0]
                ):
                    raise ValueError("captured evidence/system prompt differs from frozen task")
                if {k: v for k, v in p["sampling"].items() if k != "seed"} != {
                    k: v for k, v in p_a["sampling"].items() if k != "seed"
                }:
                    raise ValueError("sampling differs beyond predeclared seed derivation")
                counts["prepared"] += 1
                counts["identical_prompt_tokens"] += int(
                    p["prompt_token_ids"] == p_a["prompt_token_ids"]
                )
                counts["different_seed"] += int(p["sampling"]["seed"] != p_a["sampling"]["seed"])
        factors[factor] = {
            "execution_id": plan["execution_id"],
            "audit_id": report["audit_id"],
            "report_package_id": read(unit / "model_report/manifest.json")["package_id"],
            "report_sha256": digest(unit / "model_report/report.json"),
            "complete": report["complete"],
            "received": report["received"],
            "planned": report["planned"],
            "zero_effect_episodes": len(zero),
            "effective_factor_counts": effects,
            "gold_equivalences": len(gold),
            "evidence_exposure": exposure,
            "actual_preparations": {k: dict(v) for k, v in prepared_counts.items()},
            "methods": {
                m: paired_scores(base_report["methods"][m], report["methods"][m], mapping, metadata)
                for m in METHODS
            },
            "format_layers": report["format_layers"],
            "format_screens": report["reliability"],
            "field_error_reasons": dict(Counter(e["reason"] for e in report["errors"]["fields"])),
            "action_errors": len(report["errors"]["actions"]),
            "usage": report["usage"],
            "finish_reasons": report["finish_reasons"],
            "extraction_errors": report["extraction_errors"],
        }
    result = {
        "schema_version": "p5_matched_stress_comparison_v1",
        "base_execution_id": base_plan["execution_id"],
        "base_audit_id": base_report["audit_id"],
        "base_report_sha256": digest(base_root / "model_report/report.json"),
        "factors": factors,
        "additional_model_calls": 0,
        "fixed_denominators": True,
        "interpretation": "Descriptive same-model development comparison: three dependent source groups, one repeat. New stress slot seeds and full H100 hardware differ from the P4 MIG run; no identical-sample, causal-memory, timing or general-weather superiority claim.",
    }
    result["comparison_id"] = fingerprint(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--base-run", type=Path)
    parser.add_argument("--runs-root", type=Path)
    args = parser.parse_args()
    runs = (
        {f: args.runs_root / ("p5-qwen3-" + f.replace("_", "-") + "-v1") for f in FACTORS}
        if args.runs_root
        else None
    )
    result = generate(args.base_run, runs)
    output = HERE / "stress_comparison"
    if args.verify:
        verify_seal(output)
        if read(output / "comparison.json") != result:
            raise ValueError("stress comparison reconstruction differs")
    else:
        output.mkdir(exist_ok=False)
        write(output / "comparison.json", result)
        seal(output)
    print({"status": "passed", "comparison_id": result["comparison_id"]})


if __name__ == "__main__":
    main()
