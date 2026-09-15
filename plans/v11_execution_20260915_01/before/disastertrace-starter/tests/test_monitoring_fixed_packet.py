import pytest

from disastertrace.monitoring_v1.fixed_packet import parse


@pytest.mark.parametrize("raw", [
    '{"fact_truth":"false","probability":0.1,"probability":0.9}',
    '{"fact_truth":false,"probability":0.1}',
    '{"fact_truth":"false","probability":true}',
    '{"fact_truth":"false","probability":NaN}',
    '{"fact_truth":"false","probability":1.1}',
])
def test_invalid_joint_response_is_not_silently_repaired(raw):
    with pytest.raises(ValueError):
        parse(raw, ["a", "b"], ["a"], "direct")


def test_wrong_aggregate_and_unread_claim_remain_separate_model_errors():
    answer = parse('{"slots":{"a":"true","b":"false"},"fact_truth":"false","probability":0.2}',
                   ["a", "b"], ["a"], "slotwise")
    assert answer["fact_truth"] == "false"
    assert answer["composed_aggregate"] == "true"
    assert answer["unread_slot_claims"] == ["b"]
