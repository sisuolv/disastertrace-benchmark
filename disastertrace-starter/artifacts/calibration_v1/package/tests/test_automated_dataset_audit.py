"""Frozen lexical checks are observations, not human adjudication or LLM results."""

import shutil
from copy import deepcopy
from pathlib import Path

import pytest

from disastertrace.automated.common import (
    file_hash,
    fingerprint,
    read_jsonl,
    write_json,
    write_jsonl,
)
from disastertrace.automated.dataset_audit import (
    METHOD,
    audit_dataset,
    audit_record_similarity,
    shingle_jaccard,
    word_shingles,
)

BUILD = Path(__file__).resolve().parents[1] / "work/build-cohort-v1"


def record(source_id, raw_text, storm_id="AL012040"):
    return {
        "source_id": source_id,
        "storm_id": storm_id,
        "storm_name": "SYNTHETIC",
        "advisory_number": "9",
        "issued_at": "2040-08-01T06:00:00Z",
        "raw_text": raw_text,
    }


def compare(left, right, **kwargs):
    return audit_record_similarity(
        [left, right], {left["source_id"]: "development", right["source_id"]: "heldout"}, **kwargs
    )


def test_word_five_shingles_are_sets_and_retain_digits():
    assert word_shingles("Storm, wind 105 MPH; pressure 970 MB.") == {
        ("storm", "wind", "105", "mph", "pressure"),
        ("wind", "105", "mph", "pressure", "970"),
        ("105", "mph", "pressure", "970", "mb"),
    }
    assert shingle_jaccard("a b c d e f", "a b c d e g") == pytest.approx(1 / 3)
    assert shingle_jaccard("one two three", "one two three four") is None


def test_exact_cross_split_duplicates_have_hash_groups_not_near_candidates():
    text = "Synthetic storm report with maximum wind of 105 mph"
    result = compare(record("a", text), record("b", text, "AL022040"))
    assert result["raw_duplicate_groups"][0]["source_ids"] == ["a", "b"]
    assert result["raw_duplicate_groups"][0]["cross_split"] is True
    assert result["normalized_duplicate_groups"][0]["cross_split"] is True
    assert result["near_duplicate_candidates"] == []


def test_case_and_whitespace_duplicates_do_not_require_byte_equality():
    result = compare(
        record("a", "Wind 105 MPH\n pressure 970 MB"),
        record("b", " wind\t105 mph PRESSURE 970 mb ", "AL022040"),
    )
    assert result["raw_duplicate_groups"] == []
    assert len(result["normalized_duplicate_groups"]) == 1
    assert result["normalized_duplicate_groups"][0]["cross_split"] is True


def test_single_word_change_to_long_report_is_only_near_duplicate_candidate():
    text = " ".join(f"token{n}" for n in range(500))
    result = compare(
        record("a", text), record("b", text.replace("token250", "replacement"), "AL022040")
    )
    assert result["raw_duplicate_groups"] == result["normalized_duplicate_groups"] == []
    candidate = result["near_duplicate_candidates"][0]
    assert 0.9 <= candidate["jaccard"] < 1
    assert candidate["different_metadata_fields"] == ["storm_id"]
    assert candidate["classification"] == "high_full_report_overlap_different_metadata"
    assert candidate["interpretation"] == "candidate_only_not_proof_of_leakage_or_boilerplate_only"
    assert METHOD["near_candidates_change_admission"] is False


def test_same_template_with_distinct_facts_does_not_imply_identical_report():
    shared = "Synthetic weather bulletin summary observations warning information next report"
    left = record("a", shared + " " + " ".join(f"alpha{n}" for n in range(100)))
    right = record("b", shared + " " + " ".join(f"beta{n}" for n in range(100)), "AL022040")
    result = compare(left, right)
    assert 0 < result["maximum_cross_split_jaccard"] < 0.9
    assert result["near_duplicate_candidates"] == []
    assert result["normalized_duplicate_groups"] == []


