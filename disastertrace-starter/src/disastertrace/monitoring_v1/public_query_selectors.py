"""Versioned, label-free query priorities; legacy selectors remain unchanged."""

import hashlib
import math

KINDS = frozenset({"round_robin_cycle.v1", "public_risk_age.v1", "fixed_hash.v1"})


def query_priority(kind, *, seed, tick, acquired, target_id, query_id, common, available_at):
    """Rank a legal option using only the public wakeup view and catalog time.

    Risk is summed over publicly linked active targets. Recency refers to the
    catalog's available_at, not an inferred observation age or forecast value.
    Cyclic priority rotates after each completed acquisition and each wakeup;
    unsuccessful options do not advance it. No additional hidden state exists.
    """
    tie = hashlib.sha256(f"public-query-v1|{seed}|{query_id}".encode()).hexdigest()
    if kind == "fixed_hash.v1":
        return (0, 0, tie)
    if kind == "round_robin_cycle.v1":
        targets = sorted(common, key=lambda t: (common[t]["entity"], t))
        return ((targets.index(target_id) - tick - acquired) % len(targets), 0, tie)
    if kind == "public_risk_age.v1":
        risk = math.fsum(common[t]["baseline_probability"] for t in sorted(common)
                         if query_id in common[t]["public_query_ids"])
        return (-risk, -available_at, tie)
    raise ValueError("Unknown public query selector version")
