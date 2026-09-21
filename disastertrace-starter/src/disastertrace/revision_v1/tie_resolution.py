"""Shared tie resolution logic for same-minute TAF issuance ties.

This module provides the authoritative implementation of receipt-order tie
resolution, shared between:
- monitoring_v1/providers/versions.py (runtime resolution)
- scripts/validate_dl3r_semantics.py (offline validation)

V17-02 / F10 fix: Both the runtime resolver and the offline validator must
use the same resolution policy. Previously, the validator checked additional
constraints (receipt premise, BBB order) that the runtime resolver ignored,
allowing the runtime to accept conflicting ties that the validator correctly
rejected.

The resolution has three gates:
1. Receipt premise: all members have int receipt_seq, same receipt_stream,
   and sorting by receipt_seq yields non-decreasing issued_at.
2. BBB order agreement: within same-family BBB codes (AAA/AAB/AAC, etc.),
   the lexicographic BBB order must agree with receipt_seq order.
3. Winner selection: if gates 1 and 2 pass, winner = max receipt_seq.

If any gate fails, the tie is UNRESOLVED - no winner is picked.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any


@dataclass
class TieResolutionResult:
    """Result of a tie resolution attempt.

    Attributes:
        resolved: True if a unique winner was determined.
        winner: The winning row if resolved, else None.
        reason: Explanation of the result.
        rule: The rule used for resolution (only if resolved).
    """
    resolved: bool
    winner: dict | None
    reason: str
    rule: str | None = None


def _get_bbb_family(wmo_bbb: str | None) -> str | None:
    """Extract the 2-letter BBB family prefix (AA, CC, RR, etc.)."""
    if wmo_bbb is None or len(wmo_bbb) < 2:
        return None
    return wmo_bbb[:2]


def check_receipt_premise(members: list[dict]) -> tuple[bool, str]:
    """Check the receipt-order premise for tied group members.

    Premise holds iff:
    - All members have type(x) is int for receipt_seq (bool rejected)
    - All members share the same receipt_stream
    - All receipt_seq values are pairwise distinct (no duplicates)
    - Sorting by receipt_seq yields non-decreasing issued_at (if present)

    Args:
        members: List of product dicts with receipt_seq, receipt_stream, and
            optionally issued_at.

    Returns:
        Tuple of (premise_ok, reason) where:
        - premise_ok: True if premise holds
        - reason: Explanation of the result
    """
    if not members:
        return False, "empty_members"

    # Check all have int receipt_seq (bool subclass rejected)
    seqs = []
    for m in members:
        seq = m.get("receipt_seq")
        if type(seq) is not int:
            return False, "no_receipt_signal"
        seqs.append(seq)

    # Check all receipt_seq values are pairwise distinct (no duplicates)
    if len(seqs) != len(set(seqs)):
        return False, "premise_violated_duplicate_seq"

    # Check all share same receipt_stream
    streams = {m.get("receipt_stream") for m in members}
    if len(streams) != 1 or None in streams:
        return False, "premise_violated_stream_mismatch"

    # Check sorted by receipt_seq yields non-decreasing issued_at (if present)
    # V17-02 / F10: Skip this check if issued_at is not present in members
    # (allows resolve_receipt_tie to work in isolation without full product data)
    if all("issued_at" in m for m in members):
        sorted_by_seq = sorted(members, key=lambda x: x["receipt_seq"])
        for i in range(1, len(sorted_by_seq)):
            if sorted_by_seq[i]["issued_at"] < sorted_by_seq[i - 1]["issued_at"]:
                return False, "premise_violated_issued_at_order"

    return True, "premise_ok"


def check_bbb_order_vs_receipt_order(members: list[dict]) -> tuple[bool, str]:
    """Check if BBB letter order agrees with receipt_seq order within same family.

    Within a BBB family (AA*, CC*, RR*), if we have AAA and AAB, then:
    - AAA < AAB lexicographically (AAA received first per WMO rules)
    - seq(AAA) should < seq(AAB) (receipt order agrees)

    If BBB order contradicts receipt order, we have a conflict that cannot
    be resolved by receipt_seq alone.

    Args:
        members: List of product dicts with wmo_bbb and receipt_seq.

    Returns:
        Tuple of (agrees, reason) where:
        - agrees: True if no contradiction found (agreement or no comparable pairs)
        - reason: Explanation of the result
    """
    # Group by BBB family
    by_family: dict[str, list[dict]] = defaultdict(list)
    for m in members:
        family = _get_bbb_family(m.get("wmo_bbb"))
        if family:
            by_family[family].append(m)

    # For each family with >1 member, check order consistency
    for family, family_members in by_family.items():
        if len(family_members) < 2:
            continue

        # Check all pairs
        for i in range(len(family_members)):
            for j in range(i + 1, len(family_members)):
                bbb_i = family_members[i].get("wmo_bbb", "")
                bbb_j = family_members[j].get("wmo_bbb", "")
                seq_i = family_members[i].get("receipt_seq", 0)
                seq_j = family_members[j].get("receipt_seq", 0)

                # If BBB order says i < j, then seq_i should < seq_j
                # If BBB order says i > j, then seq_i should > seq_j
                bbb_order = (bbb_i < bbb_j)
                seq_order = (seq_i < seq_j)

                if bbb_order != seq_order:
                    return False, "bbb_contradicts_receipt_order"

    return True, "bbb_agrees"


def resolve_receipt_tie_strict(
    tied_rows: list[dict],
) -> TieResolutionResult:
    """Resolve a same-issued_at tie using the strict shared policy.

    This is the V17-02 / F10 fix: the runtime and validator now share
    this single implementation. A tie is only resolved if:
    1. Receipt premise holds (all int seqs, same stream, monotonic issued_at)
    2. BBB order agrees with receipt order (when comparable pairs exist)

    If either check fails, the result is unresolved with an explicit reason.

    Args:
        tied_rows: List of product dicts tied at the same issued_at, with
            receipt_seq, receipt_stream, wmo_bbb, and issued_at fields.

    Returns:
        TieResolutionResult indicating resolution status.
    """
    if not tied_rows:
        return TieResolutionResult(
            resolved=False,
            winner=None,
            reason="empty_input",
        )

    if len(tied_rows) < 2:
        return TieResolutionResult(
            resolved=False,
            winner=None,
            reason="single_member_not_a_tie",
        )

    # Gate 1: Check receipt premise
    premise_ok, premise_reason = check_receipt_premise(tied_rows)
    if not premise_ok:
        return TieResolutionResult(
            resolved=False,
            winner=None,
            reason=premise_reason,
        )

    # Gate 2: Check BBB order agreement
    bbb_ok, bbb_reason = check_bbb_order_vs_receipt_order(tied_rows)
    if not bbb_ok:
        return TieResolutionResult(
            resolved=False,
            winner=None,
            reason=bbb_reason,
        )

    # Gate 3: Winner = max receipt_seq
    winner = max(tied_rows, key=lambda r: r["receipt_seq"])

    # Determine rule based on whether BBB cross-validation occurred
    by_family: dict[str, list[dict]] = defaultdict(list)
    for m in tied_rows:
        family = _get_bbb_family(m.get("wmo_bbb"))
        if family:
            by_family[family].append(m)

    has_same_family_pairs = any(len(fam) >= 2 for fam in by_family.values())
    rule = "receipt_order+bbb_agree" if has_same_family_pairs else "receipt_order"

    return TieResolutionResult(
        resolved=True,
        winner=winner,
        reason="resolved",
        rule=rule,
    )
