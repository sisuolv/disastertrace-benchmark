"""Synthetic Original/Repair/Sham controller for v21."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any

from .active_policy_v21 import ContentAwareSyntheticPolicy
from .interventions_v18 import REPAIR_APPLIED, apply_intervention
from .natural_track_v18 import NaturalAction, NaturalKernel, NaturalSource, replay_suffix
from .synthetic_natural_v21 import target_card


def _parent_snapshot() -> dict[str, Any]:
    env = NaturalKernel(
        [
            NaturalSource("q0", 0, {"visibility_m": 4000}),
            NaturalSource("q1", 0, {"visibility_m": 3000}),
        ],
        start=0,
        deadline=20,
        target=target_card(),
    )
    env.step(NaturalAction("RETRIEVE", 0, query_id="q0"))
    snapshot = env.snapshot()
    # Inject one explicitly identified wrong cache value.  It is not an
    # evaluator gold value; the kernel's source history proves the mismatch.
    snapshot["read"]["q0"] = {"visibility_m": 9999}
    return snapshot


def run_repair_trial() -> dict[str, Any]:
    parent = _parent_snapshot()
    records = [
        {
            "source_id": "synthetic",
            "source_revision": "r1",
            "kind": "fixture",
            "issued_at": 0,
            "available_at": 0,
            "valid_start": 0,
            "valid_end": 20,
            "content": {"visibility_m": 4000},
        },
        {
            "source_id": "synthetic",
            "source_revision": "r2",
            "kind": "fixture",
            "issued_at": 1,
            "available_at": 1,
            "valid_start": 0,
            "valid_end": 20,
            "content": {"visibility_m": 3000},
        },
    ]
    result = apply_intervention(
        records,
        "repair",
        target_start=0,
        target_end=20,
        kernel_snapshot=parent,
        corrected_state_patch={"read": {"q0": None}},
        repair_policy=lambda: ContentAwareSyntheticPolicy(),
        max_actions=6,
    )
    if result.status != REPAIR_APPLIED:
        raise AssertionError(f"expected a real repair, got {result.status}")
    # Sham uses the same replay controller and action budget but does not alter
    # semantic state.  Equality is a required negative control.
    sham_trace = replay_suffix(parent, ContentAwareSyntheticPolicy(), max_actions=6)
    source_digest = hashlib.sha256(
        json.dumps(parent["sources"], sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "schema": "disastertrace.v21.repair_trial.v1",
        "evidence_role": "SYNTHETIC_PROTOCOL_CHECK",
        "synthetic": True,
        "empirical": False,
        "status": result.status,
        "original_trace": deepcopy(result.control_trace),
        "repair_trace": deepcopy(result.natural_trace),
        "sham_trace": sham_trace,
        "repair_witness": result.repair_witness,
        "sham_matches_original": sham_trace == result.control_trace,
        "repair_changes_suffix": result.natural_trace != result.control_trace,
        "sources_unchanged": result.repair_witness["sources_sha256"] == source_digest,
        "interpretation": "The repaired cache changes which suffix query is selected; this proves state use, not a real-world gain.",
    }
