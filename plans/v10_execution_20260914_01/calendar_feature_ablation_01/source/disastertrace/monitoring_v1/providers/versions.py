"""Native issuance selection within one explicitly designated product series."""

from dataclasses import asdict

from ..targets import canonical_hash


def latest_issuance(products):
    products = list(products)
    if any(type(row.get("issued_at")) is not int for row in products):
        raise ValueError("Native version ordering requires integer issuance times")
    latest = max((row["issued_at"] for row in products), default=None)
    return (
        [row for row in products if row["issued_at"] == latest],
        [row for row in products if row["issued_at"] != latest],
    )


def taf_semantics(product):
    """Bind the complete parsed product, excluding transport formatting."""
    row = asdict(product)
    row.pop("raw")
    for clause in row["clauses"]:
        clause.pop("raw")
    return canonical_hash(row)


def current_taf(products, *, station, cutoff, start, end, lag_us=120_000_000):
    """Select a disclosed issuance in one station's TAF series before projection."""
    visible = [p for p in products if p["station"] == station and p["issued_at"] + lag_us <= cutoff]
    current, _ = latest_issuance(visible)
    if not current:
        return {"status": "no_product", "source_ids": []}
    source_ids = sorted(p["source_id"] for p in current)
    if len({p["native_semantics_sha256"] for p in current}) != 1:
        return {"status": "conflict", "source_ids": source_ids}
    # Choosing a stable alias is lawful only after semantic equivalence is proved.
    selected = min(current, key=lambda p: p["source_id"])
    status = selected["status"]
    if status in {"active", "unparsed"} and not (
        selected["valid_start"] <= start < end <= selected["valid_end"]
    ):
        status = "current_version_does_not_cover_target"
    return {
        "status": status,
        "source_ids": source_ids,
        "selected_id": selected["source_id"],
        "issued_at": selected["issued_at"],
    }
