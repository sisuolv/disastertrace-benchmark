"""P2-only prepared-byte capture; the legacy request validator remains strict."""

from disastertrace.automated import provider_capture as transport_core
from disastertrace.automated.common import canonical, strict_json
from disastertrace.automated.provider import ProviderConfig

from .provider_adapter import prepare

SCHEMA_VERSION = "controlled_provider_capture_v1"


def validate_prepared(prepared: dict) -> ProviderConfig:
    try:
        config = ProviderConfig.from_dict(prepared["config"])
        public = strict_json(prepared["payload"]["messages"][1]["content"])
        if canonical(prepared) != canonical(prepare(public, config)):
            raise ValueError()
        return config
    except (ValueError, TypeError, KeyError, IndexError, AttributeError, RecursionError):
        raise ValueError("invalid prepared controlled provider request") from None


def send_prepared(prepared, *, total_deadline=180, transport=None, credential=None):
    config = validate_prepared(prepared)
    return transport_core._send_validated(
        prepared,
        config,
        total_deadline=total_deadline,
        transport=transport,
        credential=credential,
        schema_version=SCHEMA_VERSION,
    )


def validate_capture(capture, prepared):
    config = validate_prepared(prepared)
    return transport_core._validate_captured(
        capture,
        prepared,
        config,
        schema_version=SCHEMA_VERSION,
    )


def parse_capture(capture, prepared):
    body = validate_capture(capture, prepared)
    completion = transport_core._parse_captured(capture, prepared, body)
    completion["metadata"]["schema_version"] = "controlled_provider_completion_v1"
    return completion
