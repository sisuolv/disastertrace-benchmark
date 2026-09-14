"""Provider-qualified evidence support and evaluator-only finite E recipes."""

import math
from datetime import datetime, timezone
from itertools import combinations, pairwise

from ..monitoring_v1.providers.aviation import parse_metar, parse_taf
from ..monitoring_v1.support import EvidenceFact, Interval, classify, public_support
from .contracts import EvidenceBundle, Target, fingerprint


def iso(at):
    return datetime.fromtimestamp(at / 1_000_000, timezone.utc).isoformat()


def certified_metadata(reference_kind, support_assumption, visible_scope):
    if visible_scope != "policy_after_query":
        raise ValueError("Only disclosed evidence can enter public support")
    mapping = {
        ("product_label", "product_exact"): ("product_label", "product_exact", "policy"),
        ("measurement", "bounded_error"): ("measurement", "bounded_measurement", "policy"),
        ("model_estimate", "model_estimate"): ("model_estimate", "model_estimate", "policy"),
        ("raw_sensor", "raw_only"): ("raw_image", "coverage_only", "policy"),
    }
    try:
        return mapping[reference_kind, support_assumption]
    except KeyError as exc:
        raise ValueError("Reference and support assumption lack a certified mapping") from exc


def native_slot_support(bundle, *, at=None):
    row = bundle.policy_view()
    at = row["cutoff"] if at is None else at
    if at > row["cutoff"] or row["provider_version"] != "native_h15_snapshot.v1":
        raise ValueError("Unsupported provider/time for native report support")
    question = row["baseline"]["content"]["E_question"]
    if question["predicate"] != "any_registered_neighbor_slot_below_threshold":
        raise ValueError("Unqualified factual predicate")
    ids = question["query_ids"]
    if not ids or len(set(ids)) != len(ids):
        raise ValueError("Unique registered report slots required")
    grouped = {qid: [] for qid in ids}
    for asset in row["assets"]:
        qid = asset["content"]["query_id"]
        if qid in grouped and asset["completed_at"] <= at:
            grouped[qid].append(asset)
    slots = []
    for qid in ids:
        assets = grouped[qid]
        # Equal upstream availability does not establish an ordering; conflicting
        # coexisting versions then intersect instead of silently choosing a hash.
        times = sorted({a["available_at"] for a in assets})
        facts, provenance = [], []
        for asset in assets:
            reference, assumption, scope = certified_metadata(
                asset["reference_kind"],
                asset["support_assumption"],
                asset["visible_information_scope"],
            )
            if reference != "product_label" or assumption != "product_exact":
                raise ValueError(
                    "Native censoring is a report-label interval, not a physical error bound"
                )
            if asset["transform"] != {
                "version": "native_metar_interval.v1",
                "parameters": {"units": "m"},
            }:
                raise ValueError("Native report transform/units not qualified")
            result = asset["content"]
            if result["status"] != asset["missingness"]:
                raise ValueError("Source missingness mismatch")
            interval = Interval(0, math.inf)
            if result["status"] == "inconsistent_same_slot_facts":
                interval = None
            elif (
                result["status"] == "disclosed_product_fact" and len(result.get("reports", [])) == 1
            ):
                report = result["reports"][0]
                native = parse_metar(
                    report["raw"],
                    observation_time=iso(report["observation_time"]),
                    report_type="routine",
                )
                parsed = None if native.visibility is None else native.visibility.to_dict()
                if parsed != report["visibility"] or native.station != report["station"]:
                    raise ValueError("Native value differs from cached interval/station")
                if asset["raw"] != report["raw"]:
                    raise ValueError("Native asset text differs from disclosed report")
                interval = native.visibility if native.visibility is not None else interval
            facts.append(
                EvidenceFact(
                    qid,
                    times.index(asset["available_at"]),
                    asset["completed_at"],
                    "visibility",
                    "m",
                    interval,
                    reference,
                    assumption,
                    scope,
                    asset["support_rule_version"],
                )
            )
            provenance.append(
                {
                    k: asset[k]
                    for k in (
                        "asset_id",
                        "source_revision",
                        "receipt_ids",
                        "parents",
                        "available_at",
                        "completed_at",
                        "reference_kind",
                        "support_assumption",
                        "support_rule_version",
                    )
                }
            )
        support = public_support(facts, "visibility", "m", Interval(0, math.inf), at)
        slots.append(
            {
                "query_id": qid,
                "support": None if support is None else support.to_dict(),
                "status": classify(support, "lt", question["threshold_m"]),
                "provenance": provenance,
            }
        )
    statuses = [s["status"] for s in slots]
    status = (
        "inconsistent"
        if "inconsistent" in statuses
        else "supported"
        if "supported" in statuses
        else "refuted"
        if all(s == "refuted" for s in statuses)
        else "undetermined"
    )
    return {
        "schema": "disastertrace.native_E_support.v1",
        "bundle_hash": bundle.bundle_hash,
        "status": status,
        "slots": slots,
        "at": at,
        "support_scope": "native_report_label_only",
        "future_probability_implied": False,
    }


