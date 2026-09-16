"""Predeclared storm-group admission and descriptive event-level aggregation."""

from __future__ import annotations

import copy
import hashlib
from collections import Counter, defaultdict

from .common import fingerprint
from .dynamic import aware, build_episodes, score_dynamic

SPLITS = ("development", "heldout")


def _catalogue_events(catalogue: dict) -> list[dict]:
    if catalogue.get("schema_version") != "nhc_cohort_catalogue_v1":
        raise ValueError("unsupported cohort catalogue schema")
    if not isinstance(catalogue.get("cohort_id"), str) or not catalogue["cohort_id"]:
        raise ValueError("catalogue requires a cohort ID")
    events = catalogue.get("events")
    if not isinstance(events, list) or not events:
        raise ValueError("catalogue requires nonempty events")
    if (
        type(catalogue.get("planned_event_count")) is not int
        or catalogue["planned_event_count"] != len(events)
        or catalogue.get("advisories_per_event") != 3
    ):
        raise ValueError("catalogue declared counts disagree with its protocol")
    storm_ids, source_ids = set(), set()
    for event in events:
        if not isinstance(event, dict):
            raise ValueError("catalogue event must be an object")
        for key in ("storm_id", "storm_name"):
            if not isinstance(event.get(key), str) or not event[key]:
                raise ValueError(f"catalogue event requires {key}")
        if event["storm_id"] in storm_ids:
            raise ValueError("duplicate catalogue storm ID")
        storm_ids.add(event["storm_id"])
        if event.get("split") not in SPLITS:
            raise ValueError("catalogue split must be development or heldout")
        numbers = event.get("advisory_numbers")
        if (
            not isinstance(numbers, list)
            or len(numbers) != 3
            or any(not isinstance(n, str) or not n.isdecimal() for n in numbers)
        ):
            raise ValueError("catalogue requires three numeric advisory numbers")
        values = [int(n) for n in numbers]
        if values[0] < 1 or values != list(range(values[0], values[0] + 3)):
            raise ValueError("catalogue advisories must be positive and consecutive")
        ids = event.get("source_ids")
        if (
            not isinstance(ids, list)
            or len(ids) != 3
            or any(not isinstance(value, str) or not value for value in ids)
        ):
            raise ValueError("catalogue requires three source IDs")
        if len(set(ids)) != 3 or source_ids.intersection(ids):
            raise ValueError("duplicate catalogue source ID")
        source_ids.update(ids)
    return events


