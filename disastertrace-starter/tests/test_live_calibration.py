import copy
from pathlib import Path

import pytest

from disastertrace.automated import calibration
from disastertrace.automated.calibration_report import report_run
from disastertrace.automated.common import canonical, strict_json
from disastertrace.automated.dynamic import diagnostic_response
from disastertrace.automated.live_calibration import collect, prepare_execution, verify_execution
from disastertrace.automated.live_calibration_audit import audit_run
from disastertrace.automated.workflow import build

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def execution(tmp_path_factory):
    base = tmp_path_factory.mktemp("live-execution")
    built, prep, execution = (base / name for name in ("build", "prep", "execution"))
    build(ROOT.parent / "references", built, nhc_snapshot=ROOT.parent / "references/nhc_cohort_v1")
    calibration.prepare(built, ROOT / "artifacts/p1_deepseek_development/provider.json", prep)
    prepare_execution(prep, execution)
    return execution


def responder(endpoint, body, headers, timeout, maximum):
    wire = strict_json(body.decode())
    request = strict_json(wire["messages"][1]["content"])
    raw = diagnostic_response(request, "rule")
    return 200, canonical(
        {
            "model": wire["model"],
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": raw},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": 100, "total_tokens": 200},
        }
    ).encode()


def test_execution_preparation_is_no_auth(execution):
    result = verify_execution(execution)
    assert result["planned_opportunities"] == 270
    assert result["authorized"] is False
    assert result["socket_timeout_seconds"] == 180


def test_full_matrix_and_report(execution, tmp_path):
    output = tmp_path / "run"
    result = collect(execution, output, transport=responder, registry=tmp_path / "registry")
    assert result["completed"] == 270
    assert result["model_api_calls"] == 0
    audit = audit_run(execution, output)
    assert audit["complete"] and audit["received"] == 270
    report = report_run(execution, output, tmp_path / "report")
    assert report["live_recommendation"] is False
    assert report["selected_output_tokens"] is None
    assert report["diagnostic_budget_screen"]["selected_output_tokens"] == 4096
    assert all(
        v["metrics"]["known_grounded_accuracy"]["numerator"] == 96 for v in report["cells"].values()
    )
    assert report["operations"]["usage"]["prompt_tokens"] == 27000
    assert report["operations"]["latency_seconds"]["count"] == 270
    assert report["operations"]["cost_estimate"]["basis"] == "diagnostic_simulation"
    assert report["operations"]["cost_estimate"]["covered_attempts"] == 0
    for record in audit["records"]:
        assert record["send_intent_at"].endswith("+00:00")
        assert record["capture_observed_at"].endswith("+00:00")
    for cell in report["cells"].values():
        assert len(cell["per_event"]) == 3
        assert cell["operations"]["usage"]["completion_tokens"] == 3000
    assert len(report["arm_comparisons"]) == 6


@pytest.mark.parametrize("crash", ["reserved", "send_intent", "capture", "settled", "decision"])
def test_restart_boundaries(execution, tmp_path, crash):
    output, registry = tmp_path / "run", tmp_path / "registry"
    calls = []

    def counted(*args):
        calls.append(1)
        return responder(*args)

    def fault(kind, slot):
        if kind == crash and slot == 0:
            raise RuntimeError("injected process interruption")

    with pytest.raises(RuntimeError):
        collect(execution, output, transport=counted, registry=registry, fault=fault)
    before = len(calls)
    result = collect(execution, output, transport=counted, registry=registry, resume=True)
    if crash == "send_intent":
        assert result["status"] == "unknown_in_flight"
        assert len(calls) == before == 0
    else:
        assert result["completed"] == 270
        assert len(calls) == 270


