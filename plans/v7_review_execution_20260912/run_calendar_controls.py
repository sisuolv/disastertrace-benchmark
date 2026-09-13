"""Frozen same-calendar strong CPU controls with every forecast opportunity retained."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def run(args):
    from disastertrace.monitoring_v1.dataset import load_session
    from disastertrace.monitoring_v1.policies import run_session
    from disastertrace.monitoring_v1.scoring import brier_report
    from disastertrace.monitoring_v1.state import MonitoringEngine
    from freeze_active import slice_session
    from run_strong_controls import joint_reference

    bank = json.loads(args.bank.read_text())
    data = load_session(
        args.dataset, stations=args.stations, hours=args.hours, threshold=args.threshold
    )
    cutoffs = sorted({o["cutoff"] for o in data["opportunities"]})
    if len(cutoffs) != args.hours:
        raise ValueError("Calendar incomplete")
    configurations = []
    for label in (
        "FOLLOW",
        "round_robin",
        "risk",
        "coverage",
        "batch_complete",
        "all_read",
        "neighbor_persistence",
        "capacity_revise_defer",
    ):
        for protocol in ("base_bound_override", "persistent_override"):
            configurations.append({"label": label, "protocol": protocol})
    write(args.output / "CONFIGURATIONS.json", configurations)
    reports = {}
    for number, start in enumerate(range(0, args.hours, args.block_hours)):
        block = slice_session(data, cutoffs[start : start + args.block_hours])
        ticks = len({o["cutoff"] for o in block["opportunities"]})
        out = args.output / f"block-{number:02d}"
        out.mkdir()
        for rate in (1, 2, 3):
            write(
                out / f"JOINT-budget{rate * ticks}.json",
                joint_reference(block, rate * ticks, args.threshold),
            )
        for spec in configurations:
            label, protocol = spec["label"], spec["protocol"]
            rate = 3 if label in {"all_read", "neighbor_persistence"} else 2
            config = {
                "seed": 20260912,
                "request_budget": ticks * rate,
                "forecast_call_cap": len(block["opportunities"]),
                "per_tick_forecast_cap": len(args.stations) * 3,
                "input_token_cap": 11264,
                "output_token_cap": 384,
                "call_compute_cap_ms": 120000,
                "wakeup_seconds": 600,
                "token_cap": ticks * 2 * (11264 + 384),
                "compute_ms_cap": ticks * 2 * 120000 + ticks * rate * 100,
                "selector_kind": label
                if label in {"round_robin", "risk", "coverage", "batch_complete"}
                else "risk"
                if label == "capacity_revise_defer"
                else "round_robin",
                "isolation_mode": "actual_cost_clock",
                "allocation_mode": "global_budget",
                "authorization_mode": "session_shared",
                "protocol": protocol,
                "program_cost_note": "No model inference tokens; 1ms program update is declared archive accounting, not measured CPU latency",
            }
            if label == "FOLLOW":
                config.update(acquire=False, predict=False)
            if label == "capacity_revise_defer":
                config["gate"] = "capacity_revise_defer"

            if label == "neighbor_persistence":
                config["program_prediction"] = "neighbor_persistence"
            trace = run_session(block, bank, config)
            if trace["actual_model_calls"] != 0:
                raise ValueError("A cheap control was mislabeled as model inference")
            if len(trace["snapshots"]) != len(block["opportunities"]):
                raise ValueError("An arm lost opportunities")
            if trace["snapshots"] != list(
                MonitoringEngine.restore(trace["event_replay"]).snapshots.values()
            ):
                raise ValueError("CPU trace did not reconstruct")
            name = label + "-" + protocol
            write(out / (name + "-TRACE.json"), trace)
            # Outcome reads are confined to the scorer after the trace is complete.
            outcomes = {
                r["target_id"]: r
                for r in json.loads(
                    (args.dataset / "private/OUTCOMES.json").read_text()
                )
            }
            rows = [
                {
                    "opportunity_id": s["opportunity_id"],
                    "base": s["base_probability"],
                    "prediction": s["probability"],
                    "outcome": outcomes[s["target_id"]]["outcome"],
                    "baseline_kind": s["baseline_kind"],
                    "region": args.region,
                    "period": str(s["cutoff"] // 86_400_000_000),
                    "source": "native_metar",
                    "quality": outcomes[s["target_id"]]["status"],
                    "maturity": "final_archive",
                }
                for s in trace["snapshots"]
            ]
            reports[f"block-{number:02d}/" + name] = {
                "config": config,
                "label": label,
                "scores": brier_report(rows),
                "costs": trace["resource_spent"],
                "e_counts": trace["e_counts"],
                "actual_model_calls": 0,
                "cheap_program_updates": len(trace["calls"]),
                "decision_counts": dict(Counter(c["decision"] for c in trace["calls"])),
                "trace_sha256": digest(out / (name + "-TRACE.json")),
            }
            print(
                number,
                label,
                protocol,
                reports[f"block-{number:02d}/" + name]["scores"]["net_realized_gain"],
                flush=True,
            )
        write(
            args.output / "PROGRESS.json",
            {"completed_blocks": number + 1, "completed_runs": len(reports)},
        )
    write(
        args.output / "SUMMARY.json",
        {
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "region": args.region,
            "threshold_m": args.threshold,
            "hours": args.hours,
            "block_hours": args.block_hours,
            "runs": reports,
            "source_audit_sha256": digest(args.dataset / "REGIONAL_JOIN_AUDIT.json"),
            "bank_sha256": digest(args.bank),
            "interpretation": "Complete calendar with cheap full-update controls; resource sessions are not automatically independent weather processes; all_read is legal under the non-tight logical query profile and is also the physical bulk-transport sensitivity comparator.",
        },
    )


def main(args):
    if args.frozen_worker:
        run(args)
        return
    args.output.mkdir(exist_ok=False)
    source = args.output / "implementation"
    package = source / "disastertrace"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text('"""Frozen monitoring program controls."""\n')
    shutil.copytree(
        BASE.parents[1] / "disastertrace-starter/src/disastertrace/monitoring_v1",
        package / "monitoring_v1",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    for name in (
        "run_calendar_controls.py",
        "freeze_active.py",
        "gpu_worker.py",
        "run_strong_controls.py",
        "run_programs.py",
    ):
        shutil.copyfile(BASE / name, source / name)
    write(
        args.output / "SOURCE_BINDINGS.json",
        {str(p.relative_to(source)): digest(p) for p in source.rglob("*.py")},
    )
    command = [
        sys.executable,
        str(source / "run_calendar_controls.py"),
        "--frozen-worker",
    ] + sys.argv[1:]
    env = dict(
        os.environ, PYTHONPATH=str(source.resolve()), PYTHONDONTWRITEBYTECODE="1"
    )
    result = subprocess.run(command, env=env, check=False)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument(
        "--bank", type=Path, default=BASE / "calibration_bank_01/BANK.json"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stations", nargs="+", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--threshold", type=int, required=True)
    parser.add_argument("--hours", type=int, default=648)
    parser.add_argument("--block-hours", type=int, default=72)
    parser.add_argument("--frozen-worker", action="store_true")
    main(parser.parse_args())
