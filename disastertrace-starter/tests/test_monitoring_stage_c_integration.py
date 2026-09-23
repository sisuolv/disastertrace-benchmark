"""Offline transport rehearsal of the actual annual comparison orchestrator.

The source fixture is an already exposed two-hour archive. Banks and model
responses are synthetic; these runs are never counted as weather experiments.
"""
import copy
import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

import pytest
from test_monitoring_native_feature_session import setup

from disastertrace.monitoring_fixed_v1.outcomes import ComparisonContract
from disastertrace.monitoring_fixed_v1.admission import AdmissionEngine
from disastertrace.monitoring_v1.formal_session import FORMAL_CONFIG, score_formal
from disastertrace.monitoring_v1.spool_backend import digest, publish, read


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[2] / "plans/v12_execution_20260915_01"
    monkeypatch.syspath_prepend(str(source))
    spec = importlib.util.spec_from_file_location("stage_c_integration", source / "stage_c.py")
    stage = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(stage)
    run = tmp_path / "run"
    out = run / "stage_C"
    out.mkdir(parents=True)
    monkeypatch.setattr(stage, "RUN", run)
    monkeypatch.setattr(stage, "OUT", out)
    for name in ("stage_c.py", "siliconflow_worker.py"):
        shutil.copy2(source / name, run / name)
    publish(run / "EXECUTION_AUTHORIZATION.json", {"credential_path": "unused_offline"})
    data, bank, cfg = setup(
        isolation_mode="actual_cost_clock",
        forecast_schedule={"kind": "public_serial_slots.v1", "lead_seconds": 120, "spacing_seconds": 30},
        failure_continuation_policy="skip_failed_call_continue_v1",
    )
    cfg.update(FORMAL_CONFIG)
    cfg.update(input_token_cap=32768, output_token_cap=512, token_cap=24*33280,
               compute_ms_cap=24*120000, authorization_mode="session_shared", persistence_latency_ms=1)
    original = tmp_path / "original"
    original.mkdir()
    for name, obj in (("DATA", data), ("BANK", bank), ("CONFIGS", {"B11_COVERAGE": cfg}), ("OUTCOMES", [])):
        publish(original / (name + ".json"), obj)
    fit = run / "annual_stage_B/fit"
    fit.mkdir(parents=True)
    values = cfg["native_feature_bank"]
    common = copy.deepcopy(values)
    common.update(mode="common", feature_names=["taf_present"])
    for mode, obj in (("common", common), ("values", values)):
        publish(fit / ("BANK_" + mode + ".json"), obj)
    publish(fit / "BANK_FREEZE.json", {"banks": {m: digest(fit / ("BANK_"+m+".json")) for m in ("common", "values")}})
    publish(out / "INTENT.json", {"model": "synthetic-model", "cases": [{"case": "fixture", "original": str(original)}],
        "model_HTTP_deadline_at": "2099-01-01T00:00:00+00:00"})
    stage.prepare_cases()
    return stage, data


@pytest.mark.parametrize("response_kind", ["valid", "invalid", "http_failure"])
def test_real_spool_and_formal_controller_keep_denominator_and_costs(prepared, monkeypatch, response_kind):
    stage, data = prepared
    sent = []
    original_deliver = stage.deliver

    def send(payload, policy):
        sent.append(payload)
        view = json.loads(payload["messages"][-1]["content"])
        assert "outcomes" not in view
        assert view["forecast_handles_are_ignored"] is True
        answer = json.dumps({"query_order": list(view["queries"]), "forecast_handles": []})
        if response_kind == "invalid":
            answer = "not valid JSON"
        body = json.dumps({"model": policy["model"], "usage": {"prompt_tokens": 100, "completion_tokens": 20},
            "choices": [{"finish_reason": "stop", "message": {"content": answer}}]}).encode()
        return (429 if response_kind == "http_failure" else 200), body, hashlib.sha256(body).hexdigest(), False

    monkeypatch.setattr(stage, "deliver", lambda b, c, p: original_deliver(b, c, p, send=send))
    result = stage.run_arm(("fixture", "LLM_SELECTOR"))
    assert result["passed"], result
    assert len(sent) == len({o["cutoff"] for o in data["opportunities"]})
    case = stage.OUT / "fixture"
    report = read(case / "LLM_SELECTOR/FORMAL_REPORT.json")
    assert len(report["snapshots"]) == len(data["opportunities"])
    assert len(list((case / "spool").glob("*.api_intent.json"))) == len(sent)
    assert report["actual_model_calls"] == len(sent)
    assert all(c["head"] == "program" for c in report["calls"])
    cfg = read(case / "CONFIGS.json")["LLM_SELECTOR"]
    assert len(report["calls"]) == cfg["per_tick_forecast_cap"] * len(sent)
    assert all(c["started_at"] < next(o["cutoff"] for o in data["opportunities"]
        if o["opportunity_id"] == c["opportunity_id"]) for c in report["calls"])
    assert (case / "LLM_SELECTOR/STOP.json").exists()
    if response_kind == "http_failure":
        assert len(list((case / "spool").glob("*.failure.json"))) == len(sent)
        assert report["resource_reserved"]["tokens"] > 0
    else:
        assert report["resource_spent"]["tokens"] == 120 * len(sent)
        errors = [r["response_error"] for r in report["selector_calls"]]
        assert all(errors) if response_kind == "invalid" else not any(errors)
    # Frozen real scoring consumes the managed journal even without model success.
    group = read(case / "COMPARISONS.json")["values"]["contract"]["payload"]
    comparison = ComparisonContract(group["invariants"], group["allowed_interventions"])
    engine = AdmissionEngine.restore(report["event_replay"])
    outcomes = [{
        "opportunity_id": oid, "target_contract_hash": o.target.contract_hash,
        "resolution_version": "missing-test.v1", "value": None, "status": "missing",
        "source_revision": "no-observation", "source_sha256": None,
        "physical_start": o.target.physical_start, "physical_end": o.target.physical_end,
        "units": o.target.units, "quality_status": "missing", "observed_at": None,
        "published_at": None, "fetched_at": None, "resolved_at": o.target.physical_end+1,
        "availability_basis": "declared_archive_scenario", "resolution_policy": "h15_routine_archive.v1",
        "provider": "IEM", "provider_version": "native_h15_snapshot.v1",
        "reference_kind": "final_archived_routine_report_not_continuous_physical_truth",
    } for oid,o in engine.opportunities.items()]
    scored = score_formal(outcomes, {"model": case / "LLM_SELECTOR/admission.jsonl"},
        comparison=comparison, run_references={"model": case / "LLM_SELECTOR"})
    assert scored is not None


def test_all_program_controls_use_frozen_raw_banks_without_model_dispatch(prepared):
    stage, data = prepared
    case = stage.OUT / "fixture"
    for arm in stage.ARMS[1:]:
        result = stage.run_arm(("fixture", arm))
        assert result["passed"], result
        assert result["actual_model_calls"] == 0
        assert result["opportunities"] == len(data["opportunities"])
    assert not list((case / "spool").glob("*.api_intent.json"))
    cfg = read(case / "CONFIGS.json")
    assert all("post_calibration" not in c["native_feature_bank"] for c in cfg.values())
    assert cfg["B00_COVERAGE"]["authorization_mode"] == "target_private"
    assert cfg["B01_COVERAGE"]["allocation_mode"] == "fixed_quota"
    assert cfg["B10_COVERAGE"]["allocation_mode"] == "global_budget"
