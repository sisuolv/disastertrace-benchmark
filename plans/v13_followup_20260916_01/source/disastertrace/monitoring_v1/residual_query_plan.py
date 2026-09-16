"""Finite, metadata-only acquisition interventions at a completed-tick boundary."""

from .targets import canonical_hash

RULES = {"no_further_paid_query", "first", "second", "all"}


def freeze_residual_plan(data, checkpoint, opportunity_id, rule, *, version="disastertrace.residual_query_plan.v1"):
    if version == "disastertrace.residual_query_plan.v2":
        return _freeze_new_plan(data, checkpoint, opportunity_id, rule)
    if version != "disastertrace.residual_query_plan.v1":
        raise ValueError("Unknown residual query plan version")
    from .policies import stable_rank

    p = checkpoint["payload"]
    if canonical_hash(p) != checkpoint["sha256"] or p["data_sha256"] != canonical_hash(data):
        raise ValueError("Query plan parent identity changed")
    if p["schema"] != "disastertrace.session_quiescent.v1" or rule not in RULES:
        raise ValueError("Finite query plan requires a quiescent parent and registered rule")
    if p["config"].get("residual_query_plan") is not None:
        raise ValueError("A finite residual plan cannot be replaced")
    cutoffs = sorted({o["cutoff"] for o in data["opportunities"]})
    if not 0 <= p["next_tick"] < len(cutoffs):
        raise ValueError("No remaining decision")
    opportunity = next((o for o in data["opportunities"] if o["opportunity_id"] == opportunity_id), None)
    if opportunity is None or opportunity["cutoff"] != cutoffs[p["next_tick"]]:
        raise ValueError("Query plan must bind the next registered decision")
    pair = next(r for r in data["e_f_pairs"] if r["opportunity_id"] == opportunity_id)
    wakeup = max(opportunity["cutoff"] - p["config"]["wakeup_seconds"] * 1_000_000, p["clock"])
    payer, scope = opportunity["target_id"], p["config"]["authorization_mode"]
    assets = {r["asset_id"] for r in p["store"]["assets"]}
    requested = {r["receipt_id"] for r in p["ledger"]["events"] if r["event"] == "reserve"}
    catalog = []
    for row in data["query_catalog"]:
        qid = row["query_id"]
        key = qid if scope == "session_shared" else payer + "::" + qid
        catalog.append({
            "catalog": row,
            "related": qid in pair["query_ids"],
            "available": row["available_at"] <= wakeup + 1,
            "already_cached": key in assets,
            "already_requested": "query-" + stable_rank(key) in requested,
        })
    eligible = sorted(
        (r["catalog"]["query_id"] for r in catalog if r["related"] and r["available"]),
        key=lambda qid: (stable_rank(p["config"]["seed"], p["next_tick"], qid), qid),
    )
    order = {"no_further_paid_query": [], "first": eligible[:1], "second": eligible[1:2], "all": eligible}[rule]
    return {
        "schema": "disastertrace.residual_query_plan.v1",
        "parent_checkpoint_sha256": checkpoint["sha256"],
        "activation_tick": p["next_tick"], "checkpoint_clock": p["clock"],
        "public_wakeup": wakeup, "decision_clock": wakeup + 1,
        "opportunity_id": opportunity_id, "payer_target": payer,
        "authorization_scope": scope, "rule": rule,
        "catalog_inventory": catalog, "eligible_query_order": eligible,
        "planned_query_order": order,
        "source_binding": "registered slot and public catalog metadata; returned source versions bind only after acquisition",
        "execution_semantics": "single activation window; fixed sequence; stop on infeasible item; no later paid queries",
        "empty_reason": "no_second_query" if rule == "second" and len(eligible) < 2 else None,
    }


def _freeze_new_plan(data, checkpoint, opportunity_id, rule):
    from .policies import stable_rank

    if rule not in {"none", "first_new", "second_new", "all_new"}:
        raise ValueError("Unknown new-acquisition rule")
    plan = freeze_residual_plan(data, checkpoint, opportunity_id, "all")
    payer = plan["payer_target"]
    assets = {r["asset_id"]: r for r in checkpoint["payload"]["store"]["assets"]}
    events = checkpoint["payload"]["ledger"]["events"]
    for item in plan["catalog_inventory"]:
        qid = item["catalog"]["query_id"]
        key = qid if plan["authorization_scope"] == "session_shared" else payer + "::" + qid
        receipt_id = "query-" + stable_rank(key)
        lifecycle = [r["event"] for r in events if r.get("receipt_id") == receipt_id]
        if key in assets and payer not in assets[key]["entitlement"]:
            raise ValueError("Cached asset lacks registered payer entitlement")
        reasons = []
        if not item["related"]: reasons.append("unrelated_to_registered_target")
        if not item["available"]: reasons.append("not_yet_available")
        if item["already_cached"]: reasons.append("authorized_cache_reusable_without_new_get")
        if item["already_requested"]: reasons.append("already_requested_no_automatic_retry")
        item.update(asset_key=key, receipt_id=receipt_id, receipt_lifecycle=lifecycle,
                    exclusion_reasons=reasons)
    excluded = {r["catalog"]["query_id"] for r in plan["catalog_inventory"] if r["exclusion_reasons"]}
    remaining = [q for q in plan["eligible_query_order"] if q not in excluded]
    order = {"none": [], "first_new": remaining[:1], "second_new": remaining[1:2], "all_new": remaining}[rule]
    plan.update(schema="disastertrace.residual_query_plan.v2", rule=rule,
                remaining_new_query_order=remaining, planned_query_order=order,
                empty_reason="no_second_new_query" if rule == "second_new" and len(remaining) < 2 else
                             "no_remaining_new_query" if rule != "none" and not remaining else None,
                retry_semantics="No original requested identity is resent, including proved-not-sent failures; new registration required",
                none_semantics="No more paid GET; common updates and registered forecasts continue")
    return plan


def validate_residual_plan(data, checkpoint, plan):
    if not isinstance(plan, dict):
        raise ValueError("Invalid residual query plan")
    expected = freeze_residual_plan(data, checkpoint, plan.get("opportunity_id"), plan.get("rule"),
                                    version=plan.get("schema"))
    if plan != expected:
        raise ValueError("Residual query plan differs from its public parent inventory")


def finish_plan_trace(trace, reason):
    done = len(trace["dispositions"])
    for index, qid in enumerate(trace["planned_query_order"][done:]):
        trace["dispositions"].append({"query_id": qid, "status": reason if index == 0 else "unexecuted_tail", "reason": reason})
