"""A preserved failed observer must not hide or impersonate a later CPU audit."""

import importlib.util
from pathlib import Path

import pytest

from disastertrace.forecast_task.common import write


@pytest.fixture
def controller(monkeypatch):
    root = Path(__file__).resolve().parents[2] / "artifacts/autonomy_10h_v1"
    monkeypatch.syspath_prepend(str(root))
    spec = importlib.util.spec_from_file_location("review_continuation_test", root / "continue_reviews_v2.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def status(bundle, number, value):
    folder = bundle / f"finalization_qwen3_{number:02d}"
    write(folder / "FINAL_STATUS.json", value)
    return folder


def test_expected_initial_failure_waits_for_a_fresh_finalization(controller, tmp_path):
    status(tmp_path, 1, {"status": "failed", "error": controller.ALLOCATION_ERROR})
    assert controller.choose_final(tmp_path, "qwen3") is None
    second = status(tmp_path, 2, {"status": "passed"})
    assert controller.choose_final(tmp_path, "qwen3") == second


def test_original_success_remains_the_authoritative_finalization(controller, tmp_path):
    first = status(tmp_path, 1, {"status": "passed"})
    assert controller.choose_final(tmp_path, "qwen3") == first


def test_two_successes_cannot_be_selected_opportunistically(controller, tmp_path):
    status(tmp_path, 1, {"status": "passed"})
    status(tmp_path, 2, {"status": "passed"})
    with pytest.raises(ValueError, match="multiple successful"):
        controller.choose_final(tmp_path, "qwen3")


@pytest.mark.parametrize("number,error", [(1, "unexpected audit failure"), (2, "allocation error")])
def test_unexpected_failures_are_not_silently_ignored(controller, tmp_path, number, error):
    status(tmp_path, number, {"status": "failed", "error": error})
    with pytest.raises(ValueError, match="unexpected failed"):
        controller.choose_final(tmp_path, "qwen3")


def test_missing_final_status_stays_pending(controller, tmp_path):
    (tmp_path / "finalization_qwen3_01").mkdir()
    assert controller.choose_final(tmp_path, "qwen3") is None
