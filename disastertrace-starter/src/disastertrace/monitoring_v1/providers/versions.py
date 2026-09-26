"""Native issuance selection within one explicitly designated product series."""

from dataclasses import asdict
from typing import TYPE_CHECKING

from ..targets import canonical_hash
from ...revision_v1.tie_resolution import (
    resolve_receipt_tie_strict,
    TieResolutionResult,
)

if TYPE_CHECKING:
    from typing import Any


def resolve_receipt_tie(tied_rows, *, strict: bool = True):
    """Return the unique latest-received row; signal absence or ambiguity returns None.

    V17-02 / F10 fix: Now uses the shared resolve_receipt_tie_strict() which
    checks both the receipt premise AND BBB order agreement before picking a
    winner. This aligns runtime behavior with the offline validator.

    When strict=True (default), uses the full validation including BBB order
    checks. When strict=False, uses legacy behavior (receipt_seq only).

    Resolvable iff (strict mode):
    - Every row has type(row.get("receipt_seq")) is int (bool subclass rejected)
    - All rows share the same receipt_stream
    - Sorting by receipt_seq yields non-decreasing issued_at
    - BBB letter order agrees with receipt_seq order (when comparable pairs exist)

    receipt_seq is not a runtime arrival timestamp but rather the **position within
    the sha256-sealed AFOS archive byte stream** (.body file row index), assigned
    during data-receipt verification. This field is produced by episode_compiler's
    compile_afos_taf_stream and explicitly opted-in by data sources - monitoring_v1
    layers never produce it, so this tie-break does not conflict with admission.py's
    "no authority from arrival order" principle.

    Args:
        tied_rows: List of product dicts tied at the same issued_at.
        strict: If True (default), use full validation including BBB checks.
                If False, use legacy behavior (receipt_seq only, no BBB check).

    Returns:
        The winning row if resolved, else None.
    """
    if not tied_rows or len(tied_rows) < 2:
        return None

    if strict:
        # V17-02 / F10 fix: Use shared strict resolution
        result = resolve_receipt_tie_strict(tied_rows)
        return result.winner if result.resolved else None

    # Legacy fallback (strict=False): original behavior without BBB check
    # Strict int check (bool is subclass of int, must be rejected)
    for row in tied_rows:
        seq = row.get("receipt_seq")
        if type(seq) is not int:
            return None

    # All rows must share the same receipt_stream
    streams = {row.get("receipt_stream") for row in tied_rows}
    if len(streams) != 1 or None in streams:
        return None

    # All receipt_seq values must be pairwise distinct
    seqs = [row["receipt_seq"] for row in tied_rows]
    if len(seqs) != len(set(seqs)):
        return None

    # Winner = max receipt_seq (latest received)
    return max(tied_rows, key=lambda r: r["receipt_seq"])


def resolve_receipt_tie_with_status(tied_rows) -> TieResolutionResult:
    """Return full resolution status including reason for unresolved ties.

    V17-02 / F10 fix: This variant returns a TieResolutionResult with explicit
    reason for unresolved status, allowing callers (like the ledger) to
    propagate "unresolved" as a distinct state rather than silently coercing
    it into a winner.

    Args:
        tied_rows: List of product dicts tied at the same issued_at.

    Returns:
        TieResolutionResult with resolved status, winner (if any), and reason.
    """
    if not tied_rows or len(tied_rows) < 2:
        return TieResolutionResult(
            resolved=False,
            winner=None,
            reason="not_a_tie" if tied_rows else "empty_input",
        )

    return resolve_receipt_tie_strict(tied_rows)


def latest_issuance(products):
    """Select the latest issuance(s) from a product list.

    Returns (latest_rows, rest_rows) where the partition invariant holds:
    every input row appears in exactly one of the two returned lists.

    When the max-issued_at set has more than one row (a tie), attempts
    receipt-order tie-break via resolve_receipt_tie. If successful, returns
    a singleton latest list and moves the tie losers into rest. If not
    resolvable, returns all tied rows in latest (legacy behavior).
    """
    products = list(products)
    if any(type(row.get("issued_at")) is not int for row in products):
        raise ValueError("Native version ordering requires integer issuance times")
    latest = max((row["issued_at"] for row in products), default=None)
    latest_rows = [row for row in products if row["issued_at"] == latest]
    rest_rows = [row for row in products if row["issued_at"] != latest]

    # Attempt tie-break if multiple latest
    if len(latest_rows) > 1:
        winner = resolve_receipt_tie(latest_rows)
        if winner is not None:
            # Winner becomes sole latest; losers join rest
            losers = [r for r in latest_rows if r is not winner]
            return ([winner], rest_rows + losers)

    return (latest_rows, rest_rows)


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
