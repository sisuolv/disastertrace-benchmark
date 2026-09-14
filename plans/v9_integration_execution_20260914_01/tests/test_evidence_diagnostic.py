"""Strict diagnostic denominator and decomposition contracts."""
import importlib.util
import json
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / 'scripts/evidence_diagnostic.py'
spec = importlib.util.spec_from_file_location('v9_evidence', PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.mark.parametrize('values,truth', [(['true', 'unknown'], 'true'),
    (['false', 'unknown'], 'unknown'), (['false', 'false'], 'false'),
    (['true', 'conflict'], 'conflict'), (['unknown', 'unknown'], 'unknown')])
def test_existential_requires_complete_refutation_and_preserves_conflict(values, truth):
    assert module.aggregate(values) == truth


@pytest.mark.parametrize('raw,reasoning', [
    ('{"fact_truth":false}', 'direct'), ('{"fact_truth":"true","extra":1}', 'direct'),
    ('{"fact_truth":"false","fact_truth":"true"}', 'direct'),
    ('{"slots":{"a":"false"},"fact_truth":"false"}', 'slotwise'),
    ('{"slots":{"a":"false","b":"unknown","x":"true"},"fact_truth":"true"}', 'slotwise'),
    ('{"slots":{"a":"false","a":"true","b":"unknown"},"fact_truth":"true"}', 'slotwise'),
])
def test_invalid_or_incomplete_outputs_are_not_partial_success(raw, reasoning):
    with pytest.raises(ValueError):
        module.parse(raw, ['a', 'b'], reasoning)


def test_reported_aggregate_and_program_aggregate_remain_separate_diagnostics():
    raw = json.dumps({'slots': {'a': 'false', 'b': 'unknown'}, 'fact_truth': 'false'})
    answer = module.parse(raw, ['a', 'b'], 'slotwise')
    assert answer['fact_truth'] == 'false'
    assert module.aggregate(answer['slots'].values()) == 'unknown'
