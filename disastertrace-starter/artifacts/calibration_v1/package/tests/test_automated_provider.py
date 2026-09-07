from __future__ import annotations

import copy
import json
import threading
from dataclasses import FrozenInstanceError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import URLError

import pytest

from disastertrace.automated.common import canonical, fingerprint
from disastertrace.automated.dynamic import FIELDS, POLICY
from disastertrace.automated.provider import ProviderClient, ProviderConfig, ProviderError


@pytest.fixture
def config_dict():
    return {
        "model": "local-test-model",
        "base_url": "http://127.0.0.1:8000/v1",
        "key_env": None,
        "max_output_tokens": 128,
        "token_parameter": "max_tokens",
        "temperature": 0,
        "timeout": 5,
        "max_response_bytes": 65536,
    }


@pytest.fixture
def public_request():
    return {
        "protocol": "disastertrace_text_v1",
        "instruction": "Return the requested state and action as JSON.",
        "checkpoint_time": "2021-08-28T15:00:00+00:00",
        "required_fields": list(FIELDS),
        "policy": dict(POLICY),
        "evidence": [],
        "previous_state": None,
    }


def response_body(**updates):
    response = {
        "model": "local-test-model-snapshot",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "  invalid model JSON\n"},
                "finish_reason": "length",
            }
        ],
        "usage": {"prompt_tokens": 16, "completion_tokens": 4, "total_tokens": 20},
    }
    response.update(updates)
    return canonical(response).encode()


def test_prepare_is_offline_and_binds_all_decoding_parameters(
    config_dict, public_request, monkeypatch
):
    config_dict.update(base_url="https://example.invalid/v1", key_env="TEST_PROVIDER_KEY")
    monkeypatch.delenv("TEST_PROVIDER_KEY", raising=False)
    client = ProviderClient(ProviderConfig.from_dict(config_dict))
    prepared = client.prepare(public_request)
    assert prepared["endpoint"] == "https://example.invalid/v1/chat/completions"
    assert prepared["wire_payload_sha256"] == fingerprint(prepared["payload"])
    assert prepared["raw_request"] == canonical(prepared["payload"])
    assert json.loads(prepared["payload"]["messages"][1]["content"]) == public_request
    assert len(prepared["payload"]["messages"]) == 2
    changed = dict(config_dict, temperature=1)
    assert (
        ProviderClient(ProviderConfig.from_dict(changed)).prepare(public_request)["request_sha256"]
        != prepared["request_sha256"]
    )
    with pytest.raises(ProviderError, match="missing_credential"):
        client.complete(public_request)


def test_frozen_config(config_dict):
    config = ProviderConfig.from_dict(config_dict)
    with pytest.raises(FrozenInstanceError):
        config.model = "changed"


@pytest.mark.parametrize(
    "key,value",
    [
        ("base_url", "http://example.com/v1"),
        ("base_url", "https://user:SECRET@example.com/v1"),
        ("base_url", "https://example.com/v1?api_key=SECRET"),
        ("base_url", "https://example.com/v1#SECRET"),
        ("base_url", "https://example.com/v1?"),
        ("base_url", "http://127.0.0.1:99999/v1"),
        ("base_url", "http://127.0.0.1:8000/v1/chat/completions"),
        ("base_url", "http://127.0.0.1\\@example.com/v1"),
        ("base_url", "http://127.0.0.1/v1\n"),
        ("model", ""),
        ("model", "  model"),
        ("max_output_tokens", True),
        ("max_output_tokens", 0),
        ("token_parameter", "made_up"),
        ("temperature", float("nan")),
        ("temperature", True),
        ("temperature", 3),
        ("timeout", 0),
        ("timeout", float("inf")),
        ("max_response_bytes", -1),
        ("key_env", "SECRET=abc"),
    ],
)
def test_config_rejects_invalid_values(config_dict, key, value):
    config_dict[key] = value
    with pytest.raises(ValueError) as caught:
        ProviderConfig.from_dict(config_dict)
    assert "SECRET" not in str(caught.value)


@pytest.mark.parametrize("extra", ["api_key", "password", "unexpected"])
def test_unknown_config_fields_rejected_without_reflection(config_dict, extra):
    config_dict[extra] = "DO_NOT_EXPOSE"
    with pytest.raises(ValueError) as caught:
        ProviderConfig.from_dict(config_dict)
    assert "DO_NOT_EXPOSE" not in str(caught.value)


def test_optional_temperature_and_completion_token_parameter(config_dict, public_request):
    config_dict.update(temperature=None, token_parameter="max_completion_tokens")
    payload = ProviderClient(ProviderConfig.from_dict(config_dict)).prepare(public_request)[
        "payload"
    ]
    assert payload["max_completion_tokens"] == 128
    assert "max_tokens" not in payload and "temperature" not in payload


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "[::1]"])
def test_local_http_accepted(config_dict, host):
    config_dict["base_url"] = f"http://{host}:8080/v1"
    ProviderConfig.from_dict(config_dict)


def test_public_request_whitelist_and_fresh_messages(config_dict, public_request):
    client = ProviderClient(ProviderConfig.from_dict(config_dict))
    bad = dict(public_request, private_references={"answer": 105})
    with pytest.raises(ValueError):
        client.prepare(bad)
    prepared = client.prepare(public_request)
    prepared["payload"]["messages"].append({"role": "assistant", "content": "old"})
    assert len(client.prepare(public_request)["payload"]["messages"]) == 2
    evidence = {
        "delivery_index": 0,
        "record_id": "a",
        "issued_at": public_request["checkpoint_time"],
        "text": "1: report",
        "fields": {"answer": 105},
    }
    with pytest.raises(ValueError):
        client.prepare(dict(public_request, evidence=[evidence]))


