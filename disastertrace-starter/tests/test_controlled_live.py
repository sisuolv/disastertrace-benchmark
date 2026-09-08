from pathlib import Path

import pytest

from disastertrace.automated.common import canonical, fingerprint, strict_json, write_json
from disastertrace.automated.run_store import read_events
from disastertrace.automated.workflow import build
from disastertrace.controlled import package, runtime, scorer
from disastertrace.controlled.execution import prepare_execution, verify_execution
from disastertrace.controlled.live import collect, diagnostic_transport
from disastertrace.controlled.live_audit import audit_run
from disastertrace.controlled.live_report import report_run
from disastertrace.controlled.output_contract import VERSIONS

ROOT = Path(__file__).resolve().parents[1]
RATES = ROOT / "artifacts/p1_deepseek_development/docs/rates.json"


@pytest.fixture(scope="module", params=VERSIONS)
def prepared_execution(tmp_path_factory, request):
    base = tmp_path_factory.mktemp("p2-execution")
    built, dataset, execution = (base / n for n in ("build", "dataset", "execution"))
    build(ROOT.parent / "references", built, nhc_snapshot=ROOT.parent / "references/nhc_cohort_v1")
    package.prepare(built, dataset)
    prepare_execution(
        dataset,
        execution,
        rates=RATES,
        registry=base / "live_registry",
        output_contract=request.param,
    )
    return execution


def test_p2_frozen_scope_and_own_output_reservation(prepared_execution):
    plan = verify_execution(prepared_execution)
    assert plan["protocol"] == "disastertrace_controlled_v1"
    assert plan["planned_opportunities"] == 270
    assert plan["budget"]["max_requested_output_tokens"] == 2211840
    assert plan["config"]["max_output_tokens"] == 8192
    assert plan["authorized"] is False
    assert len(plan["episodes"]) == 18
    assert {ep["split"] for ep in plan["episodes"]} == {"development"}


def test_full_matrix_direct_scoring_and_origin_gate(prepared_execution, tmp_path):
    output = tmp_path / "run"
    summary = collect(prepared_execution, output, transport=diagnostic_transport)
    audit = audit_run(prepared_execution, output)
    assert summary["completed"] == audit["attempts"] == audit["received"] == 270
    assert audit["budget"]["pending"] == "0"
    assert len(audit["histories"]) == 54
    assert audit["model_api_calls"] == 0
    report = report_run(prepared_execution, output, tmp_path / "report")
    assert report["eligible_for_llm_leaderboard"] is False
    assert report["reliability"]["measured_model_reliability"] is False
    assert report["model_calls"] == 0
    for method, cell in report["methods"].items():
        assert cell["metrics"]["known_grounded_accuracy"]["numerator"] == 282
        assert cell["metrics"]["unknown_accuracy"]["denominator"] == 78
        baseline = scorer.score(
            verify_execution(prepared_execution)["episodes"],
            runtime.rehearse(verify_execution(prepared_execution)["episodes"], method),
            method,
        )
        assert cell["metrics"] == baseline["metrics"]
    with pytest.raises(ValueError):
        report_run(prepared_execution, output, tmp_path / "model-only", require_model=True)
    with pytest.raises(ValueError):
        collect(
            prepared_execution,
            tmp_path / "duplicate",
            transport=diagnostic_transport,
            registry=tmp_path / "diagnostic_registry",
        )


@pytest.mark.parametrize("boundary", ["reserved", "send_intent", "capture", "settled", "decision"])
def test_interruption_resume_and_offline_recovery(prepared_execution, tmp_path, boundary):
    output = tmp_path / "run"
    calls = []

    def counted(*args):
        calls.append(1)
        return diagnostic_transport(*args)

    def fault(kind, index):
        if kind == boundary and index == 1:
            raise RuntimeError("injected interruption")

    with pytest.raises(RuntimeError):
        collect(prepared_execution, output, transport=counted, fault=fault)
    before = len(calls)
    recovered = collect(prepared_execution, output, resume=True, offline_only=True)
    assert len(calls) == before
    if boundary == "send_intent":
        assert recovered["status"] == "unknown_in_flight"
        assert recovered["budget"]["pending"] != "0"
        stopped = collect(prepared_execution, output, transport=counted, resume=True)
        assert stopped["status"] == "unknown_in_flight" and len(calls) == before
    else:
        complete = collect(prepared_execution, output, transport=counted, resume=True)
        assert complete["completed"] == 270 and len(calls) == 270


