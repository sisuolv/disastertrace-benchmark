"""Registered-set admission for derived C2 analyses, separate from F scoring."""

import hashlib
import json
from pathlib import Path

from .targets import canonical_hash


def load_bound_json(path, expected_sha256):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("Analysis input differs from its registered file hash")
    return json.loads(raw)


def _unique(rows, field, issues, label):
    indexed = {}
    for row in rows:
        key = row.get(field)
        if not isinstance(key, str) or not key or key in indexed:
            issues.append(f"{label}: missing or duplicate {field}")
        else:
            indexed[key] = row
    return indexed


def validate_branch_set(registration, artifacts):
    """Validate full registered opportunities and call lineage without requiring Y."""
    opportunities = registration["opportunity_ids"]
    if (not opportunities or len(opportunities) != len(set(opportunities))
            or not all(isinstance(o, str) and o for o in opportunities)
            or not registration["branches"]):
        raise ValueError("Nonempty unique opportunity and branch registration required")
    required = set(opportunities)
    rules = registration["branches"]
    issues, branches = [], {}
    expected_executions = {name for name, alias in rules.items() if alias is None}
    if set(artifacts) - expected_executions:
        issues.append("Unregistered physical execution")
    for name, alias in rules.items():
        actual = name if alias is None else alias
        if actual not in expected_executions:
            issues.append(f"{name}: alias must bind a registered non-alias execution")
            continue
        artifact = artifacts.get(actual)
        if artifact is None:
            issues.append(f"{name}: registered report missing")
            continue
        if artifact.get("parent_sha256") != registration["parent_sha256"]:
            issues.append(f"{name}: parent binding mismatch")
        for field in ("data_sha256", "bank_sha256"):
            if field in registration and artifact.get(field) != registration[field]:
                issues.append(f"{name}: {field} binding mismatch")
        if artifact.get("actions") is None or artifact.get("score_verified") is not True:
            issues.append(f"{name}: action trace or bound score qualification missing")
        report = artifact.get("report")
        if not isinstance(report, dict):
            issues.append(f"{name}: report missing")
            continue
        snaps = _unique(report.get("snapshots", []), "opportunity_id", issues, name + ":snapshots")
        if not required <= snaps.keys():
            issues.append(f"{name}: registered residual opportunities missing")
        if "all_opportunity_ids" in registration and set(snaps) != set(registration["all_opportunity_ids"]):
            issues.append(f"{name}: full opportunity roster changed")
        all_calls = _unique(report.get("calls", []), "call_id", issues, name + ":calls")
        for call in all_calls.values():
            if call.get("opportunity_id") not in snaps:
                issues.append(f"{name}: call has no registered snapshot")
        calls = {k: c for k,c in all_calls.items() if c.get("opportunity_id") in required}
        trace_rows = artifact.get("traces")
        if not isinstance(trace_rows, list):
            issues.append(f"{name}: required trace artifact missing")
            trace_rows = []
        traces = _unique(trace_rows, "call_id", issues, name + ":traces")
        if traces.keys() - all_calls.keys():
            issues.append(f"{name}: trace references unknown call")
        needed = {k for k,c in calls.items() if c.get("head") in registration["trace_heads"]}
        missing = needed - traces.keys()
        if missing:
            issues.append(f"{name}: required call traces missing: {sorted(missing)}")
        for key in needed & traces.keys():
            call, trace = calls[key], traces[key]
            if any(trace.get(f) != call.get(f) for f in
                   ("call_id", "opportunity_id", "started_at", "proposed_probability")):
                issues.append(f"{name}: trace does not bind actual call {key}")
            for field in ("claims", "features"):
                if field in trace and canonical_hash(trace[field]) != trace.get(field + "_sha256"):
                    issues.append(f"{name}: {field} trace hash mismatch {key}")
        branches[name] = {
            "execution": actual, "alias_of": alias,
            "registered_opportunities": len(required),
            "present_opportunities": len(required & snaps.keys()),
            "required_trace_calls": sorted(needed), "missing_trace_calls": sorted(missing),
            "opportunities_without_call": sorted(required - {c["opportunity_id"] for c in calls.values()}),
        }
    complete = not issues and set(branches) == set(rules)
    return {
        "schema": "disastertrace.c2_analysis_integrity.v1",
        "analysis_complete": complete, "issues": issues,
        "execution_complete": complete and all(a.get("execution_complete", False) for a in artifacts.values()),
        "registered_logical_branches": len(rules), "unique_executions": len(expected_executions),
        "registered_opportunities": len(required), "branches": branches,
        "expected_pair_count": len(rules) * (len(rules) - 1) // 2,
        "available_logical_branches": len(branches),
        "terminal_class": "completed" if complete else "incomplete_not_comparable",
        "formal_qualification": "derived_analysis_only; requires independently bound formal execution",
        "scientific_scope": "registered_residual_development_diagnostic",
        "requires_nonzero_effect": False,
    }
