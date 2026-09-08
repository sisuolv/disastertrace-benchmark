import copy
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from test_controlled_capture import config, prepared
from test_controlled_live import RATES, rechain
from test_controlled_live import prepared_execution as prepared_execution
from test_provider_capture import server

from disastertrace.automated.common import canonical, strict_json
from disastertrace.automated.provider import ProviderError
from disastertrace.automated.run_store import read_events
from disastertrace.controlled import provider_adapter, provider_capture, runtime, scorer
from disastertrace.controlled.execution import (
    authorization_template,
    contract_version,
    prepare_execution,
    verify_execution,
)
from disastertrace.controlled.live import collect, diagnostic_transport
from disastertrace.controlled.live_audit import audit_run
from disastertrace.controlled.live_report import report_run


@pytest.mark.parametrize("cap", [200, 503])
def test_p2_real_loopback_exact_bytes_and_completion_schema(cap):
    request = prepared()
    _, body = diagnostic_transport(None, request["raw_request"].encode(), None, None, None)
    with server("normal", body=body, status=cap) as (url, received, _):
        public = strict_json(request["payload"]["messages"][1]["content"])
        wire = provider_adapter.prepare(public, replace(config(), base_url=url))
        capture = provider_capture.send_prepared(wire, total_deadline=3)
    assert received == [wire["raw_request"].encode()]
    assert capture["total_deadline_enforced"] and capture["transport_terminated"]
    assert provider_capture.validate_capture(capture, wire) == body
    if cap == 200:
        assert (
            provider_capture.parse_capture(capture, wire)["metadata"]["schema_version"]
            == "controlled_provider_completion_v1"
        )
    else:
        with pytest.raises(ProviderError):
            provider_capture.parse_capture(capture, wire)


def test_p2_socket_deadline_retains_bounded_prefix():
    request = prepared()
    with server("drip", body=b"x" * 100) as (url, received, _):
        public = strict_json(request["payload"]["messages"][1]["content"])
        wire = provider_adapter.prepare(public, replace(config(), base_url=url))
        capture = provider_capture.send_prepared(wire, total_deadline=0.5)
    assert len(received) == 1
    assert capture["error_code"] == "total_deadline_exceeded"
    assert capture["transport_terminated"] is True
    assert len(provider_capture.validate_capture(capture, wire)) < 100


def test_allowance_stops_before_the_first_send(prepared_execution, tmp_path):
    execution = tmp_path / "execution"
    prepare_execution(
        prepared_execution / "dataset",
        execution,
        rates=RATES,
        registry=tmp_path / "live_registry",
        allowance_usd="0.47",
        output_contract=contract_version(verify_execution(prepared_execution)),
    )
    result = collect(execution, tmp_path / "run", transport=lambda *_: pytest.fail("budget bypass"))
    assert result["status"] == "budget_guard" and result["completed"] == 0
    assert audit_run(execution, tmp_path / "run")["attempts"] == 0


def test_cumulative_conservative_budget_stops_without_retry(prepared_execution, tmp_path):
    calls = []

    def costly(*args):
        calls.append(1)
        status, body = diagnostic_transport(*args)
        envelope = strict_json(body.decode())
        envelope["usage"] = {
            "prompt_tokens": 1048576,
            "completion_tokens": 8192,
            "total_tokens": 1056768,
        }
        return status, canonical(envelope).encode()

    result = collect(prepared_execution, tmp_path / "run", transport=costly)
    assert result["status"] == "budget_guard"
    assert result["completed"] == len(calls) == 6
    assert result["budget"]["pending"] == "0"
    assert result["budget"]["settled"] == "2.83312128"


def test_model_authored_carrier_byte_guard(prepared_execution, tmp_path):
    calls = []

    def large_carrier(*args):
        calls.append(1)
        status, body = diagnostic_transport(*args)
        envelope = strict_json(body.decode())
        if len(calls) == 7:
            answer = strict_json(envelope["choices"][0]["message"]["content"])
            answer["state"]["maximum_wind_mph"]["evidence"] *= 6000
            envelope["choices"][0]["message"]["content"] = canonical(answer)
        return status, canonical(envelope).encode()

    result = collect(prepared_execution, tmp_path / "run", transport=large_carrier)
    assert result["status"] == "request_bytes_guard"
    assert result["completed"] == len(calls) == 7
    assert result["budget"]["pending"] == "0"


