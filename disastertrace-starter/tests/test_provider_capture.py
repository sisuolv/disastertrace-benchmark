import base64
import copy
import hashlib
import json
import multiprocessing
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from disastertrace.automated.collection_audit import validate_completion
from disastertrace.automated.common import canonical, fingerprint
from disastertrace.automated.dynamic import FIELDS, POLICY
from disastertrace.automated.provider import ProviderClient, ProviderConfig, ProviderError
from disastertrace.automated.provider_capture import (
    parse_capture,
    send_prepared,
    validate_capture,
    validate_prepared,
)


def prepared(*, url="http://127.0.0.1:9", cap=4096, key_env=None, timeout=2):
    config = ProviderConfig(
        model="offline-test",
        base_url=url,
        key_env=key_env,
        max_output_tokens=128,
        token_parameter="max_tokens",
        temperature=None,
        timeout=timeout,
        max_response_bytes=cap,
        reasoning_effort="high",
        thinking_type="enabled",
    )
    public = {
        "protocol": "disastertrace_text_v1",
        "instruction": "Return the public state.",
        "checkpoint_time": "2026-01-01T00:00:00Z",
        "required_fields": list(FIELDS),
        "policy": POLICY,
        "evidence": [],
        "previous_state": None,
    }
    return ProviderClient(config).prepare(public)


def envelope(**updates):
    value = {
        "model": "offline-test",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "{}",
                    "reasoning_content": "not the answer",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
    }
    value.update(updates)
    return canonical(value).encode()


def injected(status, body):
    return lambda *_args: (status, body)


def test_exact_saved_bytes_no_prepare_or_environment_read(monkeypatch):
    request = prepared(key_env="NEVER_READ_CAPTURE_KEY")
    sent = []

    def transport(url, body, headers, timeout, limit):
        sent.append((url, body, headers, timeout, limit))
        return 200, envelope()

    monkeypatch.setattr(ProviderClient, "prepare", lambda *_: pytest.fail("reprepared"))
    monkeypatch.setenv("NEVER_READ_CAPTURE_KEY", "must-not-read")
    capture = send_prepared(request, transport=transport, credential="fixture-key")
    assert len(sent) == 1
    assert sent[0][1] == request["raw_request"].encode()
    assert sent[0][2]["Authorization"] == "Bearer fixture-key"
    assert capture["origin"] == "injected_transport_unverified"
    assert capture["total_deadline_enforced"] is False
    assert capture["automatic_retry"] is False
    assert validate_capture(capture, request) == envelope()
    completion = parse_capture(capture, request)
    assert completion["raw_response"] == "{}"
    assert completion["metadata"]["usage"]["total_tokens"] == 5
    validate_completion(
        completion["raw_response"],
        completion["metadata"],
        request,
        ProviderConfig.from_dict(request["config"]),
    )


@pytest.mark.parametrize(
    "field", ["endpoint", "raw_request", "request_sha256", "wire_payload_sha256", "config_sha256"]
)
def test_corrupted_preparation_cannot_send(field):
    request = prepared()
    request[field] += "changed"
    with pytest.raises(ValueError, match="prepared"):
        send_prepared(request, transport=lambda *_: pytest.fail("sent"))


def test_rehashed_invalid_payload_still_rejected():
    request = prepared()
    request["payload"]["stream"] = True
    request["raw_request"] = canonical(request["payload"])
    request["wire_payload_sha256"] = fingerprint(request["payload"])
    request["request_sha256"] = fingerprint(
        {key: request[key] for key in ("endpoint", "config", "payload")}
    )
    with pytest.raises(ValueError, match="prepared"):
        validate_prepared(request)


@pytest.mark.parametrize(
    "credential,error",
    [
        (None, "missing_credential"),
        ("", "missing_credential"),
        ("line\nbreak", "invalid_credential"),
    ],
)
def test_credential_failure_no_send_or_environment_fallback(monkeypatch, credential, error):
    monkeypatch.setenv("NEVER_READ_CAPTURE_KEY", "present-but-not-authorized")
    request = prepared(key_env="NEVER_READ_CAPTURE_KEY")
    capture = send_prepared(
        request, credential=credential, transport=lambda *_: pytest.fail("sent")
    )
    assert capture["error_code"] == error
    assert capture["request_may_have_reached_provider"] is False
    assert validate_capture(capture, request) is None