def build_cohort(records: list[dict], catalogue: dict) -> dict:
    """Admit complete fixed triples without replacing or relabelling failed events.

    Structural ambiguity in the input inventory is a fatal error. Event-specific
    source defects are quarantined, preserving every planned split assignment.
    """
    events = _catalogue_events(catalogue)
    expected = {
        source_id: (event, str(int(number)))
        for event in events
        for source_id, number in zip(event["source_ids"], event["advisory_numbers"])
    }
    if not isinstance(records, list):
        raise ValueError("records must be a list")
    by_source, record_ids = {}, set()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("record must be an object")
        source_id, record_id = record.get("source_id"), record.get("record_id")
        if not isinstance(source_id, str) or not isinstance(record_id, str) or not record_id:
            raise ValueError("record requires explicit source and record IDs")
        if source_id not in expected:
            raise ValueError(f"unplanned source ID: {source_id}")
        if source_id in by_source or record_id in record_ids:
            raise ValueError("duplicate source or record ID in input inventory")
        by_source[source_id] = record
        record_ids.add(record_id)

    reasons = {event["storm_id"]: [] for event in events}

    def reject(event: dict, code: str, detail: str, source_id: str | None = None) -> None:
        row = {"code": code, "detail": detail}
        if source_id is not None:
            row["source_id"] = source_id
        reasons[event["storm_id"]].append(row)

    hashes = defaultdict(list)
    for source_id, record in by_source.items():
        event, number = expected[source_id]
        if (
            record.get("record_id") != source_id
            or record.get("storm_id") != event["storm_id"]
            or not isinstance(record.get("storm_name"), str)
            or record["storm_name"].casefold() != event["storm_name"].casefold()
            or record.get("advisory_number") != number
        ):
            reject(
                event,
                "PLANNED_IDENTITY_MISMATCH",
                "Record identity differs from its frozen catalogue entry",
                source_id,
            )
        raw_text = record.get("raw_text")
        provenance = record.get("provenance")
        if not isinstance(raw_text, str) or not isinstance(provenance, dict):
            reject(
                event,
                "SOURCE_PROVENANCE_MISSING",
                "Raw source text and explicit provenance are required",
                source_id,
            )
            continue
        digest = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        if provenance.get("source_sha256") != digest:
            reject(
                event,
                "SOURCE_HASH_MISMATCH",
                "Source hash does not match unchanged UTF-8 text",
                source_id,
            )
        hashes[digest].append((event, source_id))
        if provenance.get("source_origin") not in {"official_record", "synthetic_record"}:
            reject(
                event,
                "SOURCE_ORIGIN_UNSUPPORTED",
                "An explicit official or synthetic record origin is required",
                source_id,
            )
    for duplicates in hashes.values():
        if len({event["split"] for event, _ in duplicates}) > 1:
            ids = sorted(source_id for _, source_id in duplicates)
            for event, source_id in duplicates:
                reject(
                    event,
                    "CROSS_SPLIT_SOURCE_DUPLICATE",
                    f"Identical source text appears across splits: {ids}",
                    source_id,
                )

    episodes, outcomes = [], []
    catalogue_hash = fingerprint(catalogue)
    for event in events:
        selected = [
            by_source[source_id] for source_id in event["source_ids"] if source_id in by_source
        ]
        for source_id in event["source_ids"]:
            if source_id not in by_source:
                reject(
                    event,
                    "PLANNED_SOURCE_MISSING",
                    "Planned advisory was not supplied as an admitted parsed record",
                    source_id,
                )
        if len(selected) == 3:
            try:
                times = [aware(record["issued_at"]) for record in selected]
                if any(later <= earlier for earlier, later in zip(times, times[1:])):
                    reject(
                        event,
                        "NONINCREASING_ADVISORY_TIME",
                        "Issue times must increase in frozen advisory-number order",
                    )
                if len({time.year for time in times}) != 1:
                    reject(
                        event,
                        "MIXED_YEAR_SCOPE",
                        "The selected triple must remain in one calendar year",
                    )
            except (KeyError, TypeError, ValueError) as exc:
                reject(event, "ISSUE_TIME_INVALID", str(exc))
        event_episodes = []
        if not reasons[event["storm_id"]]:
            try:
                event_episodes = build_episodes(copy.deepcopy(selected))
            except (KeyError, TypeError, ValueError) as exc:
                reject(event, "EPISODE_CONTRACT_REJECTED", str(exc))
        for episode, branch in zip(event_episodes, ("base", "delay")):
            episode.update(
                split=event["split"],
                cohort_id=catalogue["cohort_id"],
                catalogue_sha256=catalogue_hash,
                branch=branch,
            )
        episodes.extend(event_episodes)
        outcomes.append(
            {
                "storm_id": event["storm_id"],
                "storm_name": event["storm_name"],
                "split": event["split"],
                "status": "admitted" if event_episodes else "quarantined",
                "source_ids": list(event["source_ids"]),
                "provided_source_ids": [row["source_id"] for row in selected],
                "episode_ids": [row["episode_id"] for row in event_episodes],
                "rejection_reasons": reasons[event["storm_id"]],
            }
        )
    splits = {}
    for split in SPLITS:
        planned = [row for row in outcomes if row["split"] == split]
        admitted = [row for row in planned if row["status"] == "admitted"]
        splits[split] = {
            "planned_event_ids": [row["storm_id"] for row in planned],
            "admitted_event_ids": [row["storm_id"] for row in admitted],
            "quarantined_event_ids": [
                row["storm_id"] for row in planned if row["status"] != "admitted"
            ],
            "episode_ids": [episode for row in admitted for episode in row["episode_ids"]],
            "planned_event_count": len(planned),
            "admitted_event_count": len(admitted),
        }
    admitted_count = sum(row["status"] == "admitted" for row in outcomes)
    return {
        "episodes": episodes,
        "profile": {
            "schema_version": "nhc_cohort_profile_v1",
            "cohort_id": catalogue["cohort_id"],
            "catalogue_sha256": catalogue_hash,
            "candidate_event_count": len(events),
            "admitted_event_count": admitted_count,
            "quarantined_event_count": len(events) - admitted_count,
            "planned_record_count": 3 * len(events),
            "provided_record_count": len(records),
            "admitted_record_count": 3 * admitted_count,
            "episode_count": len(episodes),
            "checkpoint_count": sum(len(ep["checkpoints"]) for ep in episodes),
            "event_outcomes": outcomes,
            "rejection_counts": dict(
                Counter(reason["code"] for rows in reasons.values() for reason in rows)
            ),
            "selection_basis": catalogue.get("selection_basis"),
            "new_human_reviews": 0,
            "model_result_based_filtering": False,
            "historical_availability_proven": False,
        },
        "split_manifest": {
            "schema_version": "nhc_cohort_splits_v1",
            "cohort_id": catalogue["cohort_id"],
            "catalogue_sha256": catalogue_hash,
            "grouping_unit": "storm_event",
            "assignment_origin": "predeclared_catalogue",
            "splits": splits,
            "assignments": copy.deepcopy(outcomes),
            "cross_split_source_duplicates": 0,
            "source_duplicate_check_scope": "admitted_events_only_after_quarantine",
            "pretraining_contamination_checked": False,
        },
    }