@pytest.mark.parametrize(
    "field", ["max_attempts", "max_requested_output_tokens", "execution_id", "rates_sha256"]
)
def test_consumed_or_mismatched_scope_cannot_authorize_p2(prepared_execution, tmp_path, field):
    plan = verify_execution(prepared_execution)
    auth = authorization_template(plan)
    auth.update(authorized=True, authorization_evidence="TEST FIXTURE ONLY")
    auth[field] = "old-t6-identity" if isinstance(auth[field], str) else auth[field] - 1
    with pytest.raises(ValueError, match="authorization"):
        collect(prepared_execution, tmp_path / "run", authorization=auth)
    assert not (tmp_path / "run").exists()


def test_stale_price_attestation_never_claims_a_run(prepared_execution, tmp_path):
    plan = verify_execution(prepared_execution)
    auth = authorization_template(plan)
    auth.update(authorized=True, authorization_evidence="TEST FIXTURE ONLY")
    attestation = {
        "execution_id": plan["execution_id"],
        "rates_sha256": plan["rates_sha256"],
        "verified_at": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
        "evidence": "TEST FIXTURE ONLY",
    }
    with pytest.raises(ValueError, match="price attestation"):
        collect(
            prepared_execution, tmp_path / "run", authorization=auth, price_attestation=attestation
        )
    assert not (tmp_path / "run").exists()


def test_model_branch_with_mocked_socket_and_offline_finalization(
    prepared_execution, tmp_path, monkeypatch
):
    from disastertrace.automated import provider_capture as core

    plan = verify_execution(prepared_execution)
    auth = authorization_template(plan)
    auth.update(authorized=True, authorization_evidence="TEST FIXTURE ONLY; NO MODEL REQUESTS")
    attestation = {
        "execution_id": plan["execution_id"],
        "rates_sha256": plan["rates_sha256"],
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "evidence": "TEST FIXTURE ONLY",
    }
    calls = []

    def fake_socket(endpoint, body, headers, configuration, deadline):
        calls.append(body)
        status, response = diagnostic_transport(
            endpoint, body, headers, configuration.timeout, configuration.max_response_bytes
        )
        return status, response, None, True, True, True

    def fault(kind, index):
        if kind == "capture" and index == 2:
            raise RuntimeError("captured then interrupted")

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-fixture-credential")
    monkeypatch.setattr(core, "_network", fake_socket)
    output = tmp_path / "run"
    with pytest.raises(RuntimeError):
        collect(
            prepared_execution,
            output,
            authorization=auth,
            price_attestation=attestation,
            fault=fault,
        )
    monkeypatch.delenv("DEEPSEEK_API_KEY")
    recovered = collect(prepared_execution, output, resume=True, offline_only=True)
    assert recovered["completed"] == len(calls) == 3
    report = report_run(prepared_execution, output, tmp_path / "report", require_model=True)
    assert report["mode"] == "model_http"
    assert report["eligible_for_llm_leaderboard"] is False
    assert report["complete"] is False
    assert report["provider_origin_authenticated"] is False


def test_diagnostic_trace_relabeling_rejected_by_both_public_scorers(prepared_execution, tmp_path):
    plan = verify_execution(prepared_execution)
    traces = runtime.rehearse(plan["episodes"], "snapshot")
    forged = copy.deepcopy(traces)
    for row in forged:
        row.update(model_kind="model_api", eligible_for_llm_leaderboard=True, provider_requests=1)
    with pytest.raises(ValueError, match="diagnostic"):
        scorer.score(plan["episodes"], forged, "snapshot")
    # The captured scorer requires a durable journal and an execution registry claim.
    with pytest.raises(FileNotFoundError):
        report_run(
            prepared_execution, tmp_path / "no-journal", tmp_path / "report", require_model=True
        )


def test_torn_journal_cannot_resume(prepared_execution, tmp_path):
    output = tmp_path / "run"

    def stop(kind, index):
        if kind == "reserved":
            raise RuntimeError("stop before sending")

    with pytest.raises(RuntimeError):
        collect(prepared_execution, output, transport=diagnostic_transport, fault=stop)
    with (output / "journal.jsonl").open("ab") as stream:
        stream.write(b'{"partial":')
    with pytest.raises(ValueError, match="incomplete journal"):
        collect(
            prepared_execution,
            output,
            transport=lambda *_: pytest.fail("unsafe resume"),
            resume=True,
        )


def test_diagnostic_binding_cannot_be_replaced_with_model_label(prepared_execution, tmp_path):
    output = tmp_path / "run"

    def stop(kind, index):
        if kind == "capture":
            raise RuntimeError("small diagnostic prefix")

    with pytest.raises(RuntimeError):
        collect(prepared_execution, output, transport=diagnostic_transport, fault=stop)
    rechain(output, lambda events: events[0]["data"].update(mode="model_http"))
    with pytest.raises(ValueError):
        audit_run(prepared_execution, output)
    assert len(read_events(output)) == 4


