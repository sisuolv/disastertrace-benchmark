import copy

import pytest

from disastertrace.automated import provider_capture as nhc_capture
from disastertrace.automated.common import canonical, strict_json
from disastertrace.automated.provider import ProviderClient, ProviderConfig
from disastertrace.controlled import generator, provider_adapter, public_oracle, renderer
from disastertrace.controlled import provider_capture as p2_capture


def config():
    return ProviderConfig(
        model="fixture",
        base_url="http://127.0.0.1:9",
        key_env=None,
        max_output_tokens=8192,
        token_parameter="max_tokens",
        temperature=None,
        timeout=180,
        max_response_bytes=1048576,
    )


def prepared():
    request = renderer.render_request(generator.micro_episodes()[0], "c1", method="snapshot")
    return provider_adapter.prepare(request, config())


def responder(endpoint, body, headers, timeout, maximum):
    wire = strict_json(body.decode())
    request = strict_json(wire["messages"][1]["content"])
    return 200, canonical(
        {
            "model": wire["model"],
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": canonical(public_oracle.answer(request)),
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": 100, "total_tokens": 200},
        }
    ).encode()


def test_exact_bytes_and_cross_protocol_rejection_before_dispatch():
    from pathlib import Path

    from disastertrace.automated.common import read_jsonl
    from disastertrace.automated.dynamic import render_request

    calls = []
    p2 = prepared()

    def transport(*args):
        calls.append(args[1])
        return responder(*args)

    capture = p2_capture.send_prepared(p2, transport=transport)
    assert calls == [p2["raw_request"].encode()]
    assert capture["schema_version"] == "controlled_provider_capture_v1"
    assert p2_capture.parse_capture(capture, p2)["metadata"]["usage"]["total_tokens"] == 200
    with pytest.raises(ValueError):
        nhc_capture.send_prepared(p2, transport=transport)
    root = Path(__file__).resolve().parents[1]
    episode = read_jsonl(root / "work/build-deepseek-v1/episodes/dynamic_episodes.jsonl")[0]
    nhc = ProviderClient(config()).prepare(render_request(episode, "c0", None))
    with pytest.raises(ValueError):
        p2_capture.send_prepared(nhc, transport=transport)
    assert len(calls) == 1
    with pytest.raises(ValueError):
        nhc_capture.parse_capture(capture, nhc)


@pytest.mark.parametrize("field", ["raw_request", "payload", "config", "endpoint"])
def test_changed_preparation_never_sends(field):
    changed = copy.deepcopy(prepared())
    changed[field] = "tampered"
    with pytest.raises(ValueError):
        p2_capture.send_prepared(changed, transport=lambda *_: pytest.fail("unexpected send"))


def test_p2_capture_filters_reflected_credentials_and_keeps_http_error_bytes():
    request = prepared()
    secret = "fixture-credential-only"
    result = p2_capture.send_prepared(
        request,
        credential=secret,
        transport=lambda *_: (401, canonical({"error": secret}).encode()),
    )
    assert result["capture_kind"] == "withheld_credential"
    assert secret not in canonical(result)
    error = p2_capture.send_prepared(
        request, transport=lambda *_: (503, b"temporarily unavailable")
    )
    assert p2_capture.validate_capture(error, request) == b"temporarily unavailable"
    assert error["error_code"] == "http_error"


def test_rehashed_public_gold_and_other_method_carrier_are_rejected():
    request = renderer.render_request(generator.micro_episodes()[0], "c1", method="snapshot")
    for field in ("gold", "future_deliveries", "previous_state"):
        changed = {**request, field: {"private": "SENTINEL"}}
        with pytest.raises(ValueError):
            provider_adapter.prepare(changed, config())