def _descriptive_summary(rows: list[dict], pooled: dict) -> dict:
    macro, paired = {}, {}
    for name in pooled["metrics"]:
        values = [row["metrics"][name]["value"] for row in rows]
        defined = [value for value in values if value is not None]
        macro[name] = {
            "value": sum(defined) / len(defined) if defined else None,
            "n_events_defined": len(defined),
            "n_events_total": len(rows),
            "numerator_sum": sum(row["metrics"][name]["numerator"] for row in rows),
            "denominator_sum": sum(row["metrics"][name]["denominator"] for row in rows),
        }
        deltas = [row["paired_branches"]["delay_minus_base"][name] for row in rows]
        defined_deltas = [value for value in deltas if value is not None]
        paired[name] = {
            "value": sum(defined_deltas) / len(defined_deltas) if defined_deltas else None,
            "n_paired_events_defined": len(defined_deltas),
            "n_paired_events_total": len(rows),
        }
    return {
        "n_events": len(rows),
        "n_episodes": sum(row["n_episodes"] for row in rows),
        "n_checkpoints": sum(row["n_checkpoints"] for row in rows),
        "event_macro": macro,
        "pooled_metrics": pooled["metrics"],
        "status_counts": pooled["status_counts"],
        "paired_delay_minus_base": paired,
    }


def summarize_events(
    episodes: list[dict], traces: list[dict], *, expected_split: str | None = None
) -> dict:
    """Score a selected universe before grouping; never silently drop extra traces."""
    if expected_split is not None and expected_split not in SPLITS:
        raise ValueError("expected split must be development or heldout")
    pooled = score_dynamic(episodes, traces)
    grouped = defaultdict(list)
    for episode in episodes:
        if episode.get("split") not in SPLITS:
            raise ValueError("cohort episode requires a frozen development or heldout split")
        if expected_split is not None and episode["split"] != expected_split:
            raise ValueError("episode lies outside the selected split")
        grouped[episode["group_id"]].append(episode)
    rows = []
    for group_id, event_episodes in grouped.items():
        if len({ep["split"] for ep in event_episodes}) != 1:
            raise ValueError("one storm event appears in multiple splits")
        if len(event_episodes) != 2 or {ep.get("branch") for ep in event_episodes} != {
            "base",
            "delay",
        }:
            raise ValueError("event summary requires exactly the paired base and delay branches")
        ids = {episode["episode_id"] for episode in event_episodes}
        event_traces = [row for row in traces if row["episode_id"] in ids]
        event_score = score_dynamic(event_episodes, event_traces)
        branches = {}
        for episode in event_episodes:
            branch_score = score_dynamic(
                [episode],
                [row for row in event_traces if row["episode_id"] == episode["episode_id"]],
            )
            branches[episode["branch"]] = {
                "episode_id": episode["episode_id"],
                "metrics": branch_score["metrics"],
                "status_counts": branch_score["status_counts"],
            }
        branches["delay_minus_base"] = {
            name: (
                branches["delay"]["metrics"][name]["value"]
                - branches["base"]["metrics"][name]["value"]
                if all(
                    branches[branch]["metrics"][name]["value"] is not None
                    for branch in ("base", "delay")
                )
                else None
            )
            for name in event_score["metrics"]
        }
        rows.append(
            {
                "group_id": group_id,
                "split": event_episodes[0]["split"],
                "episode_ids": sorted(ids),
                "n_episodes": len(event_episodes),
                "n_checkpoints": sum(len(ep["checkpoints"]) for ep in event_episodes),
                "metrics": event_score["metrics"],
                "paired_branches": branches,
            }
        )
    by_split = {}
    for split in SPLITS:
        selected_rows = [row for row in rows if row["split"] == split]
        if not selected_rows:
            continue
        selected_episodes = [ep for ep in episodes if ep["split"] == split]
        ids = {ep["episode_id"] for ep in selected_episodes}
        selected_traces = [row for row in traces if row["episode_id"] in ids]
        by_split[split] = _descriptive_summary(
            selected_rows, score_dynamic(selected_episodes, selected_traces)
        )
    summary = _descriptive_summary(rows, pooled)
    return {
        "schema_version": "nhc_cohort_score_v1",
        "unit_of_independence": "storm_event",
        "n_events": len(rows),
        "n_episodes": len(episodes),
        "n_checkpoints": summary["n_checkpoints"],
        "selected_splits": sorted(by_split),
        "overall": summary,
        "per_event": rows,
        "by_split": by_split,
        "confidence_intervals": None,
        "statistical_interpretation": "descriptive_purposeful_pilot_not_population_estimation",
        "conditional_metric_note": "Change and preservation eligibility depend on actual prior responses; undefined event rates are excluded and counted explicitly.",
        "paired_interpretation": "Base and delay are dependent branches of the same storm, not additional independent events.",
        "eligible_for_llm_leaderboard": False,
    }
