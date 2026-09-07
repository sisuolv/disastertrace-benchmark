"""Offline, descriptive audit of the frozen NHC event cohort; no data editing."""

from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

from .common import canonical, fingerprint, read_jsonl, strict_json
from .dynamic import reference_at, render_request, validate_episode

METHOD = {
    "version": "dataset_audit_v1",
    "exact_hash": "sha256(raw_text.encode('utf-8'))",
    "normalized_hash": "sha256(' '.join(raw_text.casefold().split()).encode('utf-8'))",
    "tokenization": "re.findall(r'[a-z0-9]+', raw_text.casefold())",
    "shingle_words": 5,
    "similarity": "set_jaccard_intersection_size_divided_by_union_size",
    "empty_shingle_similarity": None,
    "candidate_threshold": 0.9,
    "candidate_threshold_tuned_on_model_results": False,
    "common_shingle_context": "occurs_in_at_least_3_distinct_parsed_storm_events",
    "common_shingles_removed_from_similarity": False,
    "normalization_changes_source_content": False,
    "near_candidates_change_admission": False,
    "human_review_required": False,
}


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def word_shingles(text: str) -> set[tuple[str, ...]]:
    """Five-word sets retain numbers and never strip weather-specific values."""
    words = re.findall(r"[a-z0-9]+", text.casefold())
    return {tuple(words[index : index + 5]) for index in range(len(words) - 4)}


def shingle_jaccard(left: str, right: str) -> float | None:
    first, second = word_shingles(left), word_shingles(right)
    union = first | second
    return len(first & second) / len(union) if union else None


def _duplicates(rows: list[dict], key: str) -> list[dict]:
    groups = defaultdict(list)
    for row in rows:
        groups[row[key]].append(row)
    return [
        {
            "sha256": digest,
            "source_ids": sorted(row["source_id"] for row in group),
            "storm_ids": sorted({row["storm_id"] for row in group}),
            "splits": sorted({row["split"] for row in group}),
            "cross_split": len({row["split"] for row in group}) > 1,
            "all_used_in_dynamic": all(row["used_in_dynamic"] for row in group),
        }
        for digest, group in sorted(groups.items())
        if len(group) > 1
    ]


def audit_record_similarity(
    records: list[dict], source_splits: dict[str, str], *, used_source_ids: set[str] | None = None
) -> dict:
    """Compare every parsed record, including records from quarantined events."""
    source_ids = [record["source_id"] for record in records]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("duplicate parsed source ID")
    if set(source_ids) - set(source_splits):
        raise ValueError("parsed source lacks a declared split")
    used = set(source_ids) if used_source_ids is None else used_source_ids
    ordered = sorted(records, key=lambda record: record["source_id"])
    rows, shingles, events_per_shingle = [], {}, defaultdict(set)
    for record in ordered:
        source_id = record["source_id"]
        raw = record["raw_text"]
        rows.append(
            {
                "source_id": source_id,
                "storm_id": record["storm_id"],
                "split": source_splits[source_id],
                "used_in_dynamic": source_id in used,
                "raw_sha256": _sha256(raw),
                "normalized_sha256": _sha256(_normalize(raw)),
                "raw_text_chars": len(raw),
            }
        )
        shingles[source_id] = word_shingles(raw)
        for shingle in shingles[source_id]:
            events_per_shingle[shingle].add(record["storm_id"])
    common = {shingle for shingle, events in events_per_shingle.items() if len(events) >= 3}
    candidates = []
    cross_split_pairs = 0
    max_cross_split = None
    pairs_without_shingles = 0
    for left, right in combinations(ordered, 2):
        left_id, right_id = left["source_id"], right["source_id"]
        first, second = shingles[left_id], shingles[right_id]
        shared, union = first & second, first | second
        cross_split = source_splits[left_id] != source_splits[right_id]
        cross_split_pairs += int(cross_split)
        if not union:
            pairs_without_shingles += 1
            continue
        similarity = len(shared) / len(union)
        if cross_split and (max_cross_split is None or similarity > max_cross_split):
            max_cross_split = similarity
        # Exact and normalized matches have separate groups and must not be
        # reclassified as harmless template overlap by this descriptive screen.
        if _normalize(left["raw_text"]) == _normalize(right["raw_text"]):
            continue
        if similarity < METHOD["candidate_threshold"]:
            continue
        different = [
            field
            for field in ("storm_id", "storm_name", "advisory_number", "issued_at")
            if left.get(field) != right.get(field)
        ]
        candidates.append(
            {
                "source_ids": [left_id, right_id],
                "storm_ids": [left["storm_id"], right["storm_id"]],
                "splits": [source_splits[left_id], source_splits[right_id]],
                "cross_split": cross_split,
                "same_storm_event": left["storm_id"] == right["storm_id"],
                "all_used_in_dynamic": left_id in used and right_id in used,
                "jaccard": similarity,
                "intersection_shingles": len(shared),
                "union_shingles": len(union),
                "different_metadata_fields": different,
                "shared_shingles_common_to_at_least_3_events": len(shared & common),
                "common_fraction_of_shared_shingles": len(shared & common) / len(shared),
                "classification": (
                    "high_full_report_overlap_different_metadata"
                    if different
                    else "high_full_report_overlap_same_available_metadata"
                ),
                "interpretation": "candidate_only_not_proof_of_leakage_or_boilerplate_only",
            }
        )
    return {
        "scope": "all_parsed_records_including_orphans_from_quarantined_events",
        "record_count": len(rows),
        "pair_count": len(rows) * (len(rows) - 1) // 2,
        "cross_split_pair_count": cross_split_pairs,
        "pairs_without_any_five_word_shingles": pairs_without_shingles,
        "maximum_cross_split_jaccard": max_cross_split,
        "raw_duplicate_groups": _duplicates(rows, "raw_sha256"),
        "normalized_duplicate_groups": _duplicates(rows, "normalized_sha256"),
        "near_duplicate_candidates": candidates,
        "common_shingle_count": len(common),
        "records": rows,
        "method": dict(METHOD),
    }


