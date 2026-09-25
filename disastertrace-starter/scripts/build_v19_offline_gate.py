#!/usr/bin/env python3
"""Build a self-contained v19 offline acceptance artifact.

The fixture intentionally contains process failures and a pending shared Y;
it never reads weather archives, calls a provider, or accesses outcomes.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from disastertrace.monitoring_v1.agent_view_v18 import public_checkpoint
from disastertrace.monitoring_v1.evidence_qualification_v18 import qualify_stream
from disastertrace.monitoring_v1.grid_scoring_v18 import score_complete_grid
from disastertrace.monitoring_v1.natural_track_v18 import NaturalAction, NaturalKernel, NaturalSource
from disastertrace.monitoring_v1.run_journal_v18 import RunJournal
from disastertrace.monitoring_v1.scoring import brier_report
from disastertrace.revision_v1.y1_adapter_synthetic import (
    settle_synthetic_outcomes,
    synthetic_metar,
    synthetic_provenance,
    v18_target_to_h15_target,
)
from scripts.build_v18_dev_episodes import _qualify_checkpoints
from scripts.validate_v18_run_spec import validate


def _record(revision: str, available: int, visibility: int) -> dict:
    return {
        "source_id": "offline-source",
        "source_revision": revision,
        "kind": "taf",
        "issued_at": available - 1,
        "available_at": available,
        "valid_start": 100,
        "valid_end": 200,
        "content": {"periods": [{"valid_start": 100, "valid_end": 200, "operator": "BASE", "visibility_m": visibility}]},
    }


def build(out: Path) -> dict:
    episode = {"episode_id": "OFFLINE-E1", "station": "KSFO", "target_start": 100, "target_end": 200, "as_of": 30}
    qualifications = qualify_stream([_record("r1", 10, 8000), _record("r2", 20, 4000)], target_start=100, target_end=200, as_of=30)
    public = public_checkpoint(episode, qualifications[1].to_dict())
    assert public["current_evidence"]["periods"][0]["visibility_m"] == 4000

    registrations = [
        {"target_id": "t", "method": method, "checkpoint_id": f"c{i}", "checkpoint_index": i,
         "base": 0.2, "fallback": 0.2, "outcome": None}
        for method in ("raw", "tool") for i in range(2)
    ]
    submissions = [
        {"target_id": "t", "method": "raw", "checkpoint_id": "c0", "status": "valid", "probability": 0.0},
        {"target_id": "t", "method": "raw", "checkpoint_id": "c1", "status": "stop"},
        {"target_id": "t", "method": "tool", "checkpoint_id": "c0", "status": "invalid"},
        {"target_id": "t", "method": "tool", "checkpoint_id": "c1", "status": "not_dispatched"},
    ]
    grid = score_complete_grid(registrations, submissions)
    bounds = grid["report"]["full_population_gain_bounds"]
    # Independent hand calculation for two checkpoints with shared Y.
    expected = [sum((0.2 - y) ** 2 - (p - y) ** 2 for p in (0.0, 0.2)) for y in (0, 1)]
    # Four rows have normalized method trajectories; each method contributes
    # one half to the overall target, so this is the direct mean of endpoint sums.
    assert math.isclose(bounds[0], min(expected) / 2, abs_tol=1e-12)
    assert math.isclose(bounds[1], max(expected) / 2, abs_tol=1e-12)

    conflict = score_complete_grid([
        {"target_id": "conflict", "method": "m", "checkpoint_id": "a", "checkpoint_index": 0, "base": 0.2, "fallback": 0.2, "outcome": 0},
        {"target_id": "conflict", "method": "m", "checkpoint_id": "b", "checkpoint_index": 1, "base": 0.2, "fallback": 0.2, "outcome": 1},
    ], [])
    assert conflict["report"]["inconsistent_target_groups"] == 1

    journal_path = out / "synthetic_run_journal"
    journal = RunJournal(journal_path, run_id="OFFLINE-GATE-001", scope="CODE", config={"model": "stub", "max_tokens": 32})
    journal.dispatch(request_id="r1", request_sha256="a" * 64, model="stub", settings={"max_tokens": 32})
    # Deliberately leave the journal open: this models an interruption after
    # dispatch intent and keeps the incomplete attempt in the denominator.
    manifest = {"schema": "disastertrace.v19.run_spec.v1", "run_id": "OFFLINE-GATE-SPEC-001",
                "scopes": ["CODE"], "permissions": {"CODE": True}}
    spec_result = validate(manifest)

    natural = NaturalKernel([NaturalSource("q", 0, {"visibility_m": 4000})], start=0, deadline=10)
    natural.step(NaturalAction("RETRIEVE", 0, query_id="q"))
    natural.step(NaturalAction("UPDATE", 0, probability=0.4))
    natural.step(NaturalAction("STOP", 0))

    # Track E (v20 plan): exercise the real T-60/T-40/T-20 checkpoint qualifier
    # on a synthetic stream (no real archive file), and settle a synthetic
    # outcome through the real Y1 adapter -- roster construction and outcome
    # settlement, chained end to end, entirely offline.
    checkpoint_stream = [_record("c1", 10, 8000), _record("c2", 40, 3000)]
    checkpoints, excluded_checkpoints = _qualify_checkpoints(
        checkpoint_stream, target_start=100, target_end=200,
        offsets={"T-60": 60, "T-40": 40, "T-20": 20},
    )
    outcome_target = v18_target_to_h15_target(
        episode_id="OFFLINE-E1", station="KSFO", target_start_us=100, target_end_us=200, threshold_m=5000.0,
    )
    outcome_prov = synthetic_provenance(fixture_label="offline-gate", fetch_timestamp_us=200)
    outcome_obs = [synthetic_metar(station="KSFO", observation_time_us=150, visibility_m=3000.0)]
    (outcome_record,) = settle_synthetic_outcomes(
        targets=[outcome_target], observations=outcome_obs, provenance=outcome_prov,
        resolution_version="OFFLINE-GATE-Y1-001",
    )
    assert outcome_record["availability_basis"] == "synthetic_fixture"
    assert outcome_record["value"] == 1  # 3000m < 5000m threshold

    # Track E fix (v20 plan): the module's real qualified name is
    # disastertrace.monitoring_v1.api_capture -- checking the bare string
    # "api_capture" against sys.modules could never match anything and this
    # check could never fire (independent review finding). Even with the
    # right name, this only proves the module wasn't imported by the time
    # build() returns -- api_capture.py reads its key-file path lazily
    # inside capture(), not at import time, so this check cannot catch a
    # call-time reach into it; it can only catch an import creeping into
    # this gate's own import chain. Disclosed, not solved here: a stronger
    # guarantee needs running build() in a fresh subprocess or a meta-path
    # import blocker, neither implemented this round.
    api_capture_imported = "disastertrace.monitoring_v1.api_capture" in sys.modules

    artifact = {
        "schema": "disastertrace.v19.offline_gate.v1",
        "status": "OFFLINE_READY",
        "raw_weather_accessed": False,
        "outcomes_accessed": False,
        "holdout_accessed": False,
        "provider_calls": 0,
        "public_view": public,
        "grid": {"comparison_eligible": grid["comparison_eligible"], "registered": grid["registered"],
                 "status_counts": grid["submission_status_counts"], "shared_y_bounds": bounds,
                 "hand_calculation": expected},
        "conflict_isolated": conflict["report"]["inconsistent_target_groups"],
        "journal_events": len((journal_path / "events.jsonl").read_text().splitlines()),
        "run_spec": spec_result,
        "natural": natural.public_state(),
        "checkpoint_grid": {
            "checkpoint_ids": [c["checkpoint_id"] for c in checkpoints],
            "excluded_checkpoints": len(excluded_checkpoints),
        },
        # A settled SYNTHETIC outcome (Track D adapter) is not the same claim
        # as "a real outcome was accessed" -- outcomes_accessed above stays
        # False, correctly, since nothing real was read.
        "synthetic_outcome_settled": True,
        "synthetic_outcome_availability_basis": outcome_record["availability_basis"],
        "api_capture_module_imported": api_capture_imported,
    }
    assert artifact["api_capture_module_imported"] is False, (
        "api_capture.py reads a real key-file path by default; the offline "
        "gate must never import it, not merely rely on a network guard to "
        "catch it after the fact"
    )
    out.mkdir(parents=True, exist_ok=True)
    (out / "OFFLINE_GATE.json").write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return artifact


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    artifact = build(args.out)
    print(json.dumps({"status": artifact["status"], "out": str(args.out / "OFFLINE_GATE.json")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
