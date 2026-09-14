"""Fixed shared-information contracts for single/multiple target X09 probes."""

import json
import math

from .contracts import EvidenceBundle, canonical, fingerprint

HEAD_FIELDS = {
    "e_only": {"target_id", "fact_truth"},
    "f_only": {"target_id", "probability"},
    "joint": {"target_id", "fact_truth", "probability"},
}


def build_joint_context(bundles, *, access_mode):
    """Declare a new shared fixed-input condition, never a private-session arm."""
    if access_mode != "shared_disclosed_union":
        raise ValueError("Joint probes require explicit shared disclosed information")
    bundles = list(bundles)
    if not 2 <= len(bundles) <= 8 or any(not isinstance(b, EvidenceBundle) for b in bundles):
        raise ValueError("A joint cohort needs two to eight qualified bundles")
    views = [b.policy_view() for b in bundles]
    tids = sorted(row["target"]["target_id"] for row in views)
    if len(set(tids)) != len(tids):
        raise ValueError("Unique targets required in a joint cohort")
    cohort_keys = {
        canonical(
            {
                "cutoff": row["cutoff"],
                "protocol": row["state"]["protocol"],
                "availability_basis": row["availability_basis"],
                "target": {
                    k: v for k, v in row["target"].items() if k not in {"target_id", "entity"}
                },
            }
        )
        for row in views
    }
    if len(cohort_keys) != 1:
        raise ValueError("Different target/time/protocol questions need separate cohorts")
    sources, completed = {}, {}
    for row in views:
        if row["target"]["output_kind"] != "event_probability":
            raise ValueError("This joint contract requires probability targets")
        for asset in row["assets"]:
            aid = asset["asset_id"]
            immutable = {
                k: v
                for k, v in asset.items()
                if k not in {"entitlements", "receipt_ids", "completed_at"}
            }
            if aid in sources and immutable != sources[aid]:
                raise ValueError("Conflicting source identity requires explicit resolution")
            sources[aid] = immutable
            # The diagnostic grants sharing only after every original view is legal.
            completed[aid] = max(completed.get(aid, asset["completed_at"]), asset["completed_at"])
    targets = [
        {k: row[k] for k in ("opportunity_id", "target", "cutoff", "baseline", "state")}
        for row in sorted(views, key=lambda r: r["target"]["target_id"])
    ]
    context = {
        "schema": "disastertrace.joint_target_context.v1",
        "access_mode": access_mode,
        "cutoff": views[0]["cutoff"],
        "targets": targets,
        "shared_sources": [
            {**sources[aid], "completed_at": completed[aid], "entitlements": tids}
            for aid in sorted(sources)
        ],
        "original_bundle_bindings": sorted(
            [
                {"target_id": row["target"]["target_id"], "bundle_hash": b.bundle_hash}
                for row, b in zip(views, bundles)
            ],
            key=lambda r: r["target_id"],
        ),
        "information_rule": "Every single-target and multi-target call sees this entire identical context, including all common forecasts and all shared sources.",
        "resource_scope": "Fixed disclosed information diagnostic; inherited individual acquisition receipts are not a new shared-session cost measurement.",
    }
    context = json.loads(canonical(context))
    return {**context, "context_sha256": fingerprint(context)}


def _scope(context, answer_target_ids, head):
    if head not in HEAD_FIELDS:
        raise ValueError("Unregistered joint output head")
    payload = {k: v for k, v in context.items() if k != "context_sha256"}
    if context.get("context_sha256") != fingerprint(payload):
        raise ValueError("Joint context hash mismatch")
    registered = {row["target"]["target_id"] for row in context["targets"]}
    if (
        not isinstance(answer_target_ids, list)
        or not answer_target_ids
        or any(not isinstance(tid, str) for tid in answer_target_ids)
        or len(set(answer_target_ids)) != len(answer_target_ids)
        or not set(answer_target_ids) <= registered
    ):
        raise ValueError("Answer scope must contain unique registered target IDs")
    return set(answer_target_ids)


def joint_messages(context, answer_target_ids, *, head):
    _scope(context, answer_target_ids, head)
    system = (
        "Use only the complete shared context supplied in this request. All timestamps are UTC microseconds. "
        "Every source and common forecast in context is visible for every target; answer only answer_target_ids. "
        "Do not retrieve external sources or use memorized weather outcomes. "
        "Return one JSON object with exactly answers, a list with exactly one entry per requested target. "
        "Each entry contains exactly " + ", ".join(sorted(HEAD_FIELDS[head])) + ". "
        "Do not include explanations, markdown, omitted targets or unrequested targets. "
    )
    if head in {"e_only", "joint"}:
        system += (
            "For each target, E_question is in baseline.content. It concerns PAST registered neighbor report slots. "
            "The proposition is existential: at least one registered slot reported visibility strictly below threshold_m. "
            "fact_truth is one of the JSON strings true, false, unknown, conflict, never a JSON boolean. "
            "Return true when a disclosed registered report interval proves the proposition. "
            "Return false only when EVERY registered slot is disclosed and its interval proves visibility is not below threshold. "
            "Unqueried, missing or unresolved slots require unknown unless a disclosed registered slot already proves the proposition. "
            "Use open/closed interval endpoints in meters. Use conflict only for inconsistent source facts. "
            "Facts are defined by the declared product support assumptions, not error-free physical weather. "
        )
    if head in {"f_only", "joint"}:
        system += (
            "probability must be a finite number from zero to one for that target's future event contract. "
            "Use its common forecast and any relevant disclosed evidence. You may retain the baseline probability or revise it. "
            "The baseline mapping's fit period and transfer limitations are disclosed in baseline.content. "
            "E uncertainty does not force probability one half, and a resolved past fact does not determine the future event. "
        )
    return [
        {"role": "system", "content": system.strip()},
        {
            "role": "user",
            "content": canonical(
                {
                    "context": context,
                    "answer_target_ids": answer_target_ids,
                }
            ),
        },
    ]


def _unique_keys(pairs):
    row = {}
    for key, value in pairs:
        if key in row:
            raise ValueError("Duplicate JSON key")
        row[key] = value
    return row


def parse_joint_response(raw, context, answer_target_ids, *, head):
    expected = _scope(context, answer_target_ids, head)
    if not isinstance(raw, str):
        raise ValueError("A raw JSON response is required")
    result = json.loads(raw, object_pairs_hook=_unique_keys)
    if (
        not isinstance(result, dict)
        or set(result) != {"answers"}
        or not isinstance(result["answers"], list)
    ):
        raise ValueError("Wrong joint response envelope")
    answers = {}
    for row in result["answers"]:
        if not isinstance(row, dict) or set(row) != HEAD_FIELDS[head]:
            raise ValueError("Wrong per-target response fields")
        tid = row["target_id"]
        if not isinstance(tid, str) or tid not in expected or tid in answers:
            raise ValueError("Missing, duplicated or unrequested response target")
        if head in {"e_only", "joint"} and (
            not isinstance(row["fact_truth"], str)
            or row["fact_truth"] not in {"true", "false", "unknown", "conflict"}
        ):
            raise ValueError("Wrong factual truth type/value")
        if head in {"f_only", "joint"} and (
            type(row["probability"]) not in (int, float)
            or not math.isfinite(row["probability"])
            or not 0 <= row["probability"] <= 1
        ):
            raise ValueError("Probability must be finite and in range")
        answers[tid] = row
    if set(answers) != expected:
        raise ValueError("Every requested target must have exactly one answer")
    return answers