def test_common_template_context_is_counted_across_events_without_removing_words():
    text = " ".join(f"token{n}" for n in range(300))
    records = [record(str(n), text + f" ending{n}", f"AL0{n}2040") for n in (1, 2, 3)]
    result = audit_record_similarity(records, {"1": "development", "2": "heldout", "3": "heldout"})
    assert result["common_shingle_count"] == 296
    assert len(result["near_duplicate_candidates"]) == 3
    for pair in result["near_duplicate_candidates"]:
        assert pair["jaccard"] == pytest.approx(296 / 298)
        assert pair["common_fraction_of_shared_shingles"] == 1
        assert pair["classification"] == "high_full_report_overlap_different_metadata"
    assert result["method"]["common_shingles_removed_from_similarity"] is False


def test_orphan_records_remain_in_similarity_scope():
    text = "Synthetic storm report with maximum wind of 105 mph"
    result = compare(record("a", text), record("b", text, "AL022040"), used_source_ids={"a"})
    assert result["record_count"] == 2
    assert result["raw_duplicate_groups"][0]["all_used_in_dynamic"] is False


def test_duplicate_ids_and_undeclared_splits_are_rejected():
    with pytest.raises(ValueError, match="duplicate parsed source ID"):
        audit_record_similarity([record("a", "x"), record("a", "y")], {"a": "heldout"})
    with pytest.raises(ValueError, match="declared split"):
        audit_record_similarity([record("a", "x")], {})


def test_similarity_result_deterministic_under_input_order_and_does_not_mutate():
    records = [record("z", "a b c d e f"), record("a", "a b c d e g", "AL022040")]
    before = deepcopy(records)
    splits = {"z": "development", "a": "heldout"}
    assert audit_record_similarity(records, splits) == audit_record_similarity(
        list(reversed(records)), splits
    )
    assert records == before


@pytest.fixture(scope="module")
def actual_audit():
    return audit_dataset(BUILD)


def test_cached_cohort_audit_keeps_all_source_and_event_denominators(actual_audit):
    coverage = actual_audit["coverage"]
    assert (
        coverage["planned_events"],
        coverage["admitted_events"],
        coverage["quarantined_events"],
    ) == (12, 10, 2)
    assert (
        coverage["planned_source_records"],
        coverage["parsed_source_records"],
        coverage["dynamic_used_records"],
    ) == (36, 32, 30)
    assert coverage["orphan_parsed_source_ids"] == [
        "nhc-al092017-public-009",
        "nhc-al092017-public-010",
    ]
    assert len(coverage["source_rejections"]) == 4
    assert coverage["by_split"]["development"]["admitted_events"] == 3
    assert coverage["by_split"]["heldout"]["admitted_events"] == 7
    assert actual_audit["source_similarity"]["pair_count"] == 496
    assert actual_audit["source_similarity"]["cross_split_pair_count"] == 231
    assert actual_audit["inventory_exact_duplicates"]["records_with_text_hash"] == 36
    assert actual_audit["all_required_checks_pass"] is True
    assert actual_audit["shared_public_template"]["unique_templates"] == 1


def test_cached_request_sizes_count_repeated_deliveries_but_never_gold_carrier(actual_audit):
    sizes = actual_audit["input_sizes"]
    assert sizes["overall"]["checkpoints"] == 100
    assert sizes["overall"]["max_record_deliveries"] == 4
    assert sizes["token_estimate"] is None
    row = next(
        row
        for row in sizes["per_checkpoint"]
        if row["episode_id"] == "al092021:controlled:base" and row["checkpoint_id"] == "c4"
    )
    assert row["record_deliveries"] == 4
    assert row["unique_source_records"] == 3
    c0 = [row for row in sizes["per_checkpoint"] if row["checkpoint_id"] == "c0"]
    assert all(row["evidence_text_chars"] == 0 for row in c0)
    assert all(row["public_request_json_chars_without_carrier"] > 0 for row in c0)


