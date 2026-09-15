"""Explicit native-provider result policies; archive knowledge is not live release proof."""

POLICIES = {"h15_routine_archive.v1", "dwd_daily_archive.v1"}

PROVIDER_BINDINGS = {
    "h15_routine_archive.v1": ("IEM", "native_h15_snapshot.v1"),
    "dwd_daily_archive.v1": ("DWD", "DWD_TXK_TNK_UTC.v1"),
}


def validate_formal_resolution(record, target):
    policy = record.get("resolution_policy")
    if not isinstance(policy, str) or policy not in PROVIDER_BINDINGS:
        raise ValueError("Formal outcome requires a registered resolution policy")
    if (record.get("provider"), record.get("provider_version")) != PROVIDER_BINDINGS[policy]:
        raise ValueError("Formal outcome provider/version binding mismatch")
    validate_resolution(record, target)
    if record["status"] == "provisional":
        raise ValueError("Formal archive policies do not admit provisional results")
    if record["status"] == "missing" and record["value"] is not None:
        raise ValueError("Missing provider result cannot contain a value")


def validate_resolution(record, target):
    policy = record["resolution_policy"]
    if type(policy) is not str or policy not in POLICIES:
        raise ValueError("Unknown outcome resolution policy")
    h15 = policy == "h15_routine_archive.v1"
    reference = (
        "final_archived_routine_report_not_continuous_physical_truth"
        if h15
        else "native_DWD_daily_product_predicate"
    )
    if (
        target.support_kind != "interval"
        or target.units != ("m" if h15 else "C")
        or target.temporal_semantics != "future_physical"
        or record.get("reference_kind") != reference
    ):
        raise ValueError("Provider resolution policy does not match target/reference scope")
    if h15 and (
        target.variable != "visibility" or target.report_policy != "iem_routine_unique_hour.v1"
    ):
        raise ValueError("H15 policy requires the registered routine report target")
    if record["status"] != "mature":
        return
    quality = "settled_final_archived_report" if h15 else "native_QN_4:9"
    if record["quality_status"] != quality or not record.get("references"):
        raise ValueError("Mature provider result requires qualified quality and native references")
    for name in ("fetched_at", "resolved_at"):
        if record[name] is None:
            raise ValueError("Mature provider result requires " + name)
    observed, published, fetched = (
        record[k] for k in ("observed_at", "published_at", "fetched_at")
    )
    if h15:
        if observed is None or not target.physical_start <= observed < target.physical_end:
            raise ValueError("H15 observation must fall inside its registered report slot")
        earliest = observed
    else:
        # Daily and duration predicates need their complete native support window.
        earliest = target.physical_end
    if fetched < earliest or (published is not None and not earliest <= published <= fetched):
        raise ValueError("Provider result acquisition/publication contradicts physical support")
