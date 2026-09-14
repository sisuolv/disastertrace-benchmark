"""Freeze and run synthetic fixed-F preparation controls with separate replay."""

import copy
import hashlib
import itertools
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from disastertrace.monitoring_fixed_v1.admission import (
    AdmissionEngine,
    TypedOpportunity,
)
from disastertrace.monitoring_fixed_v1.contracts import Forecast, Target, fingerprint
from disastertrace.monitoring_fixed_v1.decision_baselines import act, choose_preparation
from disastertrace.monitoring_v1.preparation import score_preparation
from disastertrace.monitoring_v1.spool_backend import publish, read

HERE = Path(__file__).resolve().parents[1]
OUT = HERE / "preparation_controls_01"
US = 1_000_000
METHODS = ["no_preparation", "threshold", "edf", "rolling_two_step"]


def cards():
    base = {
        "schema": "disastertrace.preparation_scenario.v1",
        "kind": "research_assumption",
        "capacity": 1,
        "budget": 14,
        "units": "synthetic_cost_units",
        "jobs": [
            {
                "job_id": "j" + str(i),
                "target_id": "t" + str(i),
                "deadline": deadline * US,
                "duration": duration * US,
                "expires_at": expiry * US,
                "cost": cost,
                "cleanup_duration": 5 * US,
                "cleanup_cost": 1,
            }
            for i, (deadline, duration, expiry, cost) in enumerate(
                [(50, 10, 60, 3), (35, 10, 40, 3), (70, 15, 75, 4)]
            )
        ],
    }
    result = []
    for name in (
        "one_capacity",
        "two_capacity",
        "budget_limited",
        "inherited_preparation",
        "early_expiry",
        "tight_deadline",
    ):
        card = copy.deepcopy(base)
        initial = []
        probabilities = {"j0": 0.45, "j1": 0.85, "j2": 0.7}
        if name == "two_capacity":
            card["capacity"] = 2
        elif name == "budget_limited":
            card["budget"] = 7
        elif name == "inherited_preparation":
            initial = [{"job_id": "j0", "at": 0}]
            probabilities["j0"] = 0.05
            card["jobs"][0].update(duration=30 * US, expires_at=75 * US)
        elif name == "early_expiry":
            card["jobs"][1]["expires_at"] = 20 * US
        elif name == "tight_deadline":
            card["jobs"][1]["deadline"] = 12 * US
            card["jobs"][1]["expires_at"] = 20 * US
        result.append(
            {
                "id": name,
                "card": card,
                "probabilities": probabilities,
                "initial": initial,
                "miss_penalty": 10,
                "decision_ticks": [t * US for t in range(5, 76, 5)],
            }
        )
    return result


def build_engine(spec):
    targets = [
        Target(
            j["target_id"],
            "synthetic:" + j["target_id"],
            "synthetic_demand",
            "indicator",
            "event_probability",
            "point",
            100 * US,
            100 * US,
            "future_physical",
            "synthetic_demand_card.v1",
            event_operator="ge",
            threshold=1,
        )
        for j in spec["card"]["jobs"]
    ]
    probabilities = {
        j["target_id"]: spec["probabilities"][j["job_id"]] for j in spec["card"]["jobs"]
    }
    engine = AdmissionEngine(
        [TypedOpportunity("forecast-" + t.target_id, t, 90 * US) for t in targets],
        fallbacks={
            t.target_id: Forecast(
                t.contract_hash,
                "event_probability",
                "probability",
                probabilities[t.target_id],
            ).to_dict()
            for t in targets
        },
        preparation=spec["card"],
    )
    for i, row in enumerate(spec["initial"]):
        act(engine, ("prepare", row["job_id"]), row["at"], event_id="initial-" + str(i))
    return engine


def finish(engine, spec, method, start=0, directory=None):
    choices = []
    for index, at in enumerate(spec["decision_ticks"]):
        if index < start:
            continue
        engine.run([], until=at)
        action = choose_preparation(
            engine,
            spec["probabilities"],
            method=method,
            at=at,
            next_at=at + 5 * US,
            miss_penalty=spec["miss_penalty"],
        )
        act(engine, action, at + 1, event_id="decision-" + str(index))
        choices.append({"at": at, "action_at": at + 1, "action": action})
        if index == 3 and directory is not None:
            publish(directory / "BRANCH_CHECKPOINT.json", engine.export())
            publish(
                directory / "BRANCH_REQUEST.json",
                {
                    "spec": spec,
                    "method": method,
                    "next_tick": index + 1,
                    "checkpoint_sha256": fingerprint(engine.export()),
                    "loads_future_demands": False,
                },
            )
    engine.run([], until=101 * US)
    return choices


