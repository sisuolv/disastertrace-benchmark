from datetime import datetime, timezone

from scripts.build_v18_dev_episodes import _conditional_window, _normalized_visibility


def test_taf_visibility_is_normalized_to_metres():
    interval = _normalized_visibility("05008KT P6SM FEW060")
    assert interval["lower"] == 9656.064
    assert interval["upper"] == "+inf"
    assert interval["lower_closed"] is False


def test_conditional_window_and_operator_tokens_are_preserved():
    issue = datetime(2025, 1, 1, tzinfo=timezone.utc)
    assert _conditional_window("TEMPO 0103/0104 4SM -SHSN", issue) == (
        datetime(2025, 1, 1, 3, tzinfo=timezone.utc),
        datetime(2025, 1, 1, 4, tzinfo=timezone.utc),
    )
    assert _conditional_window("PROB30 0500/0503 1/4SM -SN", issue) == (
        datetime(2025, 1, 5, tzinfo=timezone.utc),
        datetime(2025, 1, 5, 3, tzinfo=timezone.utc),
    )
