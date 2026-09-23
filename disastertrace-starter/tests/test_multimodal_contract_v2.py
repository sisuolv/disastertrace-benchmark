import json
from copy import deepcopy

import pytest

from disastertrace.multimodal_contract_v2 import explicit_contract, output_schema
from disastertrace.multimodal_v1.types import ModelCommit


def test_only_output_contract_changes_and_schema_does_not_encode_answers():
    request = {
        "output_contract": {"root": "old", "logic": "watched AND forecast_inside"},
        "queries": [{"site_id": "unseen-id"}],
        "evidence": [{"original": "opaque"}],
        "target": {"valid_at": "2024-09-10T18:00:00+00:00"},
    }
    before = deepcopy(request)
    new = explicit_contract(request)
    assert request == before
    assert {k: v for k, v in new.items() if k != "output_contract"} == {
        k: v for k, v in request.items() if k != "output_contract"
    }
    assert new["output_contract"]["logic"] == request["output_contract"]["logic"]
    assert "unseen-id" not in json.dumps(new["output_contract"])
    assert "2024-09-10" not in json.dumps(new["output_contract"])


@pytest.mark.parametrize("relation", ["inside", "outside", "boundary_ambiguous", "unknown"])
@pytest.mark.parametrize("watched", [True, False, None])
@pytest.mark.parametrize("required", [True, False, None])
def test_schema_and_existing_parser_accept_same_structure_without_encoding_logic(
    relation, watched, required
):
    jsonschema = pytest.importorskip("jsonschema")
    row = {
        "relation": relation,
        "watched": watched,
        "inspection_required": required,
        "map_source": None,
        "map_locator": None,
        "rule_source": None,
        "rule_locator": None,
    }
    value = {"state": {"any-revealed-site": row}}
    jsonschema.validate(value, output_schema())
    assert ModelCommit.parse(json.dumps(value)).state == value["state"]


@pytest.mark.parametrize(
    "value",
    [{"state": []}, {"state": [{"site_id": "A"}]}, {"state": None}, {"state": {}, "extra": 1}],
)
def test_schema_and_parser_reject_observed_container_defects(value):
    jsonschema = pytest.importorskip("jsonschema")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(value, output_schema())
    with pytest.raises(ValueError):
        ModelCommit.parse(json.dumps(value))
