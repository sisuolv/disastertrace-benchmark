"""Different parser data models must retain native conditional semantics."""

from types import SimpleNamespace

from verify_native_taf import external_operator


def test_standalone_prob_is_not_a_new_prevailing_from_group():
    clause = SimpleNamespace(type="FROM", probability=SimpleNamespace(value=30))
    assert external_operator(clause) == "PROB30"
    clause.type = "TEMPO"
    assert external_operator(clause) == "PROB30 TEMPO"
    clause.probability = None
    assert external_operator(clause) == "TEMPO"
