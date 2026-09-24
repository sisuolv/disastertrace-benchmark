#!/usr/bin/env python3
"""Offline validation scaffold for a v18 development-empirical-analysis spec (Batch V4, task A1).

Only ``--validate-only`` is implemented, deliberately. Y1 (outcome settlement) and a calibrated
B1 baseline are both unauthorized/unavailable this round, so there is no real data for this
script to analyze yet -- running a real analysis would either fail for lack of input or have to
fabricate one, and neither is acceptable. This scaffold instead validates that an analysis
*spec* is well-formed and, given the spec's own self-declared evidence tiers, determines which
claim types are even structurally evaluable -- reusing the same offline-safety pattern already
established in validate_v18_run_spec.py (sensitive-key/path scanning, no external calls).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

CLAIM_TYPES = {"forecast_gain", "calibration", "ranking", "live_agent", "generalization"}

# What each claim type structurally requires before it can be anything other than
# NOT_EVALUABLE/NOT_TESTED -- matches CODEX_NEXT_TASKS.md / PAPER_READINESS_DECISION.md's own
# reasoning, expressed as machine-checkable requirements instead of only prose.
REQUIRED_EVIDENCE_TIERS: dict[str, set[str]] = {
    "forecast_gain": {"baseline_calibrated", "outcome_authorized"},
    "calibration": {"outcome_authorized"},
    "ranking": {"common_cohort_locked", "outcome_authorized"},
    "live_agent": {"prospective_agent_authorized"},
    "generalization": {"extension_executed_with_real_data"},
}

KNOWN_EVIDENCE_TIERS = {
    "baseline_interface_ready",
    "baseline_calibrated",
    "outcome_authorized",
    "common_cohort_locked",
    "prospective_agent_authorized",
    "extension_executed_with_real_data",
}

SENSITIVE = re.compile(r"(?:api[_-]?key|authorization|bearer|(?:^|[_-])token(?:$|[_-])|secret|password|credential)", re.I)


def _walk(value: Any, path: str = "root"):
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield path, str(key), item
            yield from _walk(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk(item, f"{path}[{index}]")


def validate(spec: Mapping[str, Any]) -> dict[str, Any]:
    if spec.get("schema") != "disastertrace.v19.analysis_spec.v1":
        raise ValueError("Unsupported analysis-spec schema")
    analysis_id = spec.get("analysis_id")
    if not isinstance(analysis_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}", analysis_id):
        raise ValueError("analysis_id must be a stable unique identifier")
    claims = spec.get("claims")
    if not isinstance(claims, list) or not claims or any(c not in CLAIM_TYPES for c in claims):
        raise ValueError("claims must be a nonempty list drawn from " + repr(sorted(CLAIM_TYPES)))
    evidence_tiers = spec.get("evidence_tiers", [])
    if not isinstance(evidence_tiers, list) or any(t not in KNOWN_EVIDENCE_TIERS for t in evidence_tiers):
        raise ValueError("evidence_tiers must be a list drawn from " + repr(sorted(KNOWN_EVIDENCE_TIERS)))
    evidence_set = set(evidence_tiers)

    for path, key, value in _walk(spec):
        if SENSITIVE.search(key):
            raise ValueError(f"Sensitive key is forbidden at {path}.{key}")
        if isinstance(value, str) and SENSITIVE.search(value):
            raise ValueError("Credential-like text is forbidden in analysis specs")
        if isinstance(value, str) and any(part in value.split("/") for part in ("data_real_v16", "quarantine_holdout")):
            raise ValueError("Raw/holdout paths are not accepted by offline validation")

    claim_status: dict[str, dict[str, Any]] = {}
    for claim in claims:
        required = REQUIRED_EVIDENCE_TIERS[claim]
        missing = sorted(required - evidence_set)
        claim_status[claim] = (
            {"status": "STRUCTURALLY_EVALUABLE", "missing_evidence": []}
            if not missing
            else {"status": "NOT_EVALUABLE", "missing_evidence": missing}
        )

    canonical = json.dumps(spec, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return {
        "valid": True,
        "analysis_id": analysis_id,
        "claims": claims,
        "claim_status": claim_status,
        "spec_sha256": hashlib.sha256(canonical).hexdigest(),
        "external_calls": 0,
        "raw_weather_accessed": False,
        "outcomes_accessed": False,
        "holdout_accessed": False,
        "note": "Structural evaluability only. STRUCTURALLY_EVALUABLE means the declared "
        "evidence tiers satisfy this claim type's minimum prerequisites; it is not a claim "
        "that the analysis has been run or that the underlying evidence is actually true.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--validate-only", action="store_true", help="required; no other mode is implemented")
    args = parser.parse_args()
    if not args.validate_only:
        parser.error("Only --validate-only is implemented this round; Y1/B1 real inputs are unauthorized")
    spec = json.loads(args.manifest.read_text(encoding="utf-8"))
    result = validate(spec)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