def test_cached_policy_balance_and_limitations_are_explicit(actual_audit):
    by_split = actual_audit["policy_action_distribution"]["by_split"]
    assert by_split["development"]["action_counts"] == {
        "monitor": 19,
        "prepare": 5,
        "request_evidence": 6,
    }
    assert by_split["heldout"]["action_counts"] == {
        "monitor": 32,
        "prepare": 24,
        "request_evidence": 14,
    }
    assert any("Pretraining contamination" in item for item in actual_audit["limitations"])
    assert any("cross-hazard" in item for item in actual_audit["limitations"])
    assert actual_audit["model_calls"] == actual_audit["new_human_reviews"] == 0


def test_audit_digest_and_second_execution_agree(actual_audit):
    assert actual_audit["audit_sha256"] == fingerprint(
        {key: value for key, value in actual_audit.items() if key != "audit_sha256"}
    )
    assert audit_dataset(BUILD) == actual_audit


def _resign(path):
    manifest_path = path / "manifest.json"
    from disastertrace.automated.common import strict_json

    manifest = strict_json(manifest_path.read_text())
    manifest["files"] = {relative: file_hash(path / relative) for relative in manifest["files"]}
    manifest["build_id"] = fingerprint(
        {key: value for key, value in manifest.items() if key != "build_id"}
    )
    write_json(manifest_path, manifest)


def test_build_tampering_is_rejected_before_audit(tmp_path):
    path = tmp_path / "build"
    shutil.copytree(BUILD, path)
    with (path / "records/nhc_records.jsonl").open("a") as stream:
        stream.write("\n")
    with pytest.raises(ValueError, match="artifact changed"):
        audit_dataset(path)


def test_consistently_resigned_bad_source_provenance_fails_required_check(tmp_path):
    path = tmp_path / "build"
    shutil.copytree(BUILD, path)
    records = read_jsonl(path / "records/nhc_records.jsonl")
    records[0]["provenance"]["source_sha256"] = "0" * 64
    write_jsonl(path / "records/nhc_records.jsonl", records)
    _resign(path)
    result = audit_dataset(path)
    assert result["checks"]["parsed_source_provenance_matches_inventory"] is False
    assert result["checks"]["episode_records_match_parsed_inventory"] is False
    assert result["all_required_checks_pass"] is False


def test_resigned_cross_split_copy_fails_exact_and_normalized_checks(tmp_path):
    path = tmp_path / "build"
    shutil.copytree(BUILD, path)
    records = read_jsonl(path / "records/nhc_records.jsonl")
    ida = next(row for row in records if row["source_id"] == "nhc-al092021-public-009")
    irma = next(row for row in records if row["source_id"] == "nhc-al112017-public-009")
    irma["raw_text"] = ida["raw_text"]
    write_jsonl(path / "records/nhc_records.jsonl", records)
    _resign(path)
    result = audit_dataset(path)
    assert result["checks"]["no_exact_cross_split_duplicates"] is False
    assert result["checks"]["no_normalized_cross_split_duplicates"] is False
    assert result["all_required_checks_pass"] is False


def test_resigned_inventory_split_mismatch_fails_identity_check(tmp_path):
    path = tmp_path / "build"
    shutil.copytree(BUILD, path)
    from disastertrace.automated.common import strict_json

    inventory = strict_json((path / "source_inventory.json").read_text())
    next(row for row in inventory if row.get("source") == "NHC")["split"] = "wrong"
    write_json(path / "source_inventory.json", inventory)
    _resign(path)
    result = audit_dataset(path)
    assert result["checks"]["inventory_identity_matches_declared_split"] is False
    assert result["all_required_checks_pass"] is False


def test_audit_does_not_pass_private_reference_to_request_renderer(monkeypatch):
    from disastertrace.automated import dataset_audit

    original = dataset_audit.render_request
    carriers = []

    def render(episode, checkpoint_id, previous):
        carriers.append(previous)
        request = original(episode, checkpoint_id, previous)
        assert "reference" not in request and "records" not in request
        assert all("fields" not in row for row in request["evidence"])
        return request

    monkeypatch.setattr(dataset_audit, "render_request", render)
    audit_dataset(BUILD)
    assert carriers == [None] * 100
