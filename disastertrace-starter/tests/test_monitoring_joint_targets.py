"""X09 changes answer scope while keeping the disclosed information identical."""

import copy
import json
from dataclasses import replace

import pytest
from test_monitoring_decision_inputs import baseline, probability_engine

from disastertrace.monitoring_fixed_v1.contracts import EvidenceBundle
from disastertrace.monitoring_fixed_v1.joint_targets import (
    build_joint_context,
    joint_messages,
    parse_joint_response,
)


def bundles(with_asset=False):
    _, target = probability_engine()
    result = []
    for index in range(3):
        t = replace(target, target_id="t" + str(index), entity="station:" + str(index))
        bundle, _ = baseline(t, 0.1 + index / 10, 10, "r1")
        row = bundle.policy_view()
        row["opportunity_id"] = "op-" + t.target_id
        row["baseline"]["content"]["E_question"] = {
            "predicate": "any_registered_neighbor_slot_below_threshold",
            "query_ids": ["a"],
            "threshold_m": 5000,
        }
        if with_asset:
            rid = "receipt-" + t.target_id
            row["receipts"] = [
                {
                    "receipt_id": rid,
                    "owner": t.target_id,
                    "asset_ids": ["a"],
                    "started_at": 10,
                    "completed_at": 11,
                    "cost": {"requests": 1, "bytes": 100, "tokens": 0, "compute_ms": 1},
                }
            ]
            row["assets"] = [
                {
                    "asset_id": "a",
                    "source_revision": "v1",
                    "raw": "native text",
                    "content": {"query_id": "a", "reports": []},
                    "available_at": 10,
                    "observed_at": 9,
                    "completed_at": 11,
                    "entitlements": [t.target_id],
                    "receipt_ids": [rid],
                    "parents": [],
                    "transform": {"version": "v1", "parameters": {}},
                    "reference_kind": "product_label",
                    "support_assumption": "product_exact",
                    "visible_information_scope": "policy_after_query",
                    "support_rule_version": "v1",
                    "missingness": "disclosed_product_fact",
                }
            ]
        result.append(EvidenceBundle.freeze(row))
    return result


def context(with_asset=False):
    return build_joint_context(bundles(with_asset), access_mode="shared_disclosed_union")


def test_single_and_joint_use_identical_context_and_system_instructions():
    c = context()
    together = joint_messages(c, ["t0", "t1", "t2"], head="joint")
    single = joint_messages(c, ["t1"], head="joint")
    assert together[0] == single[0]
    a, b = json.loads(together[1]["content"]), json.loads(single[1]["content"])
    assert a["context"] == b["context"] == c
    assert a["answer_target_ids"] == ["t0", "t1", "t2"]
    assert b["answer_target_ids"] == ["t1"]


def test_shared_union_deduplicates_same_product_but_preserves_all_source_bindings():
    original = bundles(True)
    before = [b.to_dict() for b in original]
    c = build_joint_context(original, access_mode="shared_disclosed_union")
    assert len(c["shared_sources"]) == 1
    assert c["shared_sources"][0]["entitlements"] == ["t0", "t1", "t2"]
    assert len(c["original_bundle_bindings"]) == 3
    assert [b.to_dict() for b in original] == before


def test_private_inputs_are_not_silently_relabelled_as_a_private_joint_condition():
    with pytest.raises(ValueError, match="shared"):
        build_joint_context(bundles(), access_mode="target_private")


@pytest.mark.parametrize("change", ["cutoff", "physical_start", "threshold", "protocol"])
def test_different_forecast_questions_cannot_be_mixed_in_one_registered_cohort(change):
    items = bundles()
    row = items[-1].policy_view()
    if change == "cutoff":
        row["cutoff"] -= 1
    elif change == "protocol":
        row["state"]["protocol"] = "persistent_override"
    else:
        row["target"][change] += 1
        if change == "physical_start":
            row["target"]["physical_end"] += 1
        from disastertrace.monitoring_fixed_v1.contracts import Target

        t = Target(**row["target"])
        for container in (row["baseline"], row["state"]):
            container["forecast"]["target_contract_hash"] = t.contract_hash
    items[-1] = EvidenceBundle.freeze(row)
    with pytest.raises(ValueError, match="cohort"):
        build_joint_context(items, access_mode="shared_disclosed_union")


def test_same_source_id_with_different_contents_requires_explicit_resolution():
    items = bundles(True)
    row = items[-1].policy_view()
    row["assets"][0]["raw"] = "different revision content"
    items[-1] = EvidenceBundle.freeze(row)
    with pytest.raises(ValueError, match="source"):
        build_joint_context(items, access_mode="shared_disclosed_union")


@pytest.mark.parametrize("ids", [[], ["t0", "t0"], ["unknown"]])
def test_answer_scope_must_be_nonempty_unique_and_registered(ids):
    with pytest.raises(ValueError):
        joint_messages(context(), ids, head="joint")


def test_joint_response_can_use_any_target_order_but_no_missing_target():
    raw = json.dumps(
        {
            "answers": [
                {"target_id": tid, "fact_truth": "unknown", "probability": 0.2}
                for tid in ("t2", "t0", "t1")
            ]
        }
    )
    parsed = parse_joint_response(raw, context(), ["t0", "t1", "t2"], head="joint")
    assert set(parsed) == {"t0", "t1", "t2"}
    assert parsed["t0"]["probability"] == 0.2


@pytest.mark.parametrize(
    "raw",
    [
        '{"answers":[]}',
        '{"answers":[{"target_id":"t0","fact_truth":"unknown","probability":true}]}',
        '{"answers":[{"target_id":"t0","fact_truth":"unknown","probability":NaN}]}',
        '{"answers":[{"target_id":"t0","fact_truth":false,"probability":0.2}]}',
        '{"answers":[{"target_id":"t0","fact_truth":"unknown","probability":1.1}]}',
        '{"answers":[{"target_id":"t0","target_id":"t1","fact_truth":"unknown","probability":0.2}]}',
        '{"answers":[{"target_id":"t0","fact_truth":"unknown","probability":0.2},{"target_id":"t0","fact_truth":"unknown","probability":0.2}]}',
        '{"answers":[{"target_id":"t1","fact_truth":"unknown","probability":0.2}]}',
        '{"answers":[{"target_id":"t0","fact_truth":"unknown","probability":0.2,"reason":"extra"}]}',
        '```json\n{"answers":[]}\n```',
    ],
)
def test_invalid_prediction_keeps_the_requested_denominator_and_is_rejected(raw):
    with pytest.raises(ValueError):
        parse_joint_response(raw, context(), ["t0"], head="joint")


@pytest.mark.parametrize(
    "head,answer",
    [
        ("e_only", {"target_id": "t0", "fact_truth": "conflict"}),
        ("f_only", {"target_id": "t0", "probability": 0}),
    ],
)
def test_E_and_F_heads_have_separate_output_fields(head, answer):
    c = context()
    assert (
        parse_joint_response(json.dumps({"answers": [answer]}), c, ["t0"], head=head)["t0"]
        == answer
    )
    bad = copy.deepcopy(answer)
    bad["probability" if head == "e_only" else "fact_truth"] = 0.5
    with pytest.raises(ValueError):
        parse_joint_response(json.dumps({"answers": [bad]}), c, ["t0"], head=head)