@pytest.mark.parametrize(
    "status,body",
    [
        (400, b'{"error":"bad request"}'),
        (429, b"slow down"),
        (503, b"unavailable"),
        (200, b"\xff\x00invalid UTF8"),
        (200, b"not JSON"),
        (200, envelope(usage={"prompt_tokens": -1})),
    ],
)
def test_error_bodies_preserved_before_parsing(status, body):
    request = prepared()
    capture = send_prepared(request, transport=injected(status, body))
    assert capture["capture_kind"] == "complete"
    assert validate_capture(capture, request) == body
    assert capture["body_sha256"] == hashlib.sha256(body).hexdigest()
    with pytest.raises(ProviderError):
        parse_capture(capture, request)


def test_missing_usage_and_empty_length_content_are_preserved():
    value = json.loads(envelope(usage=None))
    value["choices"][0]["message"]["content"] = ""
    value["choices"][0]["finish_reason"] = "length"
    request = prepared()
    capture = send_prepared(request, transport=injected(200, canonical(value).encode()))
    result = parse_capture(capture, request)
    assert result["raw_response"] == ""
    assert result["metadata"]["finish_reason"] == "length"
    assert result["metadata"]["usage_available"] is False


def test_oversize_bounded_prefix_is_not_complete():
    request = prepared(cap=8)
    capture = send_prepared(request, transport=injected(200, b"0123456789abcdef"))
    assert capture["capture_kind"] == "prefix"
    assert capture["truncated"] is True
    assert capture["error_code"] == "response_too_large"
    assert validate_capture(capture, request) == b"01234567"
    with pytest.raises(ProviderError, match="response_too_large"):
        parse_capture(capture, request)


@pytest.mark.parametrize(
    "body",
    [
        b"\xfffixture-secret",
        b'{"error":"fixture-secret"}',
        b'{"error":"\\u0066ixture-secret"}',
        b'{"error":"\\\\u0066ixture-secret"}',
    ],
)
def test_reflections_withheld_even_invalid_utf8_or_escaped(body):
    request = prepared()
    capture = send_prepared(request, transport=injected(500, body), credential="fixture-secret")
    assert capture["capture_kind"] == "withheld_credential"
    assert capture["error_code"] == "credential_reflection"
    assert capture["raw_body_b64"] is None
    assert capture["body_sha256"] is None
    assert "fixture-secret" not in canonical(capture)
    assert validate_capture(capture, request) is None


def test_transport_exception_sanitized_without_retry():
    attempts = []

    def broken(*_):
        attempts.append(1)
        raise RuntimeError("fixture-secret")

    request = prepared()
    capture = send_prepared(request, transport=broken, credential="fixture-secret")
    assert attempts == [1]
    assert capture["error_code"] == "transport_error"
    assert capture["request_may_have_reached_provider"] is True
    assert "fixture-secret" not in canonical(capture)


def test_capture_mutation_rejected():
    request = prepared()
    capture = send_prepared(request, transport=injected(200, envelope()))
    changed = copy.deepcopy(capture)
    changed["raw_body_b64"] = base64.b64encode(b"changed").decode()
    with pytest.raises(ValueError, match="capture"):
        validate_capture(changed, request)
    changed = copy.deepcopy(capture)
    changed["origin"] = "trusted-provider"
    with pytest.raises(ValueError, match="capture"):
        validate_capture(changed, request)


@pytest.mark.parametrize(
    "field,value",
    [
        ("transport_terminated", False),
        ("request_may_have_reached_provider", False),
        ("truncated", True),
        ("elapsed_seconds", float("nan")),
        ("http_status", True),
        ("captured_bytes", True),
        ("automatic_retry", True),
    ],
)
def test_inconsistent_complete_capture_rejected(field, value):
    request = prepared()
    capture = send_prepared(request, transport=injected(200, envelope()))
    capture[field] = value
    with pytest.raises(ValueError, match="capture"):
        validate_capture(capture, request)


