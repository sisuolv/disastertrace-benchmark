from scripts.run_v18_controlled_api import parse_output


def test_api_output_requires_typed_visibility_state():
    valid = '{"risk_probability":0.4,"target_state":{"visibility_m":4000,"confidence":"medium"},"next_action":"WAIT"}'
    parsed, status = parse_output(valid)
    assert status == "valid"
    assert parsed["target_state"]["visibility_m"] == 4000

    for state in (
        '{"visibility_m":"4000","confidence":"medium"}',
        '{"visibility_m":4000}',
        '{"visibility_m":-1,"confidence":"medium"}',
        '{"visibility_m":4000,"confidence":"certain"}',
    ):
        parsed, status = parse_output(
            '{"risk_probability":0.4,"target_state":' + state + ',"next_action":"WAIT"}'
        )
        assert parsed is None and status == "state_or_action"
