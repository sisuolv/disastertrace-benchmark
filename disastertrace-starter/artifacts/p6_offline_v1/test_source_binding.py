"""Pure-program sequence tests suggested by the supplemental fourth plan."""

from copy import deepcopy
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
from hypothesis import given, seed, settings
from hypothesis import strategies as st

from disastertrace.controlled import compiler, public_oracle, renderer
from disastertrace.post_p5.policies import solve

spec = spec_from_file_location(
    "p6_probe_fixtures", Path(__file__).with_name("source_binding_probes.py")
)
probes = module_from_spec(spec)
spec.loader.exec_module(probes)


@seed(20260908)
@settings(max_examples=100, deadline=None, database=None)
@given(st.lists(st.sampled_from(probes.OPERATIONS), min_size=1, max_size=20))
def test_revision_sequences_match_literal_expectations(operations):
    ep, expected, certificates = probes.build(operations)
    request = renderer.render_request(ep, "c2", method="snapshot")
    assert compiler.reference_at(ep, "c2") == expected
    assert public_oracle.answer(request) == expected
    assert solve(request) == expected
    assert len(certificates) == len(operations)
    assert "private_legality_certificate" not in request
    assert "private_expected" not in request


@pytest.mark.parametrize("kind", ["fork", "cross_key", "child_first"])
def test_private_and_public_oracles_reject_illegal_graphs(kind):
    ep, _, _ = probes.build(["same", "change"])
    request = renderer.render_request(ep, "c2", method="snapshot")
    if kind == "child_first":
        ep["deliveries"][0], ep["deliveries"][1] = ep["deliveries"][1], ep["deliveries"][0]
        request["evidence"][0], request["evidence"][1] = (
            request["evidence"][1],
            request["evidence"][0],
        )
    else:
        from disastertrace.automated.common import canonical, strict_json

        parent = ep["records"][0]["assertions"][0 if kind == "fork" else 1]["revision_id"]
        ep["records"][2]["assertions"][0]["supersedes"] = parent
        record = deepcopy(request["evidence"][2])
        header, assertion = record["text"].split("\n")
        assertion = strict_json(assertion.split("ASSERT ", 1)[1])
        assertion["supersedes"] = parent
        record["text"] = header + "\n2: ASSERT " + canonical(assertion)
        request["evidence"][2] = record
    with pytest.raises(ValueError):
        compiler.reference_at(ep, "c2")
    with pytest.raises(ValueError):
        public_oracle.answer(request)
