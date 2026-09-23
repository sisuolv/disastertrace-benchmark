import json

import pytest

from disastertrace.multimodal_v1.runner import ContextLimit, run_trajectories


def parse(text):
    value = json.loads(text)
    if not isinstance(value.get("value"), bool):
        raise ValueError("expected bool")
    return value


def test_unknown_does_not_stop_other_trajectory_or_redispatch(tmp_path):
    calls = []

    def backend(request):
        calls.append(request["checkpoint"])
        if request["checkpoint"] == "a0":
            raise TimeoutError("response unknown")
        return '{"value":false}'

    plan = {
        "a": [{"checkpoint": "a0"}, {"checkpoint": "a1"}],
        "b": [{"checkpoint": "b0"}, {"checkpoint": "b1"}],
    }
    result = run_trajectories(tmp_path, plan, backend, parse, backend_id="fault_fixture")
    assert result["counts"] == {"unknown": 1, "unattempted": 1, "received_valid": 2}
    assert calls == ["a0", "b0", "b1"]
    assert run_trajectories(tmp_path, plan, backend, parse, backend_id="fault_fixture") == result
    assert calls == ["a0", "b0", "b1"]


def test_context_failure_is_pre_dispatch_and_local(tmp_path):
    class Backend:
        def prepare(self, request):
            if request["checkpoint"] == "a":
                raise ContextLimit("context exceeds declared cap")

        def __call__(self, request):
            return '{"value":true}'

    plan = {"a": [{"checkpoint": "a"}], "b": [{"checkpoint": "b"}]}
    result = run_trajectories(tmp_path, plan, Backend(), parse, backend_id="context_fixture")
    assert result["counts"] == {"failed_preflight": 1, "received_valid": 1}
    assert not (tmp_path / "a/0000/intent.json").exists()


def test_invalid_raw_and_wrong_valid_answers_stay_in_own_history(tmp_path):
    seen = []
    values = ["not json", '{"value":false}', '{"value":true}']

    def backend(request):
        seen.append(request["carrier"])
        return values[len(seen) - 1]

    plan = {"a": [{"checkpoint": str(i)} for i in range(3)]}
    result = run_trajectories(tmp_path, plan, backend, parse, backend_id="history_fixture")
    assert seen[0] is None
    assert seen[1] == {"raw": "not json", "invalid": True, "missing": False}
    assert seen[2] == {"raw": '{"value":false}', "invalid": False, "missing": False}
    assert result["counts"] == {"received_invalid": 1, "received_valid": 2}


def test_crash_after_raw_recovers_without_calling_model(tmp_path):
    calls = []

    def backend(request):
        calls.append(request)
        return '{"value":true}'

    def crash(path):
        raise SystemExit("injected crash after raw")

    plan = {"a": [{"checkpoint": "c0"}]}
    with pytest.raises(SystemExit):
        run_trajectories(
            tmp_path, plan, backend, parse, backend_id="crash_fixture", after_raw=crash
        )
    result = run_trajectories(tmp_path, plan, backend, parse, backend_id="crash_fixture")
    assert result["counts"] == {"received_valid": 1}
    assert len(calls) == 1


def test_resume_rejects_changed_plan_backend_or_result(tmp_path):
    plan = {"a": [{"checkpoint": "c0"}]}
    run_trajectories(tmp_path, plan, lambda r: '{"value":true}', parse, backend_id="x")
    for changed_plan, backend_id in [({"a": [{"checkpoint": "c1"}]}, "x"), (plan, "y")]:
        with pytest.raises(ValueError):
            run_trajectories(
                tmp_path, changed_plan, lambda r: "unused", parse, backend_id=backend_id
            )
    p = tmp_path / "a/0000/outcome.json"
    p.write_text('{"status":"received_valid","value":{"value":false}}')
    with pytest.raises(ValueError):
        run_trajectories(tmp_path, plan, lambda r: "unused", parse, backend_id="x")


def test_temporary_raw_is_not_a_returned_answer(tmp_path):
    plan = {"a": [{"checkpoint": "c0"}]}

    def crash(request):
        (tmp_path / "a/0000/.raw.tmp").write_text('{"value":true}')
        raise SystemExit("interrupted publish")

    with pytest.raises(SystemExit):
        run_trajectories(tmp_path, plan, crash, parse, backend_id="x")
    result = run_trajectories(
        tmp_path, plan, lambda r: pytest.fail("must not retry"), parse, backend_id="x"
    )
    assert result["counts"] == {"unknown": 1}


def test_unbound_raw_rejected_and_path_components_rejected(tmp_path):
    with pytest.raises(ValueError):
        run_trajectories(tmp_path, {"../a": [{}]}, lambda r: "{}", parse, backend_id="x")
    slot = tmp_path / "a/0000"
    slot.mkdir(parents=True)
    (slot / "raw.txt").write_text('{"value":true}')
    with pytest.raises(ValueError):
        run_trajectories(tmp_path, {"a": [{}]}, lambda r: "{}", parse, backend_id="x")
