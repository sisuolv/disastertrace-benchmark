"""Semantic evidence ledger compiler for DisasterTrace v14 (P0-01).

Compiles ledger entries for each evidence package with:
- kind: one of 9 values (new_observation, amendment_supersedes, correction,
        cancellation, lossless_duplicate, mirror, late_superseded,
        no_change_reissue, baseline_update)
- supersedes: reference to the package(s) this one supersedes
- available_at: when this package becomes visible
- availability_basis: verified_publication, declared_lag, or collector_first_seen

Reuses:
- latest_issuance from monitoring_v1/providers/versions.py
- taf_semantics concept (semantic hash comparison)
- amendment_kind field (AMD/COR/original) from TAF products
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from ..monitoring_v1.providers.versions import latest_issuance


# Default declared lag in microseconds (2 minutes, matching current_taf default)
DEFAULT_DECLARED_LAG_US = 120_000_000


def _group_by_station_and_validity(products: list[dict]) -> dict[tuple, list[dict]]:
    """Group products by (station, valid_start, valid_end) for supersession analysis."""
    groups = defaultdict(list)
    for p in products:
        key = (p["station"], p.get("valid_start"), p.get("valid_end"))
        groups[key].append(p)
    return groups


def _is_same_source(source_id_a: str, source_id_b: str) -> bool:
    """Determine if two source IDs come from the same source provider.

    For mirror detection: different source prefixes indicate different providers.
    """
    # Simple heuristic: split on first hyphen and compare prefix
    prefix_a = source_id_a.split("-")[0] if "-" in source_id_a else source_id_a
    prefix_b = source_id_b.split("-")[0] if "-" in source_id_b else source_id_b
    return prefix_a == prefix_b


def _compute_available_at(
    product: dict,
    declared_lag_us: int,
    collector_first_seen: dict[str, int] | None,
) -> tuple[int, str]:
    """Compute available_at and availability_basis for a product.

    Returns (available_at, availability_basis).
    """
    issued_at = product["issued_at"]
    declared_available = issued_at + declared_lag_us

    if collector_first_seen and product["source_id"] in collector_first_seen:
        observed_at = collector_first_seen[product["source_id"]]
        # Use whichever is later - the declared publication or when collector saw it
        if observed_at > declared_available:
            return observed_at, "collector_first_seen"

    return declared_available, "declared_lag"


def _classify_kind(
    product: dict,
    prior_in_group: list[dict],
    all_in_group: list[dict],
    all_semantic_hashes: dict[str, list[dict]],
    collector_first_seen: dict[str, int] | None,
    declared_lag_us: int,
) -> tuple[str, list[str] | None]:
    """Classify a product's kind and determine what it supersedes.

    Returns (kind, supersedes_list).
    """
    source_id = product["source_id"]
    semantic_hash = product["native_semantics_sha256"]
    amendment_kind = product.get("amendment_kind", "original")
    status = product.get("status", "active")
    is_baseline = product.get("is_baseline", False)

    # Check for baseline update
    if is_baseline:
        return "baseline_update", None

    # Check for cancellation
    if status == "canceled":
        # Find what it cancels - the prior active product(s) in this group
        if prior_in_group:
            latest, _ = latest_issuance(prior_in_group)
            supersedes = [p["source_id"] for p in latest]
            return "cancellation", supersedes
        return "cancellation", None

    # Check for semantic duplicates (same hash) - compare with all products with same hash
    same_hash_products = [
        p for p in all_semantic_hashes.get(semantic_hash, [])
        if p["source_id"] != source_id
    ]

    if same_hash_products:
        # Find the first product with this hash (by issued_at, then source_id for tie-break)
        first_with_hash = min(
            same_hash_products,
            key=lambda p: (p["issued_at"], p["source_id"])
        )

        # Check if from different source - if so, it's a mirror regardless of timing
        if not _is_same_source(source_id, first_with_hash["source_id"]):
            return "mirror", None

        # Same source, same semantic content
        # If same issued_at - lossless_duplicate
        if product["issued_at"] == first_with_hash["issued_at"]:
            # Only classify as duplicate if this product is not the canonical first
            if source_id > first_with_hash["source_id"]:
                return "lossless_duplicate", None
        # Different issued_at, same source, same content - no_change_reissue
        elif product["issued_at"] > first_with_hash["issued_at"]:
            return "no_change_reissue", [first_with_hash["source_id"]]

    # Check if this is a late arrival (arrived after it was already superseded)
    # Need to look at ALL products in the group, not just those processed so far
    if collector_first_seen:
        product_available, _ = _compute_available_at(
            product, declared_lag_us, collector_first_seen
        )
        # Find products in the group that:
        # 1. Were issued AFTER this product
        # 2. Became available BEFORE this product arrived
        newer_already_visible = []
        for other in all_in_group:
            if other["source_id"] == source_id:
                continue
            other_available, _ = _compute_available_at(
                other, declared_lag_us, collector_first_seen
            )
            if other["issued_at"] > product["issued_at"] and other_available < product_available:
                newer_already_visible.append(other)

        if newer_already_visible:
            # This product was already superseded when it arrived
            latest_newer, _ = latest_issuance(newer_already_visible)
            supersedes_ids = [p["source_id"] for p in latest_newer]
            return "late_superseded", supersedes_ids

    # Check amendment_kind for AMD/COR
    if amendment_kind == "COR" and prior_in_group:
        latest, _ = latest_issuance(prior_in_group)
        supersedes = [p["source_id"] for p in latest]
        return "correction", supersedes

    if amendment_kind == "AMD" and prior_in_group:
        latest, _ = latest_issuance(prior_in_group)
        supersedes = [p["source_id"] for p in latest]
        return "amendment_supersedes", supersedes

    # Default: new_observation
    return "new_observation", None


def compile_ledger(
    products: list[dict],
    *,
    declared_lag_us: int = DEFAULT_DECLARED_LAG_US,
    collector_first_seen: dict[str, int] | None = None,
) -> list[dict]:
    """Compile a semantic evidence ledger from a list of evidence packages.

    Args:
        products: List of product dicts with fields:
            - source_id: unique identifier
            - station: station code
            - issued_at: issuance time in microseconds
            - valid_start: validity window start in microseconds
            - valid_end: validity window end in microseconds
            - amendment_kind: 'original', 'AMD', or 'COR'
            - status: 'active', 'nil', 'canceled', 'unparsed'
            - native_semantics_sha256: semantic content hash
            - is_baseline: (optional) True if this is a baseline product
        declared_lag_us: Default declared lag for availability (default 2 minutes)
        collector_first_seen: Optional dict mapping source_id to observation time

    Returns:
        List of ledger entries with fields:
            - source_id: from the product
            - kind: one of the 9 kind values
            - supersedes: list of source_ids this supersedes, or None
            - available_at: when this becomes visible (microseconds)
            - availability_basis: 'declared_lag', 'collector_first_seen', or 'verified_publication'
    """
    if not products:
        return []

    # Build index by semantic hash for duplicate/mirror detection
    semantic_hash_index: dict[str, list[dict]] = defaultdict(list)
    for p in products:
        semantic_hash_index[p["native_semantics_sha256"]].append(p)

    # Group by (station, valid_start, valid_end) for supersession analysis
    groups = _group_by_station_and_validity(products)

    # Sort products by issued_at for processing order
    sorted_products = sorted(products, key=lambda p: (p["issued_at"], p["source_id"]))

    # Track which products we've seen so far in each group
    seen_in_group: dict[tuple, list[dict]] = defaultdict(list)

    ledger = []

    for product in sorted_products:
        source_id = product["source_id"]
        group_key = (product["station"], product.get("valid_start"), product.get("valid_end"))

        # Get prior products in this group (issued before this one)
        prior_in_group = [
            p for p in seen_in_group[group_key]
            if p["issued_at"] < product["issued_at"]
        ]

        # Get ALL products in this group (for late_superseded detection)
        all_in_group = groups[group_key]

        # Classify the kind
        kind, supersedes = _classify_kind(
            product,
            prior_in_group,
            all_in_group,
            semantic_hash_index,
            collector_first_seen,
            declared_lag_us,
        )

        # Compute availability
        available_at, availability_basis = _compute_available_at(
            product, declared_lag_us, collector_first_seen
        )

        # Create ledger entry
        entry = {
            "source_id": source_id,
            "kind": kind,
            "supersedes": supersedes,
            "available_at": available_at,
            "availability_basis": availability_basis,
        }
        ledger.append(entry)

        # Add to seen
        seen_in_group[group_key].append(product)

    return ledger


def visible_at(ledger: list[dict], *, cutoff: int) -> list[dict]:
    """Filter ledger to entries visible at a given cutoff time.

    A package is visible if cutoff >= available_at.

    Args:
        ledger: List of ledger entries from compile_ledger
        cutoff: The as-of time in microseconds

    Returns:
        List of ledger entries that are visible at the cutoff time.
    """
    return [entry for entry in ledger if entry["available_at"] <= cutoff]