def test_success_preserves_raw_text_and_complete_metadata(config_dict, public_request, monkeypatch):
    secret = "secret-token-for-test"
    monkeypatch.setenv("TEST_PROVIDER_KEY", secret)
    config_dict["key_env"] = "TEST_PROVIDER_KEY"
    calls = []

    def transport(url, body, headers, timeout, maximum):
        calls.append((url, body, copy.deepcopy(headers), timeout, maximum))
        return 200, response_body()

    client = ProviderClient(ProviderConfig.from_dict(config_dict), transport=transport)
    result = client.complete(public_request)
    assert len(calls) == 1 and calls[0][2]["Authorization"] == "Bearer " + secret
    assert result["raw_response"] == "  invalid model JSON\n"
    metadata = result["metadata"]
    assert metadata["raw_request"].encode() == calls[0][1]
    assert metadata["response_model"] == "local-test-model-snapshot"
    assert metadata["finish_reason"] == "length"
    assert metadata["usage"]["total_tokens"] == 20
    assert metadata["attempt_count"] == 1 and metadata["automatic_retry"] is False
    assert metadata["monetary_cap_enforced"] is False
    assert secret not in canonical(result)


@pytest.mark.parametrize(
    "status,code",
    [
        (401, "authentication_error"),
        (403, "authorization_error"),
        (429, "rate_limited"),
        (500, "http_error"),
        (302, "http_error"),
    ],
)
def test_http_errors_never_retry_or_reflect_body(config_dict, public_request, status, code):
    calls = []

    def transport(*args):
        calls.append(args)
        return status, b"Authorization: Bearer SECRET"

    with pytest.raises(ProviderError) as caught:
        ProviderClient(ProviderConfig.from_dict(config_dict), transport=transport).complete(
            public_request
        )
    assert len(calls) == 1 and caught.value.code == code
    assert caught.value.status == status
    assert caught.value.as_dict()["request_may_have_reached_provider"] is True
    assert "SECRET" not in str(caught.value) + canonical(caught.value.as_dict())


@pytest.mark.parametrize(
    "error,code",
    [
        (TimeoutError("SECRET"), "timeout"),
        (URLError(TimeoutError("SECRET")), "timeout"),
        (URLError("SECRET"), "transport_error"),
        (RuntimeError("SECRET"), "transport_error"),
    ],
)
def test_transport_errors_are_sanitized(config_dict, public_request, error, code):
    def transport(*args):
        raise error

    with pytest.raises(ProviderError) as caught:
        ProviderClient(ProviderConfig.from_dict(config_dict), transport=transport).complete(
            public_request
        )
    assert caught.value.code == code and "SECRET" not in str(caught.value)


@pytest.mark.parametrize(
    "body",
    [
        b"not json",
        b'{"model":"a","model":"b"}',
        b"\xff",
        b'{"model":"m","choices":[]}',
        response_body(usage={"prompt_tokens": True, "completion_tokens": 4, "total_tokens": 5}),
        response_body(usage={"prompt_tokens": 2, "completion_tokens": 4, "total_tokens": 7}),
        response_body(usage={"total_tokens": 5}),
        response_body(
            choices=[
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": None},
                    "finish_reason": "stop",
                }
            ]
        ),
    ],
)
def test_malformed_response_is_not_repaired(config_dict, public_request, body):
    client = ProviderClient(
        ProviderConfig.from_dict(config_dict), transport=lambda *args: (200, body)
    )
    with pytest.raises(ProviderError, match="invalid_response_schema"):
        client.complete(public_request)


def test_missing_usage_is_explicitly_unknown(config_dict, public_request):
    body = json.loads(response_body())
    del body["usage"]
    client = ProviderClient(
        ProviderConfig.from_dict(config_dict),
        transport=lambda *args: (200, canonical(body).encode()),
    )
    metadata = client.complete(public_request)["metadata"]
    assert metadata["usage"] is None and metadata["usage_available"] is False
    assert metadata["reported_output_token_cap_exceeded"] is None and metadata["cost"] is None


def test_response_byte_cap_and_secret_reflection(config_dict, public_request, monkeypatch):
    config_dict["max_response_bytes"] = 5
    client = ProviderClient(
        ProviderConfig.from_dict(config_dict), transport=lambda *args: (200, b"123456")
    )
    with pytest.raises(ProviderError, match="response_too_large"):
        client.complete(public_request)
    config_dict.update(max_response_bytes=65536, key_env="TEST_PROVIDER_KEY")
    monkeypatch.setenv("TEST_PROVIDER_KEY", "SECRET")
    client = ProviderClient(
        ProviderConfig.from_dict(config_dict),
        transport=lambda *args: (200, response_body(model="SECRET")),
    )
    with pytest.raises(ProviderError, match="credential_reflection") as caught:
        client.complete(public_request)
    assert "SECRET" not in str(caught.value)


def test_real_loopback_transport_and_no_redirect(config_dict, public_request):
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            received.append((self.path, self.rfile.read(int(self.headers["Content-Length"]))))
            if self.path.startswith("/redirect"):
                self.send_response(307)
                self.send_header("Location", "/v1/chat/completions")
                self.end_headers()
            else:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(response_body())

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        config_dict["base_url"] = base + "/v1"
        result = ProviderClient(ProviderConfig.from_dict(config_dict)).complete(public_request)
        assert result["metadata"]["http_status"] == 200
        assert received[0][0] == "/v1/chat/completions"
        config_dict["base_url"] = base + "/redirect"
        with pytest.raises(ProviderError) as caught:
            ProviderClient(ProviderConfig.from_dict(config_dict)).complete(public_request)
        assert caught.value.status == 307 and len(received) == 2
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