@contextmanager
def server(mode, *, body=b"local body", status=200):
    received = []
    closed = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            received.append(self.rfile.read(int(self.headers["Content-Length"])))
            try:
                if mode == "first":
                    time.sleep(1)
                self.send_response(status)
                if mode == "redirect":
                    self.send_header("Location", "/redirect-target")
                self.send_header("Content-Length", str(len(body) + (10 if mode == "short" else 0)))
                self.end_headers()
                if mode == "drip":
                    for byte in body:
                        self.wfile.write(bytes([byte]))
                        self.wfile.flush()
                        time.sleep(0.05)
                else:
                    self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                closed.set()

        def log_message(self, *_args):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=httpd.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}", received, closed
    finally:
        httpd.shutdown()
        worker.join()
        httpd.server_close()


@pytest.mark.parametrize("status", [200, 400, 503])
def test_real_loopback_captures_error_body_and_exact_bytes(status, monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("NO_PROXY", "")
    with server("normal", status=status) as (url, received, _):
        request = prepared(url=url)
        capture = send_prepared(request, total_deadline=3)
    assert received == [request["raw_request"].encode()]
    assert capture["origin"] == "urllib_http"
    assert capture["total_deadline_enforced"] is True
    assert capture["transport_terminated"] is True
    assert capture["http_status"] == status
    assert validate_capture(capture, request) == b"local body"


def test_real_redirect_not_followed():
    with server("redirect", status=307) as (url, received, _):
        request = prepared(url=url)
        capture = send_prepared(request, total_deadline=3)
    assert len(received) == 1
    assert capture["http_status"] == 307
    assert validate_capture(capture, request) == b"local body"


def test_real_premature_eof_is_incomplete_prefix():
    with server("short") as (url, _, _):
        request = prepared(url=url)
        capture = send_prepared(request, total_deadline=3)
    assert capture["capture_kind"] == "prefix"
    assert capture["error_code"] == "transport_error"
    assert validate_capture(capture, request) == b"local body"


def test_real_socket_timeout_is_separate_from_total_deadline():
    with server("first") as (url, _, _):
        request = prepared(url=url, timeout=0.1)
        capture = send_prepared(request, total_deadline=3)
    assert capture["error_code"] == "timeout"
    assert capture["transport_terminated"] is True
    assert validate_capture(capture, request) is None


def test_real_chunk_boundary_reflection_withheld():
    body = b"a" * 16380 + b"fixture-secret" + b"z"
    with server("normal", body=body) as (url, _, _):
        request = prepared(url=url, cap=32768)
        capture = send_prepared(request, total_deadline=3, credential="fixture-secret")
    assert capture["capture_kind"] == "withheld_credential"
    assert validate_capture(capture, request) is None


def test_real_body_cap_retains_only_bounded_prefix():
    with server("normal", body=b"a" * 100) as (url, _, _):
        request = prepared(url=url, cap=8)
        capture = send_prepared(request, total_deadline=3)
    assert capture["error_code"] == "response_too_large"
    assert capture["capture_kind"] == "prefix"
    assert validate_capture(capture, request) == b"a" * 8


@pytest.mark.parametrize("mode", ["first", "drip"])
def test_total_deadline_terminates_process_and_keeps_received_prefix(mode):
    prior = {child.pid for child in multiprocessing.active_children()}
    with server(mode, body=b"x" * 100) as (url, received, _):
        request = prepared(url=url, timeout=2)
        started = time.monotonic()
        capture = send_prepared(request, total_deadline=0.5)
        elapsed = time.monotonic() - started
        assert elapsed < 1.5
        assert len(received) == 1
        assert capture["error_code"] == "total_deadline_exceeded"
        assert capture["transport_terminated"] is True
        assert capture["request_may_have_reached_provider"] is True
        if mode == "drip":
            assert capture["capture_kind"] == "prefix"
            assert 0 < len(validate_capture(capture, request)) < 100
    assert {child.pid for child in multiprocessing.active_children()} == prior