def test_excessive_json_nesting_is_a_retained_schema_failure(prepared_execution, tmp_path):
    raw = "[" * 2000 + "0" + "]" * 2000

    def malformed(*args):
        status, body = diagnostic_transport(*args)
        envelope = strict_json(body.decode())
        envelope["choices"][0]["message"]["content"] = raw
        return status, canonical(envelope).encode()

    def stop(kind, index):
        if kind == "decision":
            raise RuntimeError("retained invalid decision")

    output = tmp_path / "run"
    with pytest.raises(RuntimeError, match="retained invalid decision"):
        collect(prepared_execution, output, transport=malformed, fault=stop)
    audit = audit_run(prepared_execution, output)
    assert audit["completed"] == 1 and audit["records"][0]["status"] == "invalid"
    assert audit["records"][0]["raw_response"] == raw
    report = report_run(prepared_execution, output, tmp_path / "report")
    assert report["methods"]["snapshot"]["metrics"]["schema_success"]["numerator"] == 0


def test_saved_report_is_recomputed_even_after_rehash(prepared_execution, tmp_path):
    from disastertrace.automated.common import file_hash, fingerprint, write_json
    from disastertrace.controlled.live_report import verify_report

    output = tmp_path / "run"

    def stop(kind, index):
        if kind == "decision":
            raise RuntimeError("short valid prefix")

    with pytest.raises(RuntimeError):
        collect(prepared_execution, output, transport=diagnostic_transport, fault=stop)
    directory = tmp_path / "report"
    report_run(prepared_execution, output, directory)
    assert verify_report(prepared_execution, output, directory)["status"] == "passed"
    report = strict_json((directory / "report.json").read_text())
    report["eligible_for_llm_leaderboard"] = True
    write_json(directory / "report.json", report)
    manifest = strict_json((directory / "manifest.json").read_text())
    manifest["files"]["report.json"] = file_hash(directory / "report.json")
    manifest["package_id"] = fingerprint({k: v for k, v in manifest.items() if k != "package_id"})
    write_json(directory / "manifest.json", manifest)
    with pytest.raises(ValueError):
        verify_report(prepared_execution, output, directory)


def test_full_collector_socket_path_is_labeled_as_local_fixture(prepared_execution, tmp_path):
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            received.append(body)
            status, response = diagnostic_transport(None, body, None, None, None)
            self.send_response(status)
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        def log_message(self, *_args):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    execution, output = tmp_path / "fixture_execution", tmp_path / "fixture_run"

    def fault(kind, index):
        if kind == "capture" and index == 2:
            raise RuntimeError("local captured prefix")

    try:
        prepare_execution(
            prepared_execution / "dataset",
            execution,
            rates=RATES,
            registry=tmp_path / "fixture_registry",
            fixture_url=f"http://127.0.0.1:{httpd.server_port}",
            output_contract=contract_version(verify_execution(prepared_execution)),
        )
        with pytest.raises(RuntimeError):
            collect(execution, output, fault=fault)
        result = collect(execution, output, resume=True, offline_only=True)
        assert result["completed"] == len(received) == 3
        report = report_run(execution, output, tmp_path / "report")
        assert report["mode"] == "loopback_http_fixture"
        assert report["model_calls"] == 0
        assert report["eligible_for_llm_leaderboard"] is False
        with pytest.raises(ValueError):
            report_run(execution, output, tmp_path / "model_only", require_model=True)
    finally:
        httpd.shutdown()
        thread.join()
        httpd.server_close()


def test_price_bytes_resolve_without_the_original_machine_path(prepared_execution, tmp_path):
    from disastertrace.automated.common import write_json

    rates = strict_json(RATES.read_text())
    rates["source"]["path"] = "/nonexistent-historical-machine/pricing.html"
    saved_rates = tmp_path / "rates.json"
    write_json(saved_rates, rates)
    (tmp_path / "pricing.html").write_bytes(RATES.with_name("pricing.html").read_bytes())
    execution = tmp_path / "relocated_execution"
    plan = prepare_execution(
        prepared_execution / "dataset",
        execution,
        rates=saved_rates,
        registry=tmp_path / "live_registry",
        output_contract=contract_version(verify_execution(prepared_execution)),
    )
    assert verify_execution(execution)["execution_id"] == plan["execution_id"]