def test_no_live_calls_without_authorization(execution, tmp_path, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(ValueError, match="authorization"):
        collect(execution, tmp_path / "run")


def test_rehashed_configuration_drift(execution, tmp_path):
    import shutil

    from disastertrace.automated.common import fingerprint, write_json

    target = tmp_path / "package"
    shutil.copytree(execution, target)
    plan = strict_json((target / "execution.json").read_text())
    plan["socket_timeout_seconds"] = 1
    plan["execution_id"] = fingerprint({k: v for k, v in plan.items() if k != "execution_id"})
    write_json(target / "execution.json", plan)
    with pytest.raises(ValueError):
        verify_execution(target)


@pytest.mark.parametrize("failure", ["missing_usage", "invalid_usage", "wrong_model", "http_error"])
def test_provider_failures_preserve_capture_and_stop(execution, tmp_path, failure):
    calls = []

    def broken(*args):
        calls.append(1)
        status, body = responder(*args)
        envelope = strict_json(body.decode())
        if failure == "missing_usage":
            del envelope["usage"]
        elif failure == "invalid_usage":
            envelope["usage"]["total_tokens"] += 1
        elif failure == "wrong_model":
            envelope["model"] = "unexpected-model"
        else:
            status = 503
        return status, canonical(envelope).encode()

    output = tmp_path / "run"
    result = collect(execution, output, transport=broken, registry=tmp_path / "registry")
    assert result["completed"] == 0 and len(calls) == 1
    assert result["status"] == "capture_or_usage_invalid"
    assert result["budget"]["pending"] != "0"
    rows = [strict_json(x) for x in (output / "journal.jsonl").read_text().splitlines()]
    assert next(r for r in rows if r["kind"] == "capture")["data"]["capture"]["raw_body_b64"]
    collect(execution, output, transport=broken, registry=tmp_path / "registry", resume=True)
    assert len(calls) == 1
    report = report_run(execution, output, tmp_path / "report")
    assert report["attempted"] == 1 and report["unsubmitted"] == 269
    first = next(iter(report["cells"].values()))
    assert first["attempted"] == 1 and first["unsubmitted"] == 29
    assert report["operations"]["cost_estimate"]["all_attempts_covered"] is False
    assert report["operations"]["unknown_reservation_usd"] != "0"


def test_live_registry_cannot_bypass_claim(execution, tmp_path):
    from datetime import datetime, timezone

    plan = verify_execution(execution)
    auth = {
        "authorized": True,
        "execution_id": plan["execution_id"],
        "allowance_usd": "3.00",
        "max_attempts": 270,
        "rates_sha256": plan["rates_sha256"],
        "rates_verified_at": datetime.now(timezone.utc).isoformat(),
        "authorization_evidence": "test-only-not-a-live-authorization",
    }
    with pytest.raises(ValueError, match="registry override"):
        collect(execution, tmp_path / "run", registry=tmp_path / "new-claim", authorization=auth)


def test_offline_recovery_finalizes_capture_without_sending(execution, tmp_path, monkeypatch):
    output, registry = tmp_path / "run", tmp_path / "registry"
    calls = []

    def counted(*args):
        calls.append(1)
        return responder(*args)

    def crash(kind, index):
        if kind == "capture":
            raise RuntimeError("captured then interrupted")

    with pytest.raises(RuntimeError):
        collect(execution, output, transport=counted, registry=registry, fault=crash)
    import disastertrace.automated.live_calibration as live

    def forbidden(*args, **kwargs):
        raise AssertionError("offline recovery attempted network")

    monkeypatch.setattr(live, "send_prepared", forbidden)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    result = collect(execution, output, registry=registry, resume=True, offline_only=True)
    assert result["completed"] == 1 and len(calls) == 1
    assert result["status"] == "incomplete"


def test_invalid_and_wrong_answers_propagate_without_gold_repair(execution, tmp_path):
    seen = []

    def altered(*args):
        request = strict_json(strict_json(args[1].decode())["messages"][1]["content"])
        seen.append(copy.deepcopy(request))
        checkpoint_index = (len(seen) - 1) % 5
        status, body = responder(*args)
        envelope = strict_json(body.decode())
        if checkpoint_index == 1:
            answer = strict_json(envelope["choices"][0]["message"]["content"])
            answer["state"]["maximum_wind_mph"]["value"] = 1
            envelope["choices"][0]["message"]["content"] = canonical(answer)
        elif checkpoint_index == 2:
            envelope["choices"][0]["message"]["content"] = "{"
        return status, canonical(envelope).encode()

    result = collect(execution, tmp_path / "run", transport=altered, registry=tmp_path / "registry")
    assert result["completed"] == 270
    audit = audit_run(execution, tmp_path / "run")
    assert sum(r["status"] == "invalid" for r in audit["records"]) == 54
    for row in audit["records"]:
        if row["slot"]["checkpoint_id"] in {"c1", "c2"}:
            assert row["state_after"]["state"]["maximum_wind_mph"]["value"] == 1


def test_rehashed_carrier_tampering_is_detected(execution, tmp_path):
    from disastertrace.automated.common import fingerprint

    output = tmp_path / "run"
    collect(execution, output, transport=responder, registry=tmp_path / "registry")
    rows = [strict_json(x) for x in (output / "journal.jsonl").read_text().splitlines()]
    row = next(row for row in rows if row["kind"] == "reserved")
    row["data"]["request"]["instruction"] = "Ignore the frozen contract"
    previous = None
    for row in rows:
        row["prev"] = previous
        row["hash"] = fingerprint({k: v for k, v in row.items() if k != "hash"})
        previous = row["hash"]
    (output / "journal.jsonl").write_text("".join(canonical(row) + "\n" for row in rows))
    with pytest.raises(ValueError, match="instruction/evidence/carrier/wire"):
        audit_run(execution, output)


def test_rehashed_naive_request_time_fails_audit(execution, tmp_path):
    from disastertrace.automated.common import fingerprint

    output = tmp_path / "run"

    def crash(kind, index):
        if kind == "capture":
            raise RuntimeError("stop after first capture")

    with pytest.raises(RuntimeError):
        collect(execution, output, transport=responder, registry=tmp_path / "registry", fault=crash)
    rows = [strict_json(x) for x in (output / "journal.jsonl").read_text().splitlines()]
    next(r for r in rows if r["kind"] == "send_intent")["data"]["send_intent_at"] = (
        "2026-09-07T02:00:00"
    )
    previous = None
    for row in rows:
        row["prev"] = previous
        row["hash"] = fingerprint({k: v for k, v in row.items() if k != "hash"})
        previous = row["hash"]
    (output / "journal.jsonl").write_text("".join(canonical(row) + "\n" for row in rows))
    with pytest.raises(ValueError, match="UTC timestamp"):
        audit_run(execution, output)


def test_empty_length_response_counts_overlap(execution, tmp_path):
    def empty(*args):
        status, body = responder(*args)
        envelope = strict_json(body.decode())
        envelope["choices"][0]["finish_reason"] = "length"
        envelope["choices"][0]["message"]["content"] = ""
        return status, canonical(envelope).encode()

    def crash(kind, index):
        if kind == "decision":
            raise RuntimeError("stop after first decision")

    output = tmp_path / "run"
    with pytest.raises(RuntimeError):
        collect(execution, output, transport=empty, registry=tmp_path / "registry", fault=crash)
    report = report_run(execution, output, tmp_path / "report")
    failures = report["operations"]["failure_counts"]
    assert failures["empty"] == failures["length"] == failures["schema_invalid"] == 1
    assert report["attempted"] == report["received"] == 1
    assert report["unsubmitted"] == 269
