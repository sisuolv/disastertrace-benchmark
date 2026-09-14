"""Translate explicit native TAF withdrawals into fixed-target stream events."""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from ..targets import utc_us
from .aviation import day_time


def unavailable_product(raw, *, station, archive_issue, source_id, reason):
    """Preserve a verified native header when a full semantic projection fails."""
    text = " ".join(raw.strip().split())
    match = re.search(r"\b" + re.escape(station) + r"\s+(\d{6})Z\s+(\d{4})/(\d{4})\b", text)
    if match is None:
        raise ValueError("Cannot bind unparsed product to a native station/time/window")
    issued = datetime.fromisoformat(archive_issue.replace("Z", "+00:00"))
    if day_time(match.group(1), issued) != issued:
        raise ValueError("Unparsed native issuance differs from catalog")
    start = day_time(match.group(2), issued)
    end = day_time(match.group(3), start)
    if not start < end <= start + timedelta(hours=36):
        raise ValueError("Unparsed native window is not a valid bounded envelope")
    return {
        "source_id": source_id,
        "station": station,
        "issued_at": utc_us(archive_issue),
        "valid_start": utc_us(start.isoformat()),
        "valid_end": utc_us(end.isoformat()),
        "status": "unparsed",
        "projection_status": "unavailable",
        "reason": reason,
        "raw": text,
        "amendment_kind": "unparsed",
        "clause_operators": [],
    }


def target_withdrawals(
    products,
    targets,
    latest_cutoff,
    *,
    declared_replay_lag_us=120_000_000,
    version_policy="legacy_covering.v1",
):
    if version_policy not in {"legacy_covering.v1", "latest_before_coverage.v2"}:
        raise ValueError("Unknown native version/coverage policy")
    withdrawals = []
    for product in products:
        if product["status"] not in {"active", "nil", "canceled", "unparsed"}:
            raise ValueError("Unknown native TAF timeline status")
        if product["status"] in {"active", "unparsed"} and version_policy == "legacy_covering.v1":
            continue
        available = product["issued_at"] + declared_replay_lag_us
        if available > latest_cutoff:
            continue
        for target in targets:
            covers = (
                product["valid_start"] is None or product["valid_start"] <= target["physical_start"]
            ) and (product["valid_end"] is None or target["physical_end"] <= product["valid_end"])
            if version_policy == "latest_before_coverage.v2":
                if target["entity"] != product["station"] or (
                    product["status"] in {"active", "unparsed"} and covers
                ):
                    continue
                withdrawals.append(
                    {
                        "target_id": target["target_id"],
                        "source_id": product["source_id"],
                        "issued_at": product["issued_at"],
                        "available_at": available,
                        "reason": product["status"]
                        if product["status"] in {"nil", "canceled"}
                        else "current_version_does_not_cover_target",
                        "availability_rule": "native_issued_at_plus_declared_replay_lag",
                    }
                )
                continue
            if (
                target["entity"] == product["station"]
                and (
                    product["valid_start"] is None
                    or product["valid_start"] <= target["physical_start"]
                )
                and (product["valid_end"] is None or target["physical_end"] <= product["valid_end"])
            ):
                withdrawals.append(
                    {
                        "target_id": target["target_id"],
                        "source_id": product["source_id"],
                        "issued_at": product["issued_at"],
                        "available_at": available,
                        "reason": product["status"],
                        "availability_rule": "native_issued_at_plus_declared_replay_lag",
                    }
                )
    return withdrawals
