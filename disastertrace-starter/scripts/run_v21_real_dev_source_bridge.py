"""Run the v21 selector contract against the bounded real dev TAF roster.

This bridge deliberately stops before outcomes or provider calls.  It converts
the already qualified source-only G1 artifact into the public Natural Track
catalogue and checks that each registered selector can run through a complete
retrieve/update/stop trace.  The result is a protocol/source integration gate,
not a forecast score.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from disastertrace.monitoring_v1.natural_selector_policy_v21 import CatalogueSelectorPolicy
from disastertrace.monitoring_v1.natural_track_v18 import NaturalAction, NaturalKernel, NaturalSource


SELECTORS = ("fixed_hash.v1", "round_robin_cycle.v1", "public_risk_age.v1")
FORBIDDEN = ("quarantine_holdout", "2025-02-17", "2025-02-18", "2025-02-19", "2025-02-20", "2025-02-21", "2025-02-22", "2025-02-23", "2025-02-24")


def _target(episode: Mapping[str, Any]) -> dict[str, Any]:
    base = {
        "entity": str(episode["station"]),
        "variable": "visibility",
        "threshold": 5000.0,
        "unit": "m",
        "comparison": "<",
        "observation_rule": "terminal observation in bounded dev target window",
        "target_start": int(episode["target_start"]),
        "target_end": int(episode["target_end"]),
        "contract_version": "v21.real-dev-source-only.v1",
    }
    base["contract_hash"] = hashlib.sha256(
        json.dumps(base, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return base


def _visibility_number(projection: Mapping[str, Any]) -> float | None:
    periods = projection.get("periods")
    if not isinstance(periods, list) or not periods:
        return None
    interval = periods[0].get("visibility_m")
    if not isinstance(interval, Mapping):
        return None
    lower = interval.get("lower")
    return float(lower) if isinstance(lower, (int, float)) and not isinstance(lower, bool) else None


def _sources(episode: Mapping[str, Any]) -> list[NaturalSource]:
    by_id: dict[str, NaturalSource] = {}
    for checkpoint in episode.get("checkpoints", []):
        for qualification in checkpoint.get("qualifications", []):
            witness = qualification.get("witness", {})
            identity = witness.get("source_identity")
            projection = witness.get("current_projection")
            if not isinstance(identity, Mapping) or not isinstance(projection, Mapping):
                continue
            query_id = identity.get("source_id")
            available_at = witness.get("available_at")
            if not isinstance(query_id, str) or not query_id:
                raise ValueError("real dev source identity is missing")
            if isinstance(available_at, bool) or not isinstance(available_at, int):
                raise ValueError("real dev source availability is not an integer")
            if query_id in by_id:
                continue
            by_id[query_id] = NaturalSource(
                query_id,
                available_at,
                {
                    "visibility_m": _visibility_number(projection),
                    "taf_projection": dict(projection),
                    "source_kind": identity.get("kind"),
                },
            )
    return [by_id[key] for key in sorted(by_id)]


def _run_episode(episode: Mapping[str, Any], selector_kind: str) -> dict[str, Any]:
    sources = _sources(episode)
    target = _target(episode)
    start = int(episode["target_start"]) - 3_600_000_000
    deadline = int(episode["target_end"])
    kernel = NaturalKernel(sources, start=start, deadline=deadline, target=target)
    policy = CatalogueSelectorPolicy(selector_kind=selector_kind, seed=17, max_queries=2)
    trace: list[dict[str, Any]] = []
    while not kernel.public_state()["terminal"]:
        if len(trace) >= 8:
            raise RuntimeError("selector did not terminate within protocol cap")
        state = kernel.public_state()
        action = policy(state)
        if not isinstance(action, NaturalAction):
            raise TypeError("selector returned a non-NaturalAction")
        result = kernel.step(action)
        trace.append({"kind": action.kind, "at": action.at, "query_id": action.query_id, "result": result})
    return {
        "episode_id": episode["episode_id"],
        "selector_kind": selector_kind,
        "source_count": len(sources),
        "retrieval_sequence": [row["query_id"] for row in trace if row["kind"] == "RETRIEVE"],
        "trace": trace,
        "terminal": kernel.public_state()["terminal"],
        "outcome_accessed_by_actor": False,
        "model_calls": 0,
    }


def run(source_artifact: Path, out: Path) -> dict[str, Any]:
    raw = source_artifact.read_text(encoding="utf-8")
    for term in FORBIDDEN:
        if term in raw:
            raise ValueError(f"forbidden scope marker in source artifact: {term}")
    data = json.loads(raw)
    if data.get("outcomes_accessed") is not False or data.get("model_calls") != 0 or data.get("holdout_accessed") is not False:
        raise ValueError("source artifact is not source-only")
    episodes = data.get("episodes")
    if not isinstance(episodes, list) or not episodes:
        raise ValueError("source artifact has no episodes")
    rows = [_run_episode(episode, selector) for episode in episodes for selector in SELECTORS]
    artifact = {
        "schema": "disastertrace.v21.real_dev_source_bridge.v1",
        "evidence_role": "BOUNDED_REAL_DEV_SOURCE_ONLY_PROTOCOL_GATE",
        "synthetic": False,
        "empirical": False,
        "source_only": True,
        "input_schema": data.get("schema"),
        "episode_count": len(episodes),
        "trace_count": len(rows),
        "selectors": list(SELECTORS),
        "outcomes_accessed": False,
        "provider_calls": 0,
        "model_calls": 0,
        "holdout_read": False,
        "quarantine_read": False,
        "status": "PASS" if all(row["terminal"] for row in rows) else "FAIL",
        "rows": rows,
        "claim_boundary": "The bridge validates bounded real TAF source semantics and the public selector protocol only; it is not a forecast score or novelty evidence.",
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    return artifact


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-artifact", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    artifact = run(args.source_artifact, args.out)
    print(json.dumps({"status": artifact["status"], "episodes": artifact["episode_count"], "traces": artifact["trace_count"]}))
    return 0 if artifact["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
