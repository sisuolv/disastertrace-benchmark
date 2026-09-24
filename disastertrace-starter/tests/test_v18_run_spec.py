import json
import subprocess
import sys

import pytest

from scripts.validate_v18_run_spec import validate


def spec():
    return {"schema": "disastertrace.v19.run_spec.v1", "run_id": "OFFLINE-SPEC-001",
            "scopes": ["CODE", "PROVIDER"], "permissions": {"CODE": True, "PROVIDER": True}}


def test_offline_spec_is_deterministic_and_external_free():
    result = validate(spec())
    assert result["valid"] is True and result["external_calls"] == 0
    assert len(result["spec_sha256"]) == 64


def test_spec_requires_explicit_scope_permission():
    bad = spec(); bad["permissions"]["PROVIDER"] = False
    with pytest.raises(ValueError, match="permission"):
        validate(bad)


def test_spec_rejects_credentials_and_protected_paths():
    bad = spec(); bad["api_key"] = "secret"
    with pytest.raises(ValueError, match="Sensitive"):
        validate(bad)
    bad = spec(); bad["readset"] = "/mnt/afs/data_real_v16/taf"
    with pytest.raises(ValueError, match="Raw/holdout"):
        validate(bad)
