"""Strict P2-only wire preparation, shared by diagnostics and captured collection."""

from dataclasses import asdict

from disastertrace.automated.common import canonical, fingerprint
from disastertrace.automated.provider import ProviderConfig

from .output_contract import V1, identity, system_message
from .public_oracle import parse_evidence
from .renderer import INSTRUCTION


def validate_public_request(request: dict) -> None:
    parse_evidence(request)
    if request["instruction"] != INSTRUCTION:
        raise ValueError("controlled public instruction changed")


def prepare(request: dict, config: ProviderConfig, *, output_contract: str = V1) -> dict:
    if not isinstance(config, ProviderConfig):
        raise ValueError("validated provider configuration required")
    validate_public_request(request)
    payload = {
        "model": config.model,
        "messages": [
            {
                "role": "system",
                "content": system_message(output_contract),
            },
            {"role": "user", "content": canonical(request)},
        ],
        "n": 1,
        "stream": False,
        config.token_parameter: config.max_output_tokens,
    }
    if config.temperature is not None:
        payload["temperature"] = config.temperature
    if config.reasoning_effort is not None:
        payload["reasoning_effort"] = config.reasoning_effort
    if config.thinking_type is not None:
        payload["thinking"] = {"type": config.thinking_type}
    configuration = asdict(config)
    endpoint = config.base_url.rstrip("/") + "/chat/completions"
    # Legacy preparations retain their exact envelope and hashes.
    binding = {} if output_contract == V1 else {"output_contract": identity(output_contract)}
    return {
        **binding,
        "endpoint": endpoint,
        "config": configuration,
        "payload": payload,
        "raw_request": canonical(payload),
        "config_sha256": fingerprint(configuration),
        "wire_payload_sha256": fingerprint(payload),
        "request_sha256": fingerprint(
            {"endpoint": endpoint, "config": configuration, "payload": payload, **binding}
        ),
    }
