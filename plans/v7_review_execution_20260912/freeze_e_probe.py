"""Freeze real E cases and four declared representations without reading future labels."""

from __future__ import annotations

import argparse
import json
import shutil
import socket
import sys
from collections import defaultdict
from datetime import datetime, timezone
from importlib.metadata import version
from itertools import combinations
from pathlib import Path

BASE = Path(__file__).resolve().parent
REPO = BASE.parents[1]
sys.path.insert(0, str(REPO / "disastertrace-starter/src"))

from disastertrace.monitoring_v1.calibration import predict
from disastertrace.monitoring_v1.dataset import load_session
from disastertrace.monitoring_v1.evidence import (
    exists_report_support,
    report_fact_status,
)
from disastertrace.monitoring_v1.policies import FORECAST_SYSTEM, stable_rank
from disastertrace.monitoring_v1.state import Baseline
from disastertrace.monitoring_v1.targets import TargetSpec
from e_probe_runtime import E_SYSTEM, EXAMPLES
from gpu_worker import digest, save


def main(args):
    from transformers import AutoTokenizer

    batch = args.output.resolve()
    batch.mkdir(exist_ok=False)
    data = load_session(args.dataset, stations=["KDEN", "KCOS", "KPUB"], threshold=1000)
    bank = json.loads(args.bank.read_text())
    targets = {t["target_id"]: t for t in data["targets"]}
    opportunities = {o["opportunity_id"]: o for o in data["opportunities"]}
    products = {q["query_id"]: q for q in data["query_results"]}
    candidate_map = defaultdict(dict)
    for c in data["baseline_candidates"]:
        candidate_map[c["target_id"]][c["source_id"]] = c
    seen, groups = set(), defaultdict(list)
    for pair in data["e_f_pairs"]:
        qids = tuple(sorted(pair["query_ids"]))
        if qids in seen:
            continue
        seen.add(qids)
        for size in range(len(qids) + 1):
            for chosen in combinations(qids, size):
                read = {q: products[q] for q in chosen}
                status = exists_report_support(qids, read, 1000)
                ident = stable_rank(20260912, *qids, "read", *chosen)
                groups[status].append((ident, pair, chosen))
    n = min(
        args.per_status,
        *(len(groups[s]) for s in ("supported", "refuted", "undetermined")),
    )
    if n < 8:
        raise ValueError("Not enough real E cases for this balanced diagnostic")
    selected = []
    labels = {}
    for status in ("supported", "refuted", "undetermined"):
        for ident, pair, chosen in sorted(groups[status], key=lambda item: item[0])[:n]:
            selected.append((ident, pair, chosen))
            labels[ident] = status
    cases = []
    for ident, pair, chosen in sorted(selected, key=lambda item: item[0]):
        o = opportunities[pair["opportunity_id"]]
        target = targets[o["target_id"]]
        clock = o["cutoff"] - 600_000_000
        eligible = [
            c
            for c in candidate_map[o["target_id"]].values()
            if c["available_at"] <= clock <= c["valid_until"]
        ]
        candidate = (
            max(eligible, key=lambda c: (c["available_at"], c["source_id"]))
            if eligible
            else None
        )
        p = predict(bank, target, candidate)["probability"]
        if candidate is None:
            raise ValueError(
                "This bounded probe requires a raw contemporaneous TAF envelope"
            )
        baseline = Baseline(
            TargetSpec(**target),
            candidate["source_id"],
            candidate["projection"],
            p,
            candidate["available_at"],
            candidate["valid_until"],
            bank["mapping_version"],
            "NWS_TAF_via_IEM_with_frozen_research_mapping",
            "fallback"
            if candidate.get("projection_status") == "unavailable"
            else "research",
        ).policy_view()
        assets = [
            {
                "asset_id": q,
                "content": products[q],
                "receipt_ids": ["fixed_source_disclosure"],
                "parents": [],
            }
            for q in chosen
        ]
        common = {
            "case_id": ident,
            "threshold_m": 1000,
            "e_predicate": pair["e_predicate"],
            "registered_query_ids": pair["query_ids"],
            "read_evidence": assets,
            "unread_queries": [q for q in pair["query_ids"] if q not in chosen],
        }
        joint = {
            **common,
            "opportunity_id": o["opportunity_id"],
            "target": target,
            "clock": clock,
            "cutoff": o["cutoff"],
            "protocol": "base_bound_override",
            "common_baseline": baseline,
            "full_native_taf": candidate["raw"],
            "current_state": {
                "target_id": target["target_id"],
                "mode": "follow",
                "probability": p,
                "active_override": None,
                "protocol": "base_bound_override",
            },
        }
        table = {k: v for k, v in common.items() if k != "read_evidence"}
        table["tool_derived_read_fact_table"] = [
            {
                "query_id": q,
                "source_product_status": products[q]["status"],
                "proposition_this_slot_below_threshold": report_fact_status(
                    products[q], 1000
                ),
            }
            for q in chosen
        ]
        table["representation_note"] = (
            "Privileged deterministic interpretation of the same read product; no hidden physical mask or future outcome. This is a tool-assisted diagnostic."
        )
        cases.append(
            {
                "case_id": ident,
                "read_query_ids": list(chosen),
                "requests": {
                    "joint_F_E": joint,
                    "E_only": common,
                    "E_examples": common,
                    "E_fact_table": table,
                },
            }
        )
    systems = {
        "joint_F_E": FORECAST_SYSTEM,
        "E_only": E_SYSTEM,
        "E_examples": E_SYSTEM + EXAMPLES,
        "E_fact_table": E_SYSTEM,
    }
    save(
        args.labels,
        {
            "labels": labels,
            "source_audit_sha256": digest(args.dataset / "REGIONAL_JOIN_AUDIT.json"),
            "sampling": "Balanced real current-evidence states; no future F outcome access; no independent prevalence claim",
            "available_by_status": {k: len(v) for k, v in groups.items()},
        },
    )
    package = batch / "source/disastertrace"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text('"""Frozen current-evidence probe."""\n')
    shutil.copytree(
        REPO / "disastertrace-starter/src/disastertrace/monitoring_v1",
        package / "monitoring_v1",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    for name in ("e_probe_runtime.py", "freeze_e_probe.py"):
        shutil.copyfile(BASE / name, batch / "source" / name)
    worker = (BASE / "gpu_worker.py").read_text()
    original = "from disastertrace.monitoring_v1.policies import run_session"
    if worker.count(original) != 1:
        raise ValueError("GPU adapter location changed")
    (batch / "source/gpu_worker.py").write_text(
        worker.replace(original, "from e_probe_runtime import run_session")
    )
    save(batch / "environment.json", {"cases": cases, "systems": systems})
    save(batch / "BANK.json", {})
    source_plan = json.loads((BASE / "gpu_front_primary_base_01/PLAN.json").read_text())
    spec = source_plan["models"]["qwen3_8b"]
    tokenizer = AutoTokenizer.from_pretrained(spec["directory"], local_files_only=True)
    tasks, preflight = [], []
    for condition, system in systems.items():
        config = {
            "condition": condition,
            "input_token_cap": 11264,
            "output_token_cap": 384,
            "call_compute_cap_ms": 120000,
            "token_cap": len(cases) * (11264 + 384),
            "compute_ms_cap": len(cases) * 120000,
        }
        tasks.append(
            {"run_id": condition, "data_file": "environment.json", "config": config}
        )
        for case in cases:
            messages = [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": json.dumps(
                        case["requests"][condition], separators=(",", ":")
                    ),
                },
            ]
            text = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
            count = len(tokenizer(text, add_special_tokens=False)["input_ids"])
            if count > 11264:
                raise ValueError("Probe input exceeds bound")
            preflight.append(
                {
                    "case_id": case["case_id"],
                    "condition": condition,
                    "input_tokens": count,
                }
            )
    save(batch / "TOKENIZER_PREFLIGHT.json", preflight)
    plan = {
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "cci_hostname": socket.gethostname(),
        "models": {"qwen3_8b": spec},
        "worker_models": {"0": "qwen3_8b"},
        "workers": {"0": tasks},
        "seed": 20260912,
        "max_new_tokens": 384,
        "context_limit": 12288,
        "max_generation_seconds": 90,
        "max_worker_seconds": 1800,
        "max_concurrent_gpus": 4,
        "max_calls_per_worker": len(cases) * 4,
        "maximum_model_calls": len(cases) * 4,
        "runtime_versions": {
            name: version(name) for name in source_plan["runtime_versions"]
        },
        "files": {
            str(p.relative_to(batch)): digest(p)
            for p in batch.rglob("*")
            if p.is_file()
        },
        "evaluation_bindings": {str(args.labels.resolve()): digest(args.labels)},
        "interpretation": "Balanced fixed-disclosure real E diagnostic, separate from F gain or policy selection; rule examples and canonical fact table are declared assistance.",
    }
    save(batch / "PLAN.json", plan)
    print(
        json.dumps(
            {
                "cases": len(cases),
                "maximum_calls": len(cases) * 4,
                "max_input_tokens": max(r["input_tokens"] for r in preflight),
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset", type=Path, default=BASE / "extension_front_range_03"
    )
    parser.add_argument(
        "--bank", type=Path, default=BASE / "calibration_bank_01/BANK.json"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--per-status", type=int, default=32)
    main(parser.parse_args())
