"""Four-layer evidence census for the v18 development port."""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Mapping


def evidence_census(episodes: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = list(episodes)
    episode_ids = [str(row.get("episode_id", "")) for row in rows]
    if not rows or any(not value for value in episode_ids):
        raise ValueError("Census requires nonempty episode identities")
    if len(set(episode_ids)) != len(episode_ids):
        raise ValueError("Duplicate episode identity")
    status = Counter()
    availability = Counter()
    source_change = 0
    content_change = 0
    unknown_content = 0
    evidence_rows = 0
    episode_rows = []
    for episode in rows:
        checkpoints = episode.get("checkpoints")
        if isinstance(checkpoints, list) and checkpoints:
            # The v3 (T-60/T-40/T-20) roster shape: the same evidence stream is
            # re-qualified once per checkpoint, with visibility only growing
            # (see build_v18_dev_episodes.py's monotonic-visibility guarantee).
            # Counting every checkpoint's list would count each row up to 3
            # times; the last checkpoint is the most complete legitimate view
            # and is used alone, matching the pre-v3 single-pass semantics.
            last_checkpoint = checkpoints[-1]
            qualifications = (
                last_checkpoint.get("qualifications") if isinstance(last_checkpoint, Mapping) else None
            )
        else:
            # Pre-v3 (flat) episode shape, preserved for backward compatibility.
            qualifications = episode.get("qualifications")
        if not isinstance(qualifications, list) or not qualifications:
            raise ValueError("Every episode needs qualification rows")
        local = Counter()
        for qualification in qualifications:
            evidence_rows += 1
            name = str(qualification.get("status", "UNKNOWN"))
            status[name] += 1
            local[name] += 1
            availability[str(qualification.get("availability", "unknown"))] += 1
            source_change_value = qualification.get("source_change")
            if source_change_value is True:
                source_change += 1
            content_value = qualification.get("target_content_change")
            if content_value is True:
                content_change += 1
            elif content_value is None:
                unknown_content += 1
        episode_rows.append({"episode_id": episode["episode_id"], "status_counts": dict(sorted(local.items()))})
    return {
        "schema": "disastertrace.v18.evidence_census.v1",
        "episode_denominator": len(rows),
        "evidence_row_denominator": evidence_rows,
        "source_change_rows": source_change,
        "target_content_change_rows": content_change,
        "unknown_target_content_rows": unknown_content,
        "status_counts": dict(sorted(status.items())),
        "availability_counts": dict(sorted(availability.items())),
        "episode_rows": episode_rows,
        "claim_boundary": "Source counts and target-content counts are separate; no risk or outcome claim is implied.",
    }
