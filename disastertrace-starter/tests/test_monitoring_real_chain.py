import json
from pathlib import Path

import pytest

from disastertrace.monitoring_v1.evidence import exists_report_support, sufficient_recipes
from disastertrace.monitoring_v1.reachability import Goal, Query, solve_joint, validate_witness
from disastertrace.monitoring_v1.resources import Cost

ROOT = Path(__file__).resolve().parents[2] / "plans/v7_review_execution_20260912/regional_01"


def fixture_data():
    if not (ROOT / "REGIONAL_JOIN_AUDIT.json").exists():
        pytest.skip("Optional downloaded regional fixture is not installed")
    pairs = json.loads((ROOT / "public/E_F_PAIRS.json").read_text())
    results = {
        r["query_id"]: r for r in json.loads((ROOT / "environment/QUERY_RESULTS.json").read_text())
    }
    return pairs, results


def test_real_native_reports_form_E_query_F_triples():
    pairs, results = fixture_data()
    pair = pairs[0]
    assert pair["F_target_id"]
    assert exists_report_support(pair["query_ids"], {}, pair["threshold_m"]) == "undetermined"
    subset = {q: results[q] for q in pair["query_ids"]}
    assert exists_report_support(pair["query_ids"], subset, pair["threshold_m"]) == "refuted"
    assert sufficient_recipes(pair["query_ids"], results, pair["threshold_m"]) == (
        frozenset(pair["query_ids"]),
    )


def test_missing_or_chronology_unknown_actual_query_does_not_become_negative():
    pairs, results = fixture_data()
    pair = next(
        p
        for p in pairs
        if any(results[q]["status"] == "correction_chronology_unproven" for q in p["query_ids"])
    )
    disclosed = {q: results[q] for q in pair["query_ids"]}
    assert (
        exists_report_support(pair["query_ids"], disclosed, pair["threshold_m"]) == "undetermined"
    )
    assert not sufficient_recipes(pair["query_ids"], results, pair["threshold_m"])


def test_actual_three_station_shared_recipes_have_joint_budget_tradeoff():
    pairs, results = fixture_data()
    selected = [
        p for p in pairs if p["deadline"] == pairs[0]["deadline"] and p["threshold_m"] == 1000
    ]
    pool = sorted({q for pair in selected for q in pair["query_ids"]})
    queries = [Query(q, Cost(requests=1), 0, 1) for q in pool]
    goals = [
        Goal(p["opportunity_id"], 5, sufficient_recipes(p["query_ids"], results, 1000))
        for p in selected
    ]
    tight = solve_joint(queries, goals, {"requests": 2}, concurrency=2)
    full = solve_joint(queries, goals, {"requests": 3}, concurrency=2)
    assert tight.exact and full.exact
    assert tight.lower_bound == 3
    assert full.lower_bound == 9
    for witness in tight.frontier:
        assert validate_witness(witness, queries, goals, {"requests": 2}, concurrency=2)


def test_evaluator_only_label_payload_cannot_certify_the_fact():
    result = {
        "status": "disclosed_product_fact",
        "reference_kind": "evaluator_label",
        "support_assumption": "product_exact",
        "visible_information_scope": "evaluator",
        "reports": [{"visibility": {"lower": 0, "upper": 0}}],
    }
    assert exists_report_support(["q"], {"q": result}, 1000) == "undetermined"


def test_conflicting_support_is_not_masked_by_another_positive():
    assert (
        exists_report_support(["a", "b"], {"a": {"status": "inconsistent_same_slot_facts"}}, 1000)
        == "inconsistent"
    )