@pytest.mark.parametrize(
    "failure", ["missing_usage", "invalid_usage", "wrong_model", "http_error", "timeout"]
)
def test_failure_capture_unknown_budget_and_fixed_denominators(
    prepared_execution, tmp_path, failure
):
    calls = []

    def broken(*args):
        calls.append(1)
        if failure == "timeout":
            raise TimeoutError("fixture only")
        status, body = diagnostic_transport(*args)
        value = strict_json(body.decode())
        if failure == "missing_usage":
            del value["usage"]
        elif failure == "invalid_usage":
            value["usage"]["total_tokens"] += 1
        elif failure == "wrong_model":
            value["model"] = "different-model"
        else:
            status = 503
        return status, canonical(value).encode()

    output = tmp_path / "run"
    result = collect(prepared_execution, output, transport=broken)
    assert result["completed"] == 0 and len(calls) == 1
    assert result["budget"]["pending"] != "0"
    assert collect(prepared_execution, output, transport=broken, resume=True)["completed"] == 0
    assert len(calls) == 1
    report = report_run(prepared_execution, output, tmp_path / "report")
    assert report["attempted"] == 1 and report["unsubmitted"] == 269
    assert (
        sum(cell["metrics"]["schema_success"]["denominator"] for cell in report["methods"].values())
        == 270
    )
    assert report["operations"]["unknown_reservation_usd"] != "0"


def test_invalid_outputs_retain_prior_wrong_claim_without_gold_repair(prepared_execution, tmp_path):
    calls = []

    def altered(*args):
        calls.append(1)
        status, body = diagnostic_transport(*args)
        envelope = strict_json(body.decode())
        checkpoint = (len(calls) - 1) % 5
        if checkpoint == 1:
            answer = strict_json(envelope["choices"][0]["message"]["content"])
            for slot in answer["state"].values():
                if slot["status"] == "known" and slot["value"] < 300:
                    slot["value"] = 1
                    break
            envelope["choices"][0]["message"]["content"] = canonical(answer)
        elif checkpoint == 2:
            envelope["choices"][0]["message"]["content"] = ""
            envelope["choices"][0]["finish_reason"] = "length"
        return status, canonical(envelope).encode()

    output = tmp_path / "run"
    collect(prepared_execution, output, transport=altered)
    audit = audit_run(prepared_execution, output)
    assert len(audit["records"]) == 270
    assert sum(r["status"] == "invalid" for r in audit["records"]) == 54
    for i in range(0, 270, 5):
        assert audit["records"][i + 2]["state_after"] == audit["records"][i + 1]["state_after"]
        assert audit["records"][i]["request"].get("previous_state") is None
        assert not audit["records"][i]["request"].get("answer_history")
    report = report_run(prepared_execution, output, tmp_path / "report")
    assert report["operations"]["failure_counts"]["length"] == 54
    assert report["reliability"]["thresholds_passed"] is False


def rechain(output, change):
    events = read_events(output)
    change(events)
    previous = None
    for event in events:
        event["prev"] = previous
        event["hash"] = fingerprint({k: v for k, v in event.items() if k != "hash"})
        previous = event["hash"]
    (output / "journal.jsonl").write_text("".join(canonical(e) + "\n" for e in events))


@pytest.mark.parametrize("tamper", ["carrier", "origin", "time", "settlement", "decision"])
def test_rehashed_journal_tampering_fails_independent_audit(prepared_execution, tmp_path, tamper):
    output = tmp_path / "run"

    def fault(kind, index):
        if kind == "decision" and index == 2:
            raise RuntimeError("fixture prefix")

    with pytest.raises(RuntimeError):
        collect(prepared_execution, output, transport=diagnostic_transport, fault=fault)

    def change(events):
        if tamper == "carrier":
            next(e for e in events if e["kind"] == "reserved")["data"]["request"][
                "instruction"
            ] += " PRIVATE"
        elif tamper == "origin":
            next(e for e in events if e["kind"] == "capture")["data"]["capture"]["origin"] = (
                "urllib_http"
            )
        elif tamper == "time":
            next(e for e in events if e["kind"] == "capture")["data"]["capture_observed_at"] = (
                "2000-01-01T00:00:00+00:00"
            )
        elif tamper == "settlement":
            next(e for e in events if e["kind"] == "settled")["data"]["settlement"]["cost"] = "0"
        else:
            next(e for e in events if e["kind"] == "decision")["data"]["raw_response"] = "{}"

    rechain(output, change)
    with pytest.raises(ValueError):
        audit_run(prepared_execution, output)


def test_authorization_before_credential_or_claim(prepared_execution, tmp_path, monkeypatch):
    import disastertrace.controlled.live as live

    monkeypatch.setattr(
        live.os.environ, "get", lambda *_: pytest.fail("credential read before authorization")
    )
    with pytest.raises(ValueError, match="authorization"):
        collect(prepared_execution, tmp_path / "run")
    assert not (tmp_path / "run").exists()


@pytest.mark.parametrize("field", ["config", "schedule", "budget", "episodes"])
def test_rehashed_execution_scope_drift_is_rejected(prepared_execution, tmp_path, field):
    import shutil

    destination = tmp_path / "changed"
    shutil.copytree(prepared_execution, destination)
    plan = strict_json((destination / "execution.json").read_text())
    if field == "config":
        plan[field]["max_output_tokens"] = 4096
    elif field == "budget":
        plan[field]["max_requested_output_tokens"] = 1474560
    elif field == "schedule":
        plan[field] = plan[field][::-1]
    else:
        plan[field][0]["split"] = "heldout"
    plan["execution_id"] = fingerprint({k: v for k, v in plan.items() if k != "execution_id"})
    write_json(destination / "execution.json", plan)
    with pytest.raises(ValueError):
        verify_execution(destination)
