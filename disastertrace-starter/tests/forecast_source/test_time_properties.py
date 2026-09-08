"""Generated month-end UTC cases compare both parsers to independently constructed times."""

from datetime import datetime, timedelta, timezone

from hypothesis import given, settings
from hypothesis import strategies as st
from test_parsers import advisory

from disastertrace.forecast_source.consensus import agree


@settings(max_examples=80, derandomize=True, deadline=None)
@given(
    year=st.integers(2018, 2026),
    month=st.integers(1, 12),
    day=st.integers(25, 28),
    hour=st.sampled_from([0, 3, 9, 15, 21]),
    issue_delay=st.integers(0, 6),
    forecast_lead=st.integers(9, 168),
)
def test_utc_rollovers_have_one_absolute_interpretation(
    year, month, day, hour, issue_delay, forecast_lead
):
    center = datetime(year, month, day, hour, tzinfo=timezone.utc)
    issued = center + timedelta(hours=issue_delay)
    valid = center + timedelta(hours=forecast_lead)
    body = advisory(
        issue=issued.strftime("%H%M UTC %a %b %d %Y").upper(),
        center=center.strftime("%d/%H%MZ"),
        valid=valid.strftime("%d/%H%MZ"),
    )
    result = agree(body)
    assert result["issued_at"] == issued.isoformat()
    assert result["center_at"] == center.isoformat()
    assert result["forecasts"][0]["valid_at"] == valid.isoformat()
    assert result["forecasts"][0]["lead_hours_from_center"] == forecast_lead
    assert result["available_at"] is None and result["initialization_at"] is None
