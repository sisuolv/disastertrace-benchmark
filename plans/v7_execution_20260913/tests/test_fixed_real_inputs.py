"""Cross-condition bindings and actual-data isolation checks before interpretation."""

import json
from collections import defaultdict
from pathlib import Path

import pytest
from disastertrace.monitoring_fixed_v1.aviation import (
    AviationProvider,
    FrozenFrequencyPredictor,
    model_messages,
    parse_response,
    visible_e_status,
)
from disastertrace.monitoring_fixed_v1.contracts import EvidenceBundle, fingerprint

MATRIX = Path(__file__).resolve().parents[1] / "evidence_bundle/matrix_01"


def bundles():
    return [
        EvidenceBundle.restore(json.loads(p.read_text()))
        for p in sorted((MATRIX / "policy").glob("*.json"))
    ]


def test_real_matrix_same_target_baseline_state_and_raw_prefixes():
    groups = defaultdict(list)
    for bundle in bundles():
        row = bundle.policy_view()
        groups[row["opportunity_id"]].append(bundle)
    assert len(groups) == 48
    for group in groups.values():
        assert len(group) == 3 and len({b.base_hash for b in group}) == 1
        records = [b.policy_view() for b in group]
        assert len({fingerprint(r["state"]) for r in records}) == 1
        assert len({fingerprint(r["target"]) for r in records}) == 1
        records.sort(key=lambda r: len(r["assets"]))
        assert [len(r["assets"]) for r in records] == [0, 1, 2]
        assert records[1]["assets"][0] == records[2]["assets"][0]


def test_no_hidden_result_keys_in_visible_inputs_and_all_assets_timely():
    def check(node):
        if isinstance(node, dict):
            assert not set(node) & {
                "outcome",
                "gold",
                "gold_mask",
                "evaluator_only",
                "expected_e",
            }
            for value in node.values():
                check(value)
        elif isinstance(node, list):
            for value in node:
                check(value)

    for bundle in bundles():
        row = bundle.policy_view()
        check(row)
        assert row["availability_basis"] == "declared_archive_scenario"
        assert all(a["completed_at"] <= row["cutoff"] for a in row["assets"])
        first = model_messages(bundle)
        first[1]["content"] = "mutated copy"
        assert model_messages(bundle)[1]["content"] != first[1]["content"]


def test_program_does_not_read_future_results_and_common_case_is_follow():
    bank = json.loads((MATRIX / "BANK.json").read_text())
    predictor = FrozenFrequencyPredictor(bank)
    for bundle in bundles():
        result = predictor.predict(bundle)
        row = bundle.policy_view()
        if not row["assets"]:
            assert result.to_dict() == row["baseline"]["forecast"]
            assert visible_e_status(bundle) == "undetermined"


def test_unparsed_native_baseline_retains_fallback_identity():
    row = bundles()[0].policy_view()
    content = row["baseline"]["content"]
    target = content["legacy_target_contract"]
    opportunity_id = row["opportunity_id"]
    provider = AviationProvider.__new__(AviationProvider)
    provider.bank = json.loads((MATRIX / "BANK.json").read_text())
    provider.targets = {target["target_id"]: target}
    provider.opportunities = {
        opportunity_id: {"target_id": target["target_id"], "cutoff": row["cutoff"]}
    }
    provider.pairs = {
        opportunity_id: {
            "query_ids": content["E_question"]["query_ids"],
            "e_predicate": content["E_question"]["predicate"],
            "threshold_m": target["threshold"],
        }
    }
    provider.bases = {
        opportunity_id: {**content["native_taf"], "projection_status": "unavailable"}
    }
    frozen = provider.freeze(opportunity_id, "common_only")
    assert frozen.policy_view()["baseline"]["kind"] == "fallback"


@pytest.mark.parametrize(
    "raw",
    [
        '{"probability":true,"e_status":"supported"}',
        '{"probability":0.2,"e_status":"yes"}',
        '{"probability":0.2,"e_status":"supported","answer":1}',
    ],
)
def test_invalid_direct_outputs_are_not_accepted(raw):
    with pytest.raises(ValueError):
        parse_response(raw, bundles()[0])


@pytest.mark.parametrize(
    "truth,status",
    [
        ("true", "supported"),
        ("false", "refuted"),
        ("unknown", "undetermined"),
        ("conflict", "inconsistent"),
    ],
)
def test_explicit_truth_output_maps_to_support_without_filled_defaults(truth, status):
    bundle = bundles()[0]
    forecast, support = parse_response(
        json.dumps({"probability": 0.2, "fact_truth": truth}), bundle
    )
    assert forecast.value == 0.2 and support == status
    system = model_messages(bundle)[0]["content"]
    assert '"probability":0.1' not in system and '"probability":0.7' not in system


def test_json_boolean_does_not_silently_coerce_to_truth_enum():
    with pytest.raises(ValueError):
        parse_response('{"probability":0.2,"fact_truth":true}', bundles()[0])