def continuation(directory):
    request = read(directory / "BRANCH_REQUEST.json")
    checkpoint = read(directory / "BRANCH_CHECKPOINT.json")
    assert fingerprint(checkpoint) == request["checkpoint_sha256"]
    engine = AdmissionEngine.restore(checkpoint)
    finish(engine, request["spec"], request["method"], request["next_tick"])
    publish(
        directory / "BRANCH_RESULT.json",
        {"checkpoint": engine.export(), "preparation": engine.preparation.to_dict()},
    )


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "continue":
        continuation(Path(sys.argv[2]))
        return
    OUT.mkdir(exist_ok=False)
    source = OUT / "source"
    source.mkdir()
    package = HERE.parents[1] / "disastertrace-starter/src/disastertrace"
    for module in ("monitoring_v1", "monitoring_fixed_v1"):
        shutil.copytree(
            package / module,
            source / "disastertrace" / module,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
    (source / "disastertrace/__init__.py").write_text(
        '"""Frozen synthetic decision controls."""\n'
    )
    shutil.copyfile(Path(__file__), source / "execute_preparation_controls.py")
    plan = {
        "schema": "disastertrace.fixed_f_preparation_comparison.v1",
        "cases": cards(),
        "methods": METHODS,
        "scenario_kind": "synthetic_research_assumption",
        "new_model_calls": 0,
        "outcomes": "Enumerate all eight binary demand vectors only in the evaluator after control trajectories finish.",
        "fixed_F": "Identical constant probabilities in every method; no forecast inference or hidden future updates.",
        "planner": "Exactly enumerate two decision steps with current probabilities held constant and projected readiness terminal cost; not global optimality.",
        "dispatch": "One action per public5-second tick, dispatched1microsecond after that processed boundary.",
        "legacy_capacity": "Ready protection occupies capacity until expiry or cancellation, including cleanup; closed deadlines are not rewritten.",
        "recovery": "D-only AdmissionEngine preparation branches; not a combined source/model/D SessionCoordinator qualification.",
        "source": {
            str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in source.rglob("*.py")
        },
    }
    publish(OUT / "DECISION_SPEC.json", plan)
    results = []
    for spec in plan["cases"]:
        forecasts = None
        for method in METHODS:
            directory = OUT / (spec["id"] + "__" + method)
            directory.mkdir()
            before = time.process_time()
            engine = build_engine(spec)
            choices = finish(engine, spec, method, directory=directory)
            cpu_seconds = time.process_time() - before
            publish(directory / "DECISIONS.json", choices)
            publish(directory / "FINAL_CHECKPOINT.json", engine.export())
            engine.write_journal(directory / "admission.jsonl")
            restored = AdmissionEngine.from_journal(directory / "admission.jsonl")
            assert restored.export() == engine.export()
            assert restored.preparation.to_dict() == engine.preparation.to_dict()
            current_forecasts = {
                oid: row["forecast"] for oid, row in engine.snapshots.items()
            }
            if forecasts is None:
                forecasts = current_forecasts
            assert current_forecasts == forecasts
            command = [
                sys.executable,
                str(source / "execute_preparation_controls.py"),
                "continue",
                str(directory),
            ]
            publish(directory / "CONTINUATION_COMMAND.json", {"command": command})
            with (directory / "continuation.log").open("x") as log:
                r = subprocess.run(
                    command,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    check=False,
                    env=dict(
                        os.environ, PYTHONPATH=str(source), PYTHONDONTWRITEBYTECODE="1"
                    ),
                )
            publish(directory / "CONTINUATION_EXIT.json", {"exit_code": r.returncode})
            assert r.returncode == 0
            branch = read(directory / "BRANCH_RESULT.json")
            assert (
                branch["checkpoint"] == engine.export()
                and branch["preparation"] == engine.preparation.to_dict()
            )
            demand_rows, weighted = [], 0.0
            for vector in itertools.product((0, 1), repeat=3):
                demand = dict(zip(sorted(engine.preparation.jobs), vector, strict=True))
                score = score_preparation(
                    restored.preparation, demand, miss_penalty=spec["miss_penalty"]
                )
                weight = 1.0
                for jid, value in demand.items():
                    p = spec["probabilities"][jid]
                    weight *= p if value else 1 - p
                weighted += weight * score["total_cost"]
                demand_rows.append(
                    {
                        "synthetic_demand": demand,
                        "independent_bernoulli_weight": weight,
                        "score": score,
                    }
                )
            expected = restored.preparation.spent + sum(
                spec["probabilities"][jid] * spec["miss_penalty"]
                for jid, snapshot in restored.preparation.snapshots.items()
                if not snapshot["ready"]
            )
            assert abs(weighted - expected) < 1e-9
            publish(directory / "EVALUATOR_ONLY_SYNTHETIC_DEMANDS.json", demand_rows)
            row = {
                "case": spec["id"],
                "method": method,
                "expected_synthetic_loss": expected,
                "preparation_cost": restored.preparation.spent,
                "ready_jobs": sum(
                    s["ready"] for s in restored.preparation.snapshots.values()
                ),
                "all_jobs": len(restored.preparation.jobs),
                "all_demand_vectors": len(demand_rows),
                "cpu_seconds": cpu_seconds,
                "measured_cpu_cost_charged_to_synthetic_budget": False,
                "independent_journal_replay": True,
                "cross_process_preparation_branch_equal": True,
                "common_forecasts_unchanged": True,
                "native_weather_data": False,
                "actual_model_calls": 0,
            }
            publish(directory / "VALIDATION.json", row)
            results.append(row)
            print(json.dumps(row), flush=True)
    publish(
        OUT / "VALIDATION.json",
        {
            "passed": True,
            "trajectories": len(results),
            "results": results,
            "total_demand_vector_settlements": len(results) * 8,
            "new_model_calls": 0,
            "scientific_scope": "Fixed-F synthetic D-sim engineering; costs and risk probabilities are research assumptions, not operational weather benefits.",
        },
    )


if __name__ == "__main__":
    main()
