"""Stdlib-only offline verification after relocating the follow-up package."""

import hashlib
import json
import socket
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "source"))

from disastertrace.monitoring_fixed_v1.admission import AdmissionEngine, score_admitted
from disastertrace.monitoring_fixed_v1.contracts import EvidenceBundle, Target
from disastertrace.monitoring_fixed_v1.support_bridge import (
    native_slot_support,
    taf_coverage,
    taf_version_support,
)
from disastertrace.monitoring_v1.preparation import score_preparation
from disastertrace.monitoring_v1.reachability import (
    Goal,
    Query,
    Witness,
    validate_witness,
)
from disastertrace.monitoring_v1.resources import Cost
from disastertrace.monitoring_v1.scoring import brier_report
from disastertrace.monitoring_v1.state import MonitoringEngine


def denied(*args, **kwargs):
    raise RuntimeError("Network is disabled in portable replay")


def load(path):
    return json.loads(path.read_text())


def main():
    socket.create_connection = denied
    socket.socket.connect = denied
    manifest = load(HERE / "MANIFEST.json")
    for name, expected in manifest["files"].items():
        path = HERE / name
        if not path.resolve().is_relative_to(HERE):
            raise ValueError("Invalid package path")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Package changed: " + name)
    report_root = HERE / "reports"
    sessions = 0
    for name, report_file, arm_names in [
        (
            "admission_02",
            "ADMISSION_REPORT.json",
            ["follow", "common_only", "fixed_one", "all_registered"],
        ),
        (
            "model_smoke_02",
            "REPORT.json",
            ["follow"]
            + [
                h + "." + c
                for h in ("f_only", "joint")
                for c in ("common_only", "fixed_one", "all_registered")
            ],
        ),
        (
            "scalar_admission_01",
            "SCALAR_ADMISSION_REPORT.json",
            ["ensemble_mean", "ensemble_median"],
        ),
    ]:
        root = report_root / name
        expected = load(root / report_file)
        if name.startswith("model"):
            expected = expected["F"]
        score = score_admitted(
            load(root / "OUTCOME_REFERENCES.json"),
            {a: root / (a + ".jsonl") for a in arm_names},
        )
        for key in (
            "contract_sha256",
            "outcome_sha256",
            "scores",
            "admission_statuses",
        ):
            if score[key] != expected[key]:
                raise ValueError("Reconstructed scoring differs: " + name + " " + key)
        sessions += len(arm_names)
    for condition in ("common_only", "fixed_one", "all_registered"):
        AdmissionEngine.from_journal(
            report_root / "model_smoke_02" / ("e_only." + condition + ".jsonl")
        )
        sessions += 1
    support_root = report_root / "support_01"
    fixtures = [
        json.loads(line)
        for line in (support_root / "E_FIXTURES.jsonl").read_text().splitlines()
    ]
    for item in fixtures:
        b = EvidenceBundle.restore(
            load(HERE / "fixed_inputs" / (item["call_id"] + ".json"))
        )
        if (
            native_slot_support(b) != item["E_report"]
            or taf_coverage(b) != item["TAF_coverage"]
        ):
            raise ValueError("Native support reconstruction mismatch")
    versions = load(support_root / "REAL_TAF_VERSION_FIXTURES.json")
    for v in versions:
        t = Target(**v["target"])
        for key, source_list in [
            ("before", v["disclosed_sources"][:1]),
            ("after", v["disclosed_sources"]),
        ]:
            if taf_version_support(source_list, t, at=v[key]["at"]) != v[key]:
                raise ValueError("Native version reconstruction mismatch")
    graph = load(support_root / "JOINT_WITNESSES.json")
    queries = [
        Query(q, Cost(**r["cost"]), r["released_at"], r["duration"])
        for q, r in graph["query_metadata"].items()
    ]
    goals = [
        Goal(
            r["target_id"],
            r["deadline"],
            tuple(frozenset(x) for x in r["alternatives"]),
        )
        for r in graph["goals"]
    ]
    witnesses = 0
    for case in graph["cases"]:
        for row in case["result"]["frontier"]:
            w = Witness(
                tuple(tuple(x) for x in row["starts"]),
                tuple(row["resolved"]),
                Cost(**row["cost"]),
                row["completion_time"],
            )
            validate_witness(
                w,
                queries,
                goals,
                case["limits"],
                concurrency=case["concurrency"],
                start=case["start"],
            )
            witnesses += 1
    branch = report_root / "branch_01"
    branch_y = {r["target_id"]: r for r in load(branch / "OUTCOME_REFERENCES.json")}
    for name, expected in load(branch / "BRANCH_LOSSES.json")["scores"].items():
        record = load(branch / (name + "-result.json"))["report"]
        engine = MonitoringEngine.restore(record["event_replay"])
        if list(engine.snapshots.values()) != record["snapshots"]:
            raise ValueError("Branch state mismatch")
        rows = [
            {
                "opportunity_id": s["opportunity_id"],
                "base": s["base_probability"],
                "prediction": s["probability"],
                "outcome": branch_y[s["target_id"]]["outcome"],
                "region": "bay",
                "source": "native_IEM_METAR",
                "maturity": branch_y[s["target_id"]]["status"],
                "baseline_kind": s["baseline_kind"],
            }
            for s in engine.snapshots.values()
        ]
        if brier_report(rows) != expected:
            raise ValueError("Branch loss reconstruction mismatch")
    preparation = report_root / "preparation_01"
    for name, expected in load(preparation / "PREPARATION_SYNTHETIC_REPORT.json")[
        "cases"
    ].items():
        engine = AdmissionEngine.from_journal(preparation / (name + ".jsonl"))
        score = score_preparation(
            engine.preparation, {"j1": 1, "j2": 1}, miss_penalty=10
        )
        if (
            score != expected["score"]
            or engine.preparation.to_dict() != expected["preparation"]
        ):
            raise ValueError("Preparation reconstruction mismatch")
        sessions += 1
    print(
        json.dumps(
            {
                "passed": True,
                "network_disabled": True,
                "manifest_files": len(manifest["files"]),
                "typed_session_journals": sessions,
                "native_support_bundles": len(fixtures),
                "native_version_pairs": len(versions),
                "independently_validated_witnesses": witnesses,
                "branch_states_and_losses": 4,
                "actual_new_model_calls": 0,
                "scope": "relocated source/receipts/scorers, not a new GPU inference or upstream-source authentication",
            }
        )
    )


if __name__ == "__main__":
    main()
