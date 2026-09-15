"""Analysis cannot turn rehearsal fallbacks or duplicated GPU time into evidence."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

EXEC = Path(__file__).resolve().parents[2] / "plans/v8_measurement_execution_20260913_01"
spec = importlib.util.spec_from_file_location(
    "joint_analysis", EXEC / "scripts/analyze_joint_results.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.fixture
def audit():
    return [
        json.loads((EXEC / "reports/joint_unlaunched_audit_01" / name).read_text())
        for name in ("VALIDATION.json", "CALLS.json", "TARGETS.json", "TABLES.json", "PAIRS.json")
    ]


def test_no_model_metrics_for_empty_capture(audit):
    with pytest.raises(ValueError, match="not model results"):
        module.summarize(*audit)
    report = module.summarize(*audit, allow_unlaunched=True)
    assert report["registered_calls"] == 384
    assert report["unique_opportunities"] == 48
    assert all(cell["metrics"] is None for cell in report["cells"])
    assert all(c["F_brier_single_minus_multi"] is None for c in report["contrasts"])


def test_failure_cannot_delete_a_joint_target_position(audit):
    audit[2].pop()
    with pytest.raises(ValueError, match="target positions"):
        module.summarize(*audit, allow_unlaunched=True)


def test_e_only_probability_is_rejected(audit):
    next(r for r in audit[2] if r["head"] == "e_only")["effective_probability"] = 0.3
    with pytest.raises(ValueError, match="E-only"):
        module.summarize(*audit, allow_unlaunched=True)


def test_independent_score_tampering_is_rejected(audit):
    audit[3][0]["E_correct"] = 17
    with pytest.raises(ValueError, match="score mismatch"):
        module.summarize(*audit, allow_unlaunched=True)


def test_batch_time_is_not_multiplied_by_call_count(audit):
    copied = copy.deepcopy(audit)
    for row in copied[1][:4]:
        row["batch_elapsed_us"] = 2_000_000
    report = module.summarize(*copied, allow_unlaunched=True)
    assert report["completed_physical_batches"] == 1
    assert report["completed_physical_batch_elapsed_seconds"] == 2
    assert report["scope_specific_GPU_time"] is None
    copied[1][1]["batch_elapsed_us"] = 3_000_000
    with pytest.raises(ValueError, match="conflicting elapsed"):
        module.summarize(*copied, allow_unlaunched=True)


def test_output_budget_is_reported_per_cell_and_not_equalized(audit):
    report = module.summarize(*audit, allow_unlaunched=True)
    assert {
        r["planned_output_token_budget"] for r in report["cells"] if r["scope"] == "single"
    } == {24 * 512}
    assert {r["planned_output_token_budget"] for r in report["cells"] if r["scope"] == "multi"} == {
        8 * 512
    }
