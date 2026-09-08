import copy
import os
import shutil
import subprocess
import sys
from dataclasses import replace

import pytest
from test_controlled_capture import config, responder
from test_controlled_live import ROOT, rechain
from test_controlled_live import prepared_execution as prepared_execution
from test_provider_capture import server

from disastertrace.automated.common import canonical, fingerprint, strict_json, write_json
from disastertrace.automated.provider import ProviderConfig
from disastertrace.controlled import generator, provider_adapter, provider_capture, renderer
from disastertrace.controlled.execution import contract_version, read, verify_execution
from disastertrace.controlled.live import collect, diagnostic_transport
from disastertrace.controlled.live_audit import audit_run
from disastertrace.controlled.output_contract import V1, V2, VERSIONS, identity, system_message
from disastertrace.controlled.schema import METHODS, empty_decision, parse_decision


def request(method="snapshot"):
    previous = empty_decision()
    previous["state"]["maximum_wind_mph"] = {
        "status": "known",
        "value": 1,
        "evidence": [{"record_id": "INCORRECT_MODEL_CLAIM", "line": 2}],
    }
    previous["action"] = "monitor"
    return renderer.render_request(
        generator.micro_episodes()[0],
        "c1",
        method=method,
        previous=previous,
        history=[previous],
    )


@pytest.mark.parametrize("method", METHODS)
def test_v1_envelope_matches_the_previous_frozen_implementation(method):
    public = request(method)
    source = (
        ROOT / "artifacts/p2_deepseek_development_v1/execution/dataset/implementation_source/src"
    )
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join((str(ROOT / "scripts/offline_guard"), str(source))),
        "PYTHONDONTWRITEBYTECODE": "1",
        "DISASTERTRACE_OFFLINE": "1",
    }
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from disastertrace.automated.common import canonical, strict_json; "
            "from disastertrace.automated.provider import ProviderConfig; "
            "from disastertrace.controlled.provider_adapter import prepare; "
            "d = strict_json(sys.stdin.read()); "
            "print(canonical(prepare(d['request'], ProviderConfig.from_dict(d['config']))))",
        ],
        env=env,
        input=canonical(
            {"request": public, "config": provider_adapter.prepare(public, config())["config"]}
        ),
        capture_output=True,
        text=True,
        check=True,
    )
    assert strict_json(result.stdout) == provider_adapter.prepare(public, config())


def test_common_system_and_same_public_exposure_for_all_methods_and_checkpoints():
    systems = set()
    for episode in generator.micro_episodes():
        for checkpoint in episode["checkpoints"]:
            for method in METHODS:
                public = renderer.render_request(
                    episode, checkpoint["checkpoint_id"], method=method
                )
                old = provider_adapter.prepare(public, config())
                new = provider_adapter.prepare(public, config(), output_contract=V2)
                systems.add(new["payload"]["messages"][0]["content"])
                assert [m["role"] for m in new["payload"]["messages"]] == ["system", "user"]
                assert new["payload"]["messages"][1] == old["payload"]["messages"][1]
                assert new["raw_request"].encode() == canonical(new["payload"]).encode()
                projected = copy.deepcopy(new["payload"])
                projected["messages"][0] = old["payload"]["messages"][0]
                assert projected == old["payload"]
                assert new["config"] == old["config"]
                assert new["output_contract"] == identity(V2)
                assert new["request_sha256"] != old["request_sha256"]
                assert "response_format" not in new["payload"]
                assert public["instruction"] == renderer.INSTRUCTION
                for delivery in episode["deliveries"]:
                    if delivery["delivered_at"] > checkpoint["at"]:
                        assert delivery["delivery_id"] not in new["raw_request"]
                assert episode["episode_id"] not in new["raw_request"]
                assert "private/gold" not in new["raw_request"]
    assert systems == {system_message(V2)}


@pytest.mark.parametrize("version", VERSIONS)
@pytest.mark.parametrize("method", METHODS)
def test_exact_loopback_bytes_and_cross_contract_capture_rejection(version, method):
    public = request(method)
    wire = provider_adapter.prepare(public, config(), output_contract=version)
    _, body = responder(None, wire["raw_request"].encode(), None, None, None)
    with server("normal", body=body) as (url, received, _):
        cfg = replace(config(), base_url=url)
        wire = provider_adapter.prepare(public, cfg, output_contract=version)
        capture = provider_capture.send_prepared(wire, total_deadline=3)
    assert received == [wire["raw_request"].encode()]
    assert provider_capture.validate_capture(capture, wire) == body
    alternate = provider_adapter.prepare(public, cfg, output_contract=V1 if version == V2 else V2)
    with pytest.raises(ValueError):
        provider_capture.parse_capture(capture, alternate)
    exposed = strict_json(wire["payload"]["messages"][1]["content"])
    if method == "structured_state":
        assert exposed["previous_state"] == public["previous_state"]
    elif method == "answer_history":
        assert exposed["answer_history"] == public["answer_history"]


