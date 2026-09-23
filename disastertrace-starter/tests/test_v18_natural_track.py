import pytest

from disastertrace.monitoring_v1.natural_track_v18 import NaturalAction, NaturalKernel, NaturalSource


def kernel():
    return NaturalKernel(
        [NaturalSource("q1", 10, {"visibility_m": 4000}), NaturalSource("q2", 30, {"visibility_m": 9000})],
        start=0,
        deadline=60,
    )


def test_retrieve_separates_unavailable_from_available_content():
    env = kernel()
    assert env.step(NaturalAction("RETRIEVE", 0, query_id="q1"))["status"] == "unavailable"
    env.step(NaturalAction("WAIT", 0, wake_at=10))
    result = env.step(NaturalAction("RETRIEVE", 10, query_id="q1"))
    assert result["status"] == "available"
    assert env.public_state()["read_query_ids"] == ["q1"]


def test_stop_is_terminal_and_does_not_read_outcome():
    env = kernel()
    result = env.step(NaturalAction("STOP", 0))
    assert result["status"] == "stopped"
    assert "outcome" not in result
    with pytest.raises(ValueError, match="after STOP"):
        env.step(NaturalAction("WAIT", 0, wake_at=1))


def test_action_contract_rejects_unknown_query_and_invalid_wait():
    with pytest.raises(ValueError, match="future wake"):
        NaturalAction("WAIT", 3, wake_at=3)
    with pytest.raises(ValueError, match="query_id"):
        NaturalAction("RETRIEVE", 0)
    with pytest.raises(ValueError, match="Unknown query"):
        kernel().step(NaturalAction("RETRIEVE", 0, query_id="q3"))


def test_action_contract_rejects_fields_belonging_to_another_action():
    with pytest.raises(ValueError, match="Invalid natural action"):
        NaturalAction([], 0)
    with pytest.raises(ValueError, match="probability"):
        NaturalAction("STOP", 0, probability=0.4)
    with pytest.raises(ValueError, match="wake_at"):
        NaturalAction("RETRIEVE", 0, query_id="q1", wake_at=4)
    with pytest.raises(ValueError, match="query_id"):
        NaturalAction("WAIT", 0, wake_at=4, query_id="q1")


def test_wait_to_or_past_deadline_expires_the_kernel():
    env = kernel()
    result = env.step(NaturalAction("WAIT", 0, wake_at=100))
    assert result["status"] == "expired"
    assert env.public_state()["terminal"] is True
    with pytest.raises(ValueError, match="terminal"):
        env.step(NaturalAction("WAIT", 60, wake_at=61))
