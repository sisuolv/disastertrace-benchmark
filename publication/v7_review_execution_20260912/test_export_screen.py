"""Publication scanning must reject credential shapes without rejecting risk IDs."""

import pytest
from export_snapshot import screen


def test_risk_strategy_identity_is_not_an_api_key():
    screen("report.json", b'{"strategy": "risk-global_budget-session_shared-base_bound_override"}')


@pytest.mark.parametrize("payload", [
    ("sk-" + "A" * 48).encode(),
    ("api_key: " + "B" * 36).encode(),
    b"https://example.test/data?Sign" + b"ature=example",
    b"-----BEGIN " + b"OPENSSH PRIVATE KEY-----",
], ids=["prefixed_key", "named_key", "signed_url", "private_key_header"])
def test_credential_shapes_stay_rejected(payload):
    with pytest.raises(ValueError, match="Potential sensitive"):
        screen("fixture.txt", payload)