@pytest.mark.parametrize(
    "tamper",
    [
        "drop_identity",
        "legacy_identity",
        "unknown_version",
        "digest",
        "system",
        "roles",
        "extra_message",
        "gold",
    ],
)
def test_rehashed_mixed_contract_preparation_never_dispatches(tamper):
    wire = provider_adapter.prepare(request(), config(), output_contract=V2)
    if tamper == "drop_identity":
        del wire["output_contract"]
    elif tamper == "legacy_identity":
        wire["output_contract"] = identity(V1)
    elif tamper == "unknown_version":
        wire["output_contract"]["version"] = "invented-v3"
    elif tamper == "digest":
        wire["output_contract"]["system_message_sha256"] = "0" * 64
    elif tamper == "system":
        wire["payload"]["messages"][0]["content"] += " Additional instruction."
    elif tamper == "roles":
        wire["payload"]["messages"][0]["role"] = "user"
    elif tamper == "extra_message":
        wire["payload"]["messages"].append({"role": "assistant", "content": "private claim"})
    else:
        public = strict_json(wire["payload"]["messages"][1]["content"])
        public["gold"] = "PRIVATE_SENTINEL"
        wire["payload"]["messages"][1]["content"] = canonical(public)
    wire["raw_request"] = canonical(wire["payload"])
    wire["wire_payload_sha256"] = fingerprint(wire["payload"])
    keys = ["endpoint", "config", "payload"] + (
        ["output_contract"] if "output_contract" in wire else []
    )
    wire["request_sha256"] = fingerprint({k: wire[k] for k in keys})
    with pytest.raises(ValueError, match="invalid prepared"):
        provider_capture.send_prepared(wire, transport=lambda *_: pytest.fail("invalid dispatch"))


@pytest.mark.parametrize("field", ["gold", "future_deliveries", "previous_state"])
@pytest.mark.parametrize("version", VERSIONS)
def test_versioned_preparers_reject_private_and_cross_method_fields(field, version):
    public = request()
    public[field] = "PRIVATE_SENTINEL"
    with pytest.raises(ValueError):
        provider_adapter.prepare(public, config(), output_contract=version)


def test_execution_contract_and_authorization_template_are_bound(prepared_execution):
    plan = verify_execution(prepared_execution)
    version = contract_version(plan)
    assert version in VERSIONS
    if version == V2:
        assert plan["schema_version"] == "controlled_execution_v2"
        assert plan["output_contract"] == identity(V2)
    else:
        assert "output_contract" not in plan
    auth = read(prepared_execution / "authorization.template.json")
    assert auth["execution_id"] == plan["execution_id"] and auth["authorized"] is False


def test_rehashed_cross_contract_reservation_is_rejected(prepared_execution, tmp_path):
    output = tmp_path / "run"
    version = contract_version(verify_execution(prepared_execution))

    def stop(kind, index):
        if kind == "reserved":
            raise RuntimeError("unsent fixture prefix")

    with pytest.raises(RuntimeError):
        collect(prepared_execution, output, transport=diagnostic_transport, fault=stop)

    def change(events):
        data = events[-1]["data"]
        data["prepared"] = provider_adapter.prepare(
            data["request"],
            ProviderConfig.from_dict(data["prepared"]["config"]),
            output_contract=V1 if version == V2 else V2,
        )

    rechain(output, change)
    with pytest.raises(ValueError, match="wire mismatch"):
        audit_run(prepared_execution, output)
    with pytest.raises(ValueError):
        collect(prepared_execution, output, resume=True, offline_only=True)


def test_rehashed_execution_cannot_mix_schema_and_contract(prepared_execution, tmp_path):
    destination = tmp_path / "execution"
    shutil.copytree(prepared_execution, destination)
    plan = read(destination / "execution.json")
    if contract_version(plan) == V2:
        del plan["output_contract"]
    else:
        plan["output_contract"] = identity(V2)
    plan["execution_id"] = fingerprint({k: v for k, v in plan.items() if k != "execution_id"})
    write_json(destination / "execution.json", plan)
    with pytest.raises(ValueError, match="output contract"):
        verify_execution(destination)


@pytest.mark.parametrize(
    "shape", ["flat_fields", "input_object", "extra_history", "missing_action", "action_object"]
)
def test_observed_structural_failure_classes_remain_invalid(shape):
    answer = empty_decision()
    if shape == "flat_fields":
        answer = {**answer["state"], "action": answer["action"]}
    elif shape == "input_object":
        answer = request("answer_history")
    elif shape == "extra_history":
        answer["answer_history"] = []
    elif shape == "missing_action":
        del answer["action"]
    else:
        answer["action"] = {"action": answer["action"]}
    with pytest.raises(ValueError):
        parse_decision(canonical(answer))


def test_wrong_citation_is_retained_as_a_scoring_error():
    answer = empty_decision()
    answer["state"]["maximum_wind_mph"] = {
        "status": "known",
        "value": 85,
        "evidence": [{"record_id": "DELIVERY_FIXTURE_NOT_A_RECORD", "line": 1}],
    }
    answer["action"] = "monitor"
    assert parse_decision(canonical(answer)) == answer