def _read(build_path: Path, manifest: dict, relative: str):
    if relative not in manifest["files"]:
        raise ValueError(f"audit input absent from verified manifest: {relative}")
    path = build_path / relative
    return read_jsonl(path) if relative.endswith(".jsonl") else strict_json(path.read_text())


def _year_counts(events: list[dict]) -> dict:
    years = Counter(event["storm_id"][-4:] for event in events)
    return dict(sorted(years.items()))


def _size_summary(rows: list[dict]) -> dict:
    return {
        "checkpoints": len(rows),
        "max_evidence_text_chars": max((row["evidence_text_chars"] for row in rows), default=0),
        "max_public_request_json_chars_without_carrier": max(
            (row["public_request_json_chars_without_carrier"] for row in rows), default=0
        ),
        "max_public_request_json_utf8_bytes_without_carrier": max(
            (row["public_request_json_utf8_bytes_without_carrier"] for row in rows), default=0
        ),
        "max_record_deliveries": max((row["record_deliveries"] for row in rows), default=0),
    }


def audit_dataset(build_path: Path) -> dict:
    """Audit a hash-verified cohort without network calls or model requests.

    Private references are read only to describe the existing action balance.
    Input size measurements use fresh public rendering and a null carrier.
    """
    from .workflow import verify_build

    manifest = verify_build(build_path)
    records = _read(build_path, manifest, "records/nhc_records.jsonl")
    episodes = _read(build_path, manifest, "episodes/dynamic_episodes.jsonl")
    splits = _read(build_path, manifest, "splits/event_groups.json")
    inventory = _read(build_path, manifest, "source_inventory.json")
    admission = _read(build_path, manifest, "profiles/nhc_admission.json")
    assignments = splits["assignments"]
    nhc_inventory = [row for row in inventory if row.get("source") == "NHC"]
    source_assignments = {}
    for event in assignments:
        for source_id in event["source_ids"]:
            if source_id in source_assignments:
                raise ValueError("source ID assigned to more than one event")
            source_assignments[source_id] = event
    by_source = {record["source_id"]: record for record in records}
    if len(by_source) != len(records):
        raise ValueError("duplicate parsed source ID")
    inventory_map = {row["source_id"]: row for row in nhc_inventory}
    if len(inventory_map) != len(nhc_inventory):
        raise ValueError("duplicate NHC inventory source ID")
    ids = [episode["episode_id"] for episode in episodes]
    if not episodes or len(ids) != len(set(ids)):
        raise ValueError("empty or duplicate episode IDs")
    used_source_ids = {record["source_id"] for ep in episodes for record in ep["records"]}
    source_splits = {source_id: event["split"] for source_id, event in source_assignments.items()}
    similarity = audit_record_similarity(records, source_splits, used_source_ids=used_source_ids)
    inventory_rows = [
        {
            "source_id": row["source_id"],
            "storm_id": row["storm_id"],
            "split": row["split"],
            "raw_sha256": row["text_sha256"],
            "used_in_dynamic": row["source_id"] in used_source_ids,
        }
        for row in nhc_inventory
        if row.get("text_sha256")
    ]
    inventory_duplicate_groups = _duplicates(inventory_rows, "raw_sha256")
    checks = {
        "build_manifest_verified": True,
        "source_inventory_matches_catalogue": set(inventory_map) == set(source_assignments),
        "inventory_identity_matches_declared_split": all(
            row["source_id"] in source_assignments
            and row.get("storm_id") == source_assignments[row["source_id"]]["storm_id"]
            and row.get("split") == source_assignments[row["source_id"]]["split"]
            for row in nhc_inventory
        ),
        "parsed_admission_matches_records": (
            {row["source_id"] for row in admission["items"] if row["admitted"]} == set(by_source)
            and len({row["source_id"] for row in admission["items"]}) == len(admission["items"])
            and {row["source_id"] for row in admission["items"]} == set(source_assignments)
        ),
        "parsed_source_provenance_matches_inventory": all(
            source_id in inventory_map
            and _sha256(record["raw_text"])
            == record["provenance"].get("source_sha256")
            == inventory_map[source_id].get("text_sha256")
            and record["provenance"].get("source_url") == inventory_map[source_id].get("source_url")
            and record["storm_id"] == source_assignments[source_id]["storm_id"]
            for source_id, record in by_source.items()
        ),
        "episode_records_match_parsed_inventory": all(
            record == by_source.get(record["source_id"])
            for ep in episodes
            for record in ep["records"]
        ),
        "episodes_match_declared_event_splits": all(
            ep["group_id"] == source_assignments[record["source_id"]]["storm_id"]
            and ep["split"] == source_assignments[record["source_id"]]["split"]
            and ep["episode_id"] in source_assignments[record["source_id"]]["episode_ids"]
            for ep in episodes
            for record in ep["records"]
        ),
        "declared_episode_ids_match_actual": set(ids)
        == {episode_id for event in assignments for episode_id in event["episode_ids"]},
        "admitted_events_have_exactly_two_paired_nonempty_branches": all(
            len([ep for ep in episodes if ep["group_id"] == event["storm_id"]]) == 2
            and {ep.get("branch") for ep in episodes if ep["group_id"] == event["storm_id"]}
            == {"base", "delay"}
            and all(ep["records"] for ep in episodes if ep["group_id"] == event["storm_id"])
            for event in assignments
            if event["status"] == "admitted"
        ),
        "no_exact_cross_split_duplicates": not any(
            row["cross_split"]
            for row in similarity["raw_duplicate_groups"] + inventory_duplicate_groups
        ),
        "no_normalized_cross_split_duplicates": not any(
            row["cross_split"] for row in similarity["normalized_duplicate_groups"]
        ),
    }
    request_sizes, public_templates = [], set()
    for episode in sorted(episodes, key=lambda item: item["episode_id"]):
        validate_episode(episode)
        for checkpoint in episode["checkpoints"]:
            public = render_request(episode, checkpoint["checkpoint_id"], previous=None)
            text = canonical(public)
            public_templates.add(
                fingerprint(
                    {
                        key: public[key]
                        for key in ("protocol", "instruction", "required_fields", "policy")
                    }
                )
            )
            request_sizes.append(
                {
                    "episode_id": episode["episode_id"],
                    "split": episode["split"],
                    "checkpoint_id": checkpoint["checkpoint_id"],
                    "record_deliveries": len(public["evidence"]),
                    "unique_source_records": len({row["record_id"] for row in public["evidence"]}),
                    "evidence_text_chars": sum(len(row["text"]) for row in public["evidence"]),
                    "public_request_json_chars_without_carrier": len(text),
                    "public_request_json_utf8_bytes_without_carrier": len(text.encode("utf-8")),
                }
            )
    gold = _read(build_path, manifest, "private/dynamic_references.jsonl")
    gold_by_id = {(row["episode_id"], row["checkpoint_id"]): row["reference"] for row in gold}
    expected_ids = {
        (ep["episode_id"], cp["checkpoint_id"]) for ep in episodes for cp in ep["checkpoints"]
    }
    checks["private_reference_ids_match_checkpoints"] = (
        len(gold_by_id) == len(gold) and set(gold_by_id) == expected_ids
    )
    checks["private_reference_values_match_frozen_episode_contract"] = all(
        gold_by_id.get((ep["episode_id"], cp["checkpoint_id"]))
        == reference_at(ep, cp["checkpoint_id"])
        for ep in episodes
        for cp in ep["checkpoints"]
    )
    distributions = {}
    for split in sorted({ep["split"] for ep in episodes}):
        actions, by_checkpoint = Counter(), defaultdict(Counter)
        for ep in episodes:
            if ep["split"] != split:
                continue
            for cp in ep["checkpoints"]:
                reference = gold_by_id.get((ep["episode_id"], cp["checkpoint_id"]))
                action = (
                    reference.get("action", "missing_reference")
                    if isinstance(reference, dict)
                    else "missing_reference"
                )
                actions[action] += 1
                by_checkpoint[cp["checkpoint_id"]][action] += 1
        count = sum(actions.values())
        distributions[split] = {
            "checkpoints": count,
            "action_counts": dict(sorted(actions.items())),
            "majority_action_fraction": max(actions.values()) / count,
            "by_checkpoint": {
                key: dict(sorted(value.items())) for key, value in sorted(by_checkpoint.items())
            },
        }
    coverage_by_split = {}
    for split in sorted({event["split"] for event in assignments}):
        planned = [event for event in assignments if event["split"] == split]
        admitted = [event for event in planned if event["status"] == "admitted"]
        coverage_by_split[split] = {
            "planned_events": len(planned),
            "admitted_events": len(admitted),
            "quarantined_events": len(planned) - len(admitted),
            "planned_year_counts": _year_counts(planned),
            "admitted_year_counts": _year_counts(admitted),
            "admitted_storm_names": sorted(event["storm_name"] for event in admitted),
            "parsed_records": sum(source_splits[source_id] == split for source_id in by_source),
            "dynamic_used_records": sum(
                source_splits[source_id] == split for source_id in used_source_ids
            ),
            "episodes": sum(ep["split"] == split for ep in episodes),
            "checkpoints": sum(len(ep["checkpoints"]) for ep in episodes if ep["split"] == split),
        }
    result = {
        "schema_version": "dataset_audit_v1",
        "build_id": manifest["build_id"],
        "method": dict(METHOD),
        "checks": checks,
        "all_required_checks_pass": all(checks.values()),
        "coverage": {
            "scope": "purposeful_atlantic_tropical_cyclone_pilot",
            "unit_of_independence": "storm_event",
            "planned_events": len(assignments),
            "admitted_events": sum(event["status"] == "admitted" for event in assignments),
            "quarantined_events": sum(event["status"] != "admitted" for event in assignments),
            "planned_source_records": len(source_assignments),
            "inventory_source_records": len(nhc_inventory),
            "parsed_source_records": len(records),
            "dynamic_used_records": len(used_source_ids),
            "orphan_parsed_source_ids": sorted(set(by_source) - used_source_ids),
            "source_rejections": [row for row in admission["items"] if not row["admitted"]],
            "quarantined_event_details": [
                event for event in assignments if event["status"] != "admitted"
            ],
            "by_split": coverage_by_split,
        },
        "split_assignments": assignments,
        "source_similarity": similarity,
        "inventory_exact_duplicates": {
            "scope": "acquisition_inventory_text_hashes_including_rejected_sources",
            "records_with_text_hash": len(inventory_rows),
            "duplicate_groups": inventory_duplicate_groups,
            "raw_rejected_text_reopened": False,
        },
        "shared_public_template": {
            "template_hashes": sorted(public_templates),
            "unique_templates": len(public_templates),
            "scope": "protocol_instruction_required_fields_and_policy_only",
            "interpretation": "Shared task wording is expected; it does not make reports identical or splits unseen-template tests.",
        },
        "input_sizes": {
            "units": "unicode_characters_and_utf8_bytes_not_model_tokens",
            "carrier": "null; actual model-authored carrier and provider envelope add size",
            "repeated_deliveries_counted": True,
            "token_estimate": None,
            "overall": _size_summary(request_sizes),
            "by_split": {
                split: _size_summary([row for row in request_sizes if row["split"] == split])
                for split in coverage_by_split
            },
            "per_checkpoint": request_sizes,
        },
        "policy_action_distribution": {
            "origin": "frozen_private_reference_auditor_only_never_added_to_public_requests",
            "policy_kind": "research_rule_not_operational_advice",
            "by_split": distributions,
            "interpretation": "Action imbalance can conceal incorrect source/state updates; retain grounded-state metrics.",
        },
        "limitations": [
            "Near-duplicate candidates are lexical similarity observations, not proof of leakage or harmless boilerplate.",
            "Normalization and near-duplicate comparison cover parsed records; rejected raw text is represented by acquisition hashes only.",
            "Common shingles are context only; no automatic exclusion, relabelling, threshold tuning, or new human annotation is performed.",
            "Pretraining contamination is not measured or ruled out; the archives and heldout content are public.",
            "This small purposeful Atlantic cyclone cohort does not establish representative or cross-hazard extreme-weather coverage.",
            "Base and delay branches share one storm and are dependent; release schedules are controlled, not proven historical availability.",
            "Digest checks establish artifact consistency, not scientific truth, source-server authenticity, or historical availability.",
            "Null-carrier request sizes are not full conversation maxima, model token counts, or context-window compatibility guarantees.",
        ],
        "model_calls": 0,
        "new_human_reviews": 0,
    }
    result["audit_sha256"] = fingerprint(result)
    return result
