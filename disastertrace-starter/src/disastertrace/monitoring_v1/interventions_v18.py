"""Paired controlled interventions for the v18 mechanism pilot."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .evidence_qualification_v18 import EvidenceRecord, qualify_stream


@dataclass(frozen=True)
class InterventionResult:
    intervention: str
    records: list[dict[str, Any]]
    changed_fields: list[str]
    held_fields: list[str]
    qualification: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "disastertrace.v18.intervention_result.v1",
            "intervention": self.intervention,
            "records": self.records,
            "changed_fields": self.changed_fields,
            "held_fields": self.held_fields,
            "qualification": self.qualification,
        }


def apply_intervention(
    records: Iterable[EvidenceRecord | Mapping[str, Any]],
    intervention: str,
    *,
    target_start: int,
    target_end: int,
    as_of: int | None = None,
) -> InterventionResult:
    """Apply one declared intervention without changing the parent in place."""

    parent = [row.to_dict() if isinstance(row, EvidenceRecord) else dict(row) for row in records]
    if not parent:
        raise ValueError("An intervention needs a nonempty parent stream")
    changed: list[str] = []
    held = ["target_start", "target_end", "content", "issued_at"]
    if intervention == "identity_repeat":
        child = deepcopy(parent) + [deepcopy(parent[-1])]
        changed = ["stream_length", "duplicate_arrival"]
        held.remove("content")
    elif intervention == "same_origin_duplicate":
        child = deepcopy(parent)
        duplicate = deepcopy(parent[-1])
        duplicate["source_revision"] = duplicate["source_revision"] + "-mirror"
        duplicate["relation_status"] = "duplicate"
        child.append(duplicate)
        changed = ["stream_length", "source_revision", "relation_status"]
        held.remove("content")
    elif intervention == "matched_sham":
        child = deepcopy(parent) + [deepcopy(parent[-1])]
        child[-1].setdefault("content", {})["length_sham"] = "matched"
        child[-1]["source_revision"] = child[-1]["source_revision"] + "-sham"
        child[-1]["relation_status"] = "duplicate"
        changed = ["stream_length", "content.length_sham", "source_revision"]
    elif intervention == "withhold":
        child = deepcopy(parent[:-1])
        changed = ["stream_length", "last_arrival_withheld"]
    elif intervention == "delay":
        child = deepcopy(parent)
        child[-1]["available_at"] = (child[-1].get("available_at") or 0) + 86_400_000_000
        changed = ["available_at"]
    elif intervention == "repair":
        child = deepcopy(parent)
        if len(child) < 2:
            raise ValueError("Repair needs a parent and a later record")
        child[0]["content"] = deepcopy(child[1]["content"])
        changed = ["parent.content"]
    else:
        raise ValueError(f"Unknown intervention: {intervention}")
    qualification = qualify_stream(
        child, target_start=target_start, target_end=target_end, as_of=as_of
    )
    return InterventionResult(intervention, child, changed, held, [row.to_dict() for row in qualification])
