"""Registered branches and actual calls, including failed and zero-effect cases."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

from disastertrace.monitoring_v1.analysis_integrity import validate_branch_set
from disastertrace.monitoring_v1.comparison_fingerprint import fingerprint, compare


def fixture():
    registration = {"parent_sha256": "a" * 64, "opportunity_ids": ["o1", "o2"],
                    "branches": {"none": None, "all": None}, "trace_heads": ["program"]}
    report = {"snapshots": [{"opportunity_id": o, "forecast": {"value": .2}} for o in ["o1", "o2"]],
              "calls": [{"call_id": "c1", "opportunity_id": "o1", "head": "program", "started_at": 1,
                         "proposed_probability": .2}]}
    trace = [{"call_id": "c1", "opportunity_id": "o1", "started_at": 1, "proposed_probability": .2}]
    artifacts = {k: {"report": copy.deepcopy(report), "traces": copy.deepcopy(trace),
                     "parent_sha256": "a" * 64, "actions": {}, "score_verified": True}
                 for k in registration["branches"]}
    return registration, artifacts


@pytest.mark.parametrize("fault", ["one_missing", "all_missing", "trace_missing", "empty_trace", "duplicate_trace",
                                  "duplicate_snapshot", "duplicate_call", "parent", "unknown_arm", "unknown_trace",
                                  "wrong_trace_target", "wrong_trace_probability", "score", "actions"])
def test_incomplete_or_misbound_data_cannot_pass(fault):
    reg, art = fixture()
    one = art["all"]
    if fault == "one_missing": del art["all"]
    elif fault == "all_missing": art.clear()
    elif fault == "trace_missing": one.pop("traces")
    elif fault == "empty_trace": one["traces"] = []
    elif fault == "duplicate_trace": one["traces"] *= 2
    elif fault == "duplicate_snapshot": one["report"]["snapshots"] *= 2
    elif fault == "duplicate_call": one["report"]["calls"] *= 2
    elif fault == "parent": one["parent_sha256"] = "b" * 64
    elif fault == "unknown_arm": art["unregistered"] = copy.deepcopy(one)
    elif fault == "unknown_trace": one["traces"][0]["call_id"] = "hidden"
    elif fault == "wrong_trace_target": one["traces"][0]["opportunity_id"] = "o2"
    elif fault == "wrong_trace_probability": one["traces"][0]["proposed_probability"] = .9
    elif fault == "score": one["score_verified"] = False
    elif fault == "actions": one.pop("actions")
    result = validate_branch_set(reg, art)
    assert not result["analysis_complete"] and result["issues"]
    assert result["registered_logical_branches"] == 2
    assert result["registered_opportunities"] == 2


def test_zero_effect_missing_y_and_registered_no_call_fallback_are_complete():
    reg, art = fixture()
    result = validate_branch_set(reg, art)
    assert result["analysis_complete"] and result["expected_pair_count"] == 1
    assert result["branches"]["none"]["opportunities_without_call"] == ["o2"]
    assert result["scientific_scope"] == "registered_residual_development_diagnostic"


def test_multiple_calls_per_opportunity_are_not_overwritten():
    reg, art = fixture()
    for a in art.values():
        a["report"]["calls"].append({**a["report"]["calls"][0], "call_id": "c2", "started_at": 2})
        a["traces"].append({**a["traces"][0], "call_id": "c2", "started_at": 2})
    result = validate_branch_set(reg, art)
    assert result["analysis_complete"]
    assert result["branches"]["all"]["required_trace_calls"] == ["c1", "c2"]


def test_alias_binds_existing_execution_without_extra_independent_run():
    reg, art = fixture()
    reg["branches"]["second"] = "all"
    result = validate_branch_set(reg, art)
    assert result["analysis_complete"] and result["unique_executions"] == 2
    reg["branches"]["second"] = "absent"
    assert not validate_branch_set(reg, art)["analysis_complete"]


def test_duplicate_registration_is_rejected():
    reg, art = fixture(); reg["opportunity_ids"].append("o1")
    with pytest.raises(ValueError): validate_branch_set(reg, art)


def test_fingerprints_follow_actual_consumer_not_method_name_or_unused_bank():
    config = {"predict": True, "program_prediction": "native_feature_raw", "native_feature_bank": {"mode": "values"},
              "forecast_schedule": {"kind": "slots"}, "protocol": "base_bound_override"}
    values = fingerprint(config, baseline_bank={"base": .3}, consumer_code_sha256="a"*64)
    no_acquire = fingerprint({**config, "acquire": False}, baseline_bank={"base": .3}, consumer_code_sha256="a"*64)
    follow = fingerprint({**config, "predict": False}, baseline_bank={"base": .3}, consumer_code_sha256="a"*64)
    common = fingerprint({**config, "native_feature_bank": {"mode": "common"}}, baseline_bank={"base": .3}, consumer_code_sha256="a"*64)
    assert compare(values, no_acquire)["same_predictor"]
    assert not compare(values, follow)["same_predictor"]
    assert follow["bank_sha256"] is None
    assert not compare(values, common)["same_predictor"]
    assert "acquire" in compare(values, no_acquire)["differing_factors"]


def test_bound_loader_rejects_mutated_file_before_analysis(tmp_path):
    import hashlib
    from disastertrace.monitoring_v1.analysis_integrity import load_bound_json
    path=tmp_path/"source.json";path.write_text('{"value": 1}')
    expected=hashlib.sha256(path.read_bytes()).hexdigest()
    assert load_bound_json(path,expected)=={"value":1}
    path.write_text('{"value": 2}')
    with pytest.raises(ValueError,match="registered file hash"):load_bound_json(path,expected)


@pytest.mark.parametrize("field",["data_sha256","bank_sha256"])
def test_source_bindings_are_independent_of_parent_binding(field):
    reg,art=fixture();reg[field]="a"*64
    for a in art.values():a[field]="a"*64
    assert validate_branch_set(reg,art)["analysis_complete"]
    art["all"][field]="b"*64
    assert not validate_branch_set(reg,art)["analysis_complete"]


def test_real_legacy_analyzer_missing_reports_counterexample(tmp_path):
    source=Path(__file__).resolve().parents[2]/"plans/v12_execution_20260915_01/analyze_branches.py"
    spec=importlib.util.spec_from_file_location("frozen_v12_missing_report_probe",source)
    old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    old.ROOT=tmp_path;old.REPO=tmp_path
    def put(name,value):
        p=tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value))
    put("C2_BRANCH_EXECUTION_RESULT.json",{"passed":True,"actual_treatment_attempts":2})
    put("C2_BRANCH_ROSTER.json",{"parents":[{"parent":{"case":"fixture","directory":"input/arm"},"U_parent":["o1"]}]})
    put("input/OUTCOMES.json",[{"opportunity_id":"o1","status":"mature","value":0}])
    put("branches/fixture/RESULT.json",{"results":[{"rule":"none"},{"rule":"all"}],"shared_wakeup_equal":True})
    old.main()
    legacy=json.loads((tmp_path/"C2_ENGINEERING_RESULT.json").read_text())
    assert legacy["passed"] and legacy["comparisons"] == 0
    reg,art=fixture();art.clear()
    assert not validate_branch_set(reg,art)["analysis_complete"]
