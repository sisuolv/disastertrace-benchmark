"""Semantic evidence ledger compiler for DisasterTrace v14 (P0-01).

Compiles ledger entries for each evidence package with:
- kind: one of 9 values (new_observation, amendment_supersedes, correction,
        cancellation, lossless_duplicate, mirror, late_superseded,
        no_change_reissue, baseline_update) - these are now DERIVED from
        underlying dimensions for backward compatibility
- supersedes: reference to the package(s) this one supersedes
- superseded_by: reference to the package(s) this one is superseded BY
        (new field for late-arriving old versions)
- available_at: when this package becomes visible
- availability_basis: verified_publication, declared_lag, or collector_first_seen

Enhanced provenance fields (Issue #4):
- provider: extracted provider identity (replaces string prefix parsing)
- product_series: product lineage identifier
- origin_identity: unique origin identity tuple

Relationship dimensions (Issue #6):
- arrival_relationship: 'on_time', 'late', 'early'
- version_relationship: 'first', 'supersedes', 'superseded_by', 'concurrent'
- information_utility: 'informative', 'duplicate', 'confirmation', 'extension'

The old 9-kind field is retained and correctly derived from the new dimensions.

Reuses:
- latest_issuance from monitoring_v1/providers/versions.py
- taf_semantics concept (semantic hash comparison)
- amendment_kind field (AMD/COR/original) from TAF products
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from ..monitoring_v1.providers.versions import latest_issuance


# Default declared lag in microseconds (2 minutes, matching current_taf default)
DEFAULT_DECLARED_LAG_US = 120_000_000


@dataclass
class Provenance:
    """Explicit provenance identity for duplicate/mirror detection (Issue #4).

    Replaces string prefix parsing of source_id with structured identity.
    """
    provider: str
    product_series: str
    origin_identity: tuple

    @classmethod
    def from_source_id(cls, source_id: str, product: dict) -> "Provenance":
        """Extract provenance from product, falling back to source_id parsing."""
        # Check for explicit provenance fields first
        if "provider" in product:
            return cls(
                provider=product["provider"],
                product_series=product.get("product_series", "default"),
                origin_identity=tuple(product.get("origin_identity", (source_id,))),
            )

        # Fallback: parse source_id prefix for backward compatibility
        if "-" in source_id:
            prefix = source_id.split("-")[0]
        else:
            prefix = source_id

        return cls(
            provider=prefix,
            product_series=product.get("product_series", "default"),
            origin_identity=(source_id,),
        )


@dataclass(frozen=True)
class ProductLineage:
    """Track product lineage for cross-window version replacement (Issue #2).

    Products are in the same lineage if they share:
    - Same station
    - Same provider/product_series
    - Overlapping or adjacent validity windows (not just exact match)

    V17-02 / F01: Made frozen=True so it can be used as a dictionary key
    for lineage-based grouping.
    """
    station: str
    provider: str
    product_series: str

    @classmethod
    def from_product(cls, product: dict, provenance: Provenance) -> "ProductLineage":
        return cls(
            station=product["station"],
            provider=provenance.provider,
            product_series=provenance.product_series,
        )


def _group_by_station_and_validity(products: list[dict]) -> dict[tuple, list[dict]]:
    """Group products by (station, valid_start, valid_end) for supersession analysis."""
    groups = defaultdict(list)
    for p in products:
        key = (p["station"], p.get("valid_start"), p.get("valid_end"))
        groups[key].append(p)
    return groups


def _group_by_lineage(products: list[dict]) -> dict[ProductLineage, list[dict]]:
    """Group products by lineage for cross-window supersession (Issue #2)."""
    groups = defaultdict(list)
    for p in products:
        provenance = Provenance.from_source_id(p["source_id"], p)
        lineage = ProductLineage.from_product(p, provenance)
        groups[lineage].append(p)
    return groups


def _is_same_source(source_id_a: str, source_id_b: str,
                    product_a: dict = None, product_b: dict = None) -> bool:
    """Determine if two products come from the same source provider (Issue #4).

    Uses explicit provenance fields if available, falls back to string prefix.
    """
    if product_a is not None and product_b is not None:
        prov_a = Provenance.from_source_id(source_id_a, product_a)
        prov_b = Provenance.from_source_id(source_id_b, product_b)
        return prov_a.provider == prov_b.provider

    # Legacy fallback: split on first hyphen and compare prefix
    prefix_a = source_id_a.split("-")[0] if "-" in source_id_a else source_id_a
    prefix_b = source_id_b.split("-")[0] if "-" in source_id_b else source_id_b
    return prefix_a == prefix_b


def _compute_available_at(
    product: dict,
    declared_lag_us: int,
    collector_first_seen: dict[str, int] | None,
) -> tuple[int, str]:
    """Compute available_at and availability_basis for a product (Issue #5).

    Now properly handles verified_publication as a real input branch.

    Returns (available_at, availability_basis).
    """
    issued_at = product["issued_at"]
    declared_available = issued_at + declared_lag_us

    # Issue #5: Check for verified_publication first (highest priority)
    if "verified_publication" in product and product["verified_publication"] is not None:
        verified_at = product["verified_publication"]
        # Verified publication is authoritative
        if collector_first_seen and product["source_id"] in collector_first_seen:
            observed_at = collector_first_seen[product["source_id"]]
            # Use whichever is later between verified and observed
            if observed_at > verified_at:
                return observed_at, "collector_first_seen"
        return verified_at, "verified_publication"

    # Check collector_first_seen
    if collector_first_seen and product["source_id"] in collector_first_seen:
        observed_at = collector_first_seen[product["source_id"]]
        # Use whichever is later - the declared publication or when collector saw it
        if observed_at > declared_available:
            return observed_at, "collector_first_seen"

    return declared_available, "declared_lag"


def _compute_information_utility(
    product: dict,
    prior_in_group: list[dict],
    same_hash_products: list[dict],
    kind: str,
) -> str:
    """Compute information utility for no_change_reissue (Issue #7).

    A reissue is not automatically zero-information - it can carry:
    - Validity period extension
    - New confirmation
    - Changed reliability signal
    """
    if kind != "no_change_reissue":
        return "informative"

    # Check for validity extension - compare with same_hash_products (not just group)
    # since extended validity means different group
    if same_hash_products:
        max_prior_valid_end = max(
            (p.get("valid_end", 0) for p in same_hash_products),
            default=0
        )
        if product.get("valid_end", 0) > max_prior_valid_end:
            return "extension"

    # Also check prior_in_group for validity extension
    if prior_in_group:
        latest_prior = max(prior_in_group, key=lambda p: p["issued_at"])
        if product.get("valid_end", 0) > latest_prior.get("valid_end", 0):
            return "extension"

    # Check for confirmation count increase
    if "confirmation_count" in product:
        prior_counts = [p.get("confirmation_count", 0) for p in same_hash_products]
        if prior_counts and product["confirmation_count"] > max(prior_counts):
            return "confirmation"

    # Check for reliability signal change
    if "reliability_score" in product:
        prior_scores = [p.get("reliability_score") for p in same_hash_products if "reliability_score" in p]
        if prior_scores and product["reliability_score"] != prior_scores[-1]:
            return "informative"

    return "duplicate"


def _classify_kind_prefix_aware(
    product: dict,
    all_products: list[dict],
    view_cutoff: int,
    declared_lag_us: int,
    collector_first_seen: dict[str, int] | None,
) -> tuple[str, list[str] | None, list[str] | None, dict]:
    """Classify a product's kind with prefix-aware semantic hash comparison (Issue #1).

    This version ensures classification depends ONLY on records with
    available_at <= view_cutoff, preventing future-mirror leakage.

    Returns (kind, supersedes_list, superseded_by_list, extra_fields).
    """
    source_id = product["source_id"]
    semantic_hash = product["native_semantics_sha256"]
    amendment_kind = product.get("amendment_kind", "original")
    status = product.get("status", "active")
    is_baseline = product.get("is_baseline", False)

    product_available_at, _ = _compute_available_at(product, declared_lag_us, collector_first_seen)

    extra_fields = {
        "arrival_relationship": "on_time",
        "version_relationship": "first",
        "information_utility": "informative",
    }

    # Build prefix-aware indices: only include products available before view_cutoff
    # AND only those that would be relevant for this product's classification
    visible_products = []
    for p in all_products:
        if p["source_id"] == source_id:
            continue
        p_available, _ = _compute_available_at(p, declared_lag_us, collector_first_seen)
        # Issue #1: Only consider products that are visible at the time
        # we're classifying this product (i.e., available before product's available_at
        # OR available before view_cutoff, whichever is relevant)
        #
        # D4 (RO2): Equal available_at tie-breaking via receipt_seq.
        # Among records tied at the exact same available_at, a record p stays
        # INVISIBLE to product's classification only when p was received STRICTLY
        # LATER than product (comparable via matching receipt_stream + int seqs).
        # This breaks the cyclic-supersedes bug: two-member tie A(seq=5)/B(seq=10)
        # => A's visible set excludes B (B.seq > A.seq), B's visible set includes A
        # => only B can supersede A, never the reverse.
        if p_available < product_available_at:
            visible_products.append(p)
        elif p_available == product_available_at:
            # Equal-time visibility: include p UNLESS p was received strictly later
            # than product (both have comparable receipt ordering signals).
            p_seq = p.get("receipt_seq")
            product_seq = product.get("receipt_seq")
            p_stream = p.get("receipt_stream")
            product_stream = product.get("receipt_stream")

            # Comparability requires: both seqs are int (not bool, not None),
            # both streams match and are not None, and seqs differ.
            if (
                type(p_seq) is int
                and type(product_seq) is int
                and p_stream is not None
                and p_stream == product_stream
                and p_seq > product_seq
            ):
                # p received strictly later than product => p invisible to product
                pass
            else:
                # Fallback: legacy behavior (include p)
                visible_products.append(p)

    # Build semantic hash index from visible products only
    semantic_hash_index = defaultdict(list)
    for p in visible_products:
        semantic_hash_index[p["native_semantics_sha256"]].append(p)

    # V17-02 / F01 fix: Use lineage-based grouping instead of exact window match.
    # Group visible products by ProductLineage (station + provider + product_series)
    # for cross-window supersession detection.
    product_provenance = Provenance.from_source_id(source_id, product)
    product_lineage = ProductLineage.from_product(product, product_provenance)

    # Build lineage index from visible products
    lineage_groups: dict[ProductLineage, list[dict]] = defaultdict(list)
    for p in visible_products:
        p_provenance = Provenance.from_source_id(p["source_id"], p)
        p_lineage = ProductLineage.from_product(p, p_provenance)
        lineage_groups[p_lineage].append(p)

    # Find predecessors in the same lineage with overlapping/adjacent validity windows
    # This replaces the exact-window-match lookup
    prior_in_lineage = []
    for p in lineage_groups.get(product_lineage, []):
        if _validity_windows_overlap_or_adjacent(product, p):
            prior_in_lineage.append(p)

    # Also build exact-window group for backward compatibility with some paths
    station_validity_groups = defaultdict(list)
    for p in visible_products:
        key = (p["station"], p.get("valid_start"), p.get("valid_end"))
        station_validity_groups[key].append(p)

    group_key = (product["station"], product.get("valid_start"), product.get("valid_end"))
    prior_in_exact_window = station_validity_groups.get(group_key, [])

    # V17-02 / F01: Use lineage-based prior for AMD/COR supersession
    # Filter to only same-provider products within the lineage
    prior_in_group = prior_in_lineage

    # Check for baseline update (Issue #6: don't let this override AMD/COR/CNL)
    if is_baseline:
        # Only classify as baseline_update if there's no explicit AMD/COR/CNL
        if amendment_kind == "original" and status == "active":
            return "baseline_update", None, None, extra_fields

    # Check for cancellation
    if status == "canceled":
        if prior_in_group:
            latest, _ = latest_issuance(prior_in_group)
            supersedes = [p["source_id"] for p in latest]
            extra_fields["version_relationship"] = "supersedes"
            return "cancellation", supersedes, None, extra_fields
        return "cancellation", None, None, extra_fields

    # Check for semantic duplicates using prefix-aware index
    same_hash_products = semantic_hash_index.get(semantic_hash, [])

    if same_hash_products:
        # Find the first product with this hash (by issued_at, then source_id)
        first_with_hash = min(
            same_hash_products,
            key=lambda p: (p["issued_at"], p["source_id"])
        )

        # Issue #4: Use proper provenance comparison
        if not _is_same_source(source_id, first_with_hash["source_id"], product, first_with_hash):
            extra_fields["version_relationship"] = "concurrent"
            extra_fields["information_utility"] = "duplicate"
            return "mirror", None, None, extra_fields

        # Same source, same semantic content
        if product["issued_at"] == first_with_hash["issued_at"]:
            # Only classify as duplicate if this product is not the canonical first
            if source_id > first_with_hash["source_id"]:
                extra_fields["version_relationship"] = "concurrent"
                extra_fields["information_utility"] = "duplicate"
                return "lossless_duplicate", None, None, extra_fields
        elif product["issued_at"] > first_with_hash["issued_at"]:
            # Issue #7: Compute actual information utility for reissue
            utility = _compute_information_utility(product, prior_in_group, same_hash_products, "no_change_reissue")
            extra_fields["information_utility"] = utility
            extra_fields["version_relationship"] = "supersedes"
            return "no_change_reissue", [first_with_hash["source_id"]], None, extra_fields

    # Check if this is a late arrival (Issue #3: fix supersedes direction)
    # V17-02 / F01: Also check same provider/lineage for late-arrival detection
    if collector_first_seen:
        # Find products in the same lineage that were issued AFTER but became available BEFORE
        newer_already_visible = []
        for other in visible_products:
            if other["station"] != product["station"]:
                continue
            # V17-02 / F01: Check same provider/lineage (not just same station)
            other_provenance = Provenance.from_source_id(other["source_id"], other)
            other_lineage = ProductLineage.from_product(other, other_provenance)
            if other_lineage != product_lineage:
                continue
            # Same lineage check (relaxed from exact validity match per Issue #2)
            if not _validity_windows_overlap_or_adjacent(product, other):
                continue

            other_available, _ = _compute_available_at(other, declared_lag_us, collector_first_seen)
            # Newer by issuance but arrived earlier
            if other["issued_at"] > product["issued_at"] and other_available < product_available_at:
                newer_already_visible.append(other)

        if newer_already_visible:
            # Issue #3: This product is SUPERSEDED BY newer ones, not the reverse
            latest_newer, _ = latest_issuance(newer_already_visible)
            superseded_by_ids = [p["source_id"] for p in latest_newer]
            extra_fields["arrival_relationship"] = "late"
            extra_fields["version_relationship"] = "superseded_by"
            # Return superseded_by, NOT supersedes (fix for Issue #3)
            return "late_superseded", None, superseded_by_ids, extra_fields

    # Check amendment_kind for AMD/COR (Issue #6: these now take precedence over baseline)
    if amendment_kind == "COR" and prior_in_group:
        latest, _ = latest_issuance(prior_in_group)
        supersedes = [p["source_id"] for p in latest]
        extra_fields["version_relationship"] = "supersedes"
        return "correction", supersedes, None, extra_fields

    if amendment_kind == "AMD" and prior_in_group:
        latest, _ = latest_issuance(prior_in_group)
        supersedes = [p["source_id"] for p in latest]
        extra_fields["version_relationship"] = "supersedes"
        return "amendment_supersedes", supersedes, None, extra_fields

    # Check for baseline_update with AMD/COR override
    if is_baseline and amendment_kind in ("AMD", "COR"):
        # Baseline updates with amendments should reflect the amendment
        if prior_in_group:
            latest, _ = latest_issuance(prior_in_group)
            supersedes = [p["source_id"] for p in latest]
            extra_fields["version_relationship"] = "supersedes"
            if amendment_kind == "COR":
                return "correction", supersedes, None, extra_fields
            else:
                return "amendment_supersedes", supersedes, None, extra_fields

    # Default: new_observation
    return "new_observation", None, None, extra_fields


def _validity_windows_overlap_or_adjacent(product_a: dict, product_b: dict) -> bool:
    """Check if two products have overlapping or adjacent validity windows (Issue #2)."""
    a_start = product_a.get("valid_start", 0)
    a_end = product_a.get("valid_end", 0)
    b_start = product_b.get("valid_start", 0)
    b_end = product_b.get("valid_end", 0)

    # Overlapping: one starts before the other ends
    if a_start <= b_end and b_start <= a_end:
        return True

    # Adjacent: one ends exactly when the other starts
    if a_end == b_start or b_end == a_start:
        return True

    return False


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
            - verified_publication: (optional) verified publication time
            - provider: (optional) explicit provider identity
            - product_series: (optional) product lineage identifier
        declared_lag_us: Default declared lag for availability (default 2 minutes)
        collector_first_seen: Optional dict mapping source_id to observation time

    Returns:
        List of ledger entries with fields:
            - source_id: from the product
            - kind: one of the 9 kind values (derived from dimensions)
            - supersedes: list of source_ids this supersedes, or None
            - superseded_by: list of source_ids this is superseded BY, or None (new)
            - available_at: when this becomes visible (microseconds)
            - availability_basis: 'declared_lag', 'collector_first_seen', or 'verified_publication'
            - arrival_relationship: 'on_time', 'late', 'early' (new dimension)
            - version_relationship: 'first', 'supersedes', 'superseded_by', 'concurrent' (new)
            - information_utility: 'informative', 'duplicate', 'confirmation', 'extension' (new)
    """
    if not products:
        return []

    # Sort products by issued_at for processing order
    sorted_products = sorted(products, key=lambda p: (p["issued_at"], p["source_id"]))

    ledger = []

    for product in sorted_products:
        source_id = product["source_id"]

        # Compute availability
        available_at, availability_basis = _compute_available_at(
            product, declared_lag_us, collector_first_seen
        )

        # Classify with prefix-awareness (Issue #1 fix)
        kind, supersedes, superseded_by, extra_fields = _classify_kind_prefix_aware(
            product,
            products,  # Full products list - function does prefix filtering internally
            available_at,  # Use product's own availability as view cutoff
            declared_lag_us,
            collector_first_seen,
        )

        # Create ledger entry with all fields
        entry = {
            "source_id": source_id,
            "kind": kind,
            "supersedes": supersedes,
            "superseded_by": superseded_by,  # New field for Issue #3
            "available_at": available_at,
            "availability_basis": availability_basis,
            # New dimension fields (Issue #6)
            "arrival_relationship": extra_fields.get("arrival_relationship", "on_time"),
            "version_relationship": extra_fields.get("version_relationship", "first"),
            "information_utility": extra_fields.get("information_utility", "informative"),
        }
        ledger.append(entry)

    return ledger


def visible_at(ledger: list[dict], *, cutoff: int) -> list[dict]:
    """Filter ledger to entries visible at a given cutoff time.

    A package is visible if cutoff >= available_at.

    IMPORTANT (Issue #1): This function now returns entries with classifications
    that are stable with respect to the view prefix. Adding future entries to
    the archive will NOT change the classification of entries already visible.

    Args:
        ledger: List of ledger entries from compile_ledger
        cutoff: The as-of time in microseconds

    Returns:
        List of ledger entries that are visible at the cutoff time.
    """
    return [entry for entry in ledger if entry["available_at"] <= cutoff]


def compile_ledger_at_view(
    products: list[dict],
    *,
    view_cutoff: int,
    declared_lag_us: int = DEFAULT_DECLARED_LAG_US,
    collector_first_seen: dict[str, int] | None = None,
) -> list[dict]:
    """Compile a ledger with classifications stable for a specific view time.

    This is the strict prefix-aware variant that guarantees no future records
    can affect the classification of visible records. The returned ledger will
    contain ONLY records visible at view_cutoff, with classifications computed
    using ONLY the information that would have been available at view_cutoff.

    This implements the 验收原则 (acceptance principle) from the review:
    "The online view must be insensitive to ANY future suffix."

    Args:
        products: List of product dicts
        view_cutoff: The time at which to compute the view
        declared_lag_us: Default declared lag for availability
        collector_first_seen: Optional dict mapping source_id to observation time

    Returns:
        List of ledger entries visible at view_cutoff, with stable classifications.
    """
    if not products:
        return []

    # First filter to only products that would be visible at view_cutoff
    visible_products = []
    for p in products:
        available_at, _ = _compute_available_at(p, declared_lag_us, collector_first_seen)
        if available_at <= view_cutoff:
            visible_products.append(p)

    # Now compile the ledger using ONLY the visible products
    # This ensures future products cannot affect classification
    return compile_ledger(
        visible_products,
        declared_lag_us=declared_lag_us,
        collector_first_seen=collector_first_seen,
    )
