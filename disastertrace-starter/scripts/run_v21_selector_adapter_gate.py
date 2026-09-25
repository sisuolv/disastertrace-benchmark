"""Run the offline Natural Track selector adapter gate.

The gate verifies that registered public selector priorities can choose from a
catalogue, obey a fixed query budget, and produce the same query sequence when
the source roster is serialized in a different order.  It does not access
outcomes, real data, providers, holdout, or quarantine.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from disastertrace.monitoring_v1.natural_selector_policy_v21 import CatalogueSelectorPolicy
from disastertrace.monitoring_v1.natural_track_v18 import NaturalKernel, NaturalSource
from disastertrace.monitoring_v1.synthetic_natural_v21 import target_card


def _kernel(order: list[str]) -> NaturalKernel:
    sources = {
        "opaque-a": NaturalSource("opaque-a", 0, {"visibility_m": 4000.0}),
        "opaque-b": NaturalSource("opaque-b", 0, {"visibility_m": 9000.0}),
        "opaque-c": NaturalSource("opaque-c", 0, {"visibility_m": 7000.0}),
    }
    return NaturalKernel([sources[key] for key in order], start=0, deadline=30, target=target_card())


def _run(selector_kind: str, order: list[str]) -> dict:
    kernel = _kernel(order)
    policy = CatalogueSelectorPolicy(selector_kind=selector_kind, seed=17, max_queries=2)
    trace = []
    while not kernel.public_state()["terminal"]:
        if len(trace) >= 8:
            raise RuntimeError("selector policy did not terminate")
        action = policy(kernel.public_state())
        result = kernel.step(action)
        trace.append({"kind": action.kind, "query_id": action.query_id, "result": result})
    return {
        "selector_kind": selector_kind,
        "retrieval_sequence": [row["query_id"] for row in trace if row["kind"] == "RETRIEVE"],
        "trace": trace,
        "query_count": sum(row["kind"] == "RETRIEVE" for row in trace),
        "terminal": kernel.public_state()["terminal"],
    }


def run(out: Path | None = None) -> dict:
    rows = []
    for kind in ("fixed_hash.v1", "round_robin_cycle.v1", "public_risk_age.v1"):
        original = _run(kind, ["opaque-a", "opaque-b", "opaque-c"])
        permuted = _run(kind, ["opaque-c", "opaque-a", "opaque-b"])
        rows.append(
            {
                "selector_kind": kind,
                "original": original,
                "permuted": permuted,
                "serialization_invariant": original["retrieval_sequence"] == permuted["retrieval_sequence"],
                "budget_ok": original["query_count"] == 2 and permuted["query_count"] == 2,
            }
        )
    artifact = {
        "schema": "disastertrace.v21.selector_adapter_gate.v1",
        "synthetic": True,
        "empirical": False,
        "provider_calls": 0,
        "outcome_accessed": False,
        "holdout_read": False,
        "quarantine_read": False,
        "rows": rows,
        "status": "PASS" if all(row["serialization_invariant"] and row["budget_ok"] for row in rows) else "FAIL",
        "claim_boundary": "This validates the Natural selector contract only; it is not a weather result or novelty claim.",
    }
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return artifact


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    artifact = run(args.out)
    print(json.dumps({"status": artifact["status"], "rows": len(artifact["rows"])}))
    return 0 if artifact["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