def subset_bundle(bundle, selected):
    row = bundle.policy_view()
    selected = set(selected)
    row["assets"] = [a for a in row["assets"] if a["content"]["query_id"] in selected]
    receipts = {rid for a in row["assets"] for rid in a["receipt_ids"]}
    row["receipts"] = [r for r in row["receipts"] if r["receipt_id"] in receipts]
    return EvidenceBundle.freeze(row)


def compile_recipes(complete_bundle, *, max_queries=6):
    """Evaluator-only hindsight recipes; never add these to model requests."""
    ids = complete_bundle.policy_view()["baseline"]["content"]["E_question"]["query_ids"]
    if len(ids) > max_queries:
        raise ValueError("Finite recipe graph too large")
    recipes = []
    for size in range(len(ids) + 1):
        for selected in combinations(ids, size):
            recipe = frozenset(selected)
            if any(r <= recipe for r in recipes):
                continue
            if native_slot_support(subset_bundle(complete_bundle, recipe))["status"] in {
                "supported",
                "refuted",
            }:
                recipes.append(recipe)
    return tuple(recipes)


def native_taf_projection(candidate, target):
    product = parse_taf(
        candidate["raw"],
        station=target.entity.removeprefix("station:"),
        archive_issue=iso(candidate["issued_at"]),
    )
    return product, product.project(target.physical_start, target.physical_end)


def taf_coverage(bundle):
    row = bundle.policy_view()
    target = Target(**row["target"])
    candidate = row["baseline"]["content"]["native_taf"]
    result = {
        "schema": "disastertrace.native_taf_coverage_E.v1",
        "bundle_hash": bundle.bundle_hash,
        "model_head_qualified": False,
        "support_scope": "native_TAF_product_conditions",
        "target_contract_hash": target.contract_hash,
        "source_revision": candidate["source_id"],
    }
    try:
        product, projection = native_taf_projection(candidate, target)
        if projection != candidate["projection"]:
            raise ValueError("Reparsed target projection differs from cached product")
        segments = projection["segments"]
        coverage = sum(s["end"] - s["start"] for s in segments)
        if (
            coverage != target.physical_end - target.physical_start
            or segments[0]["start"] != target.physical_start
            or segments[-1]["end"] != target.physical_end
            or any(a["end"] != b["start"] for a, b in pairwise(segments))
        ):
            raise ValueError("Nonunique or incomplete temporal support")
        result.update(
            status="supported",
            coverage_fraction=1.0,
            projection=projection,
            native_operators=[c.operator for c in product.clauses],
            conditional_inheritance="fields inherited by the frozen native parser; not an event probability",
        )
    except (ValueError, KeyError, TypeError) as exc:
        result.update(status="unsupported", error=str(exc), coverage_fraction=None)
    return result


def taf_version_support(disclosed_candidates, target, *, at):
    candidates = [
        c
        for c in disclosed_candidates
        if c["target_id"] == target.target_id and c["available_at"] <= c["completed_at"] <= at
    ]
    if not candidates:
        return {"status": "undetermined", "history": [], "model_head_qualified": False}
    from ..monitoring_v1.providers.versions import latest_issuance

    current, _ = latest_issuance(candidates)
    projections, failures = {}, []
    for c in current:
        try:
            _, projection = native_taf_projection(c, target)
            projections[fingerprint(projection)] = projection
        except (ValueError, KeyError, TypeError) as exc:
            failures.append(str(exc))
    status = "unsupported" if failures else "inconsistent" if len(projections) != 1 else "supported"
    return {
        "schema": "disastertrace.native_taf_versions_E.v1",
        "status": status,
        "target_contract_hash": target.contract_hash,
        "at": at,
        "current_source_ids": sorted({c["source_id"] for c in current}),
        "history": sorted({c["source_id"] for c in candidates}),
        "current_projection": next(iter(projections.values())) if status == "supported" else None,
        "errors": failures,
        "support_rebuilt_from_current_version": True,
        "model_head_qualified": False,
    }
