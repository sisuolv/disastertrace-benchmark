"""A second checkpoint keeps the common task, while resources and dispatch remain separate."""

import shutil
from pathlib import Path

import pytest

from disastertrace.forecast_live import adapter as native_adapter
from disastertrace.forecast_model import adapter, package
from disastertrace.forecast_task.common import canonical, fingerprint, read


def test_common_sampling_schema_and_system_remain_identical_to_native_profile():
    differences = {k for k in adapter.SETTINGS if adapter.SETTINGS[k] != native_adapter.SETTINGS[k]}
    assert differences == {"model_id", "structured_engine_options"}
    assert adapter.guide() == native_adapter.guide()
    assert adapter.ENGINE_OPTIONS["reasoning_parser"] == "deepseek_r1"


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_model_scores_read", True),
        ("planned_answers", 1),
        ("model_id", "Qwen/Qwen3-8B"),
        ("max_phase_seconds", 18000),
        ("generation_authorized_by_this_document", True),
    ],
)
def test_rehashed_registration_cannot_change_predeclared_task_budget(tmp_path, field, value):
    project = Path(__file__).resolve().parents[2]
    original = project / "artifacts/p9_forecast_model_v1"
    shutil.copyfile(
        original / "DESIGN_BEFORE_NATIVE_RESULTS.md", tmp_path / "DESIGN_BEFORE_NATIVE_RESULTS.md"
    )
    record = read(original / "PREREGISTRATION.json")
    record[field] = value
    record["design_id"] = fingerprint({k: v for k, v in record.items() if k != "design_id"})
    (tmp_path / "PREREGISTRATION.json").write_text(canonical(record))
    with pytest.raises(ValueError, match="preregistration"):
        package.validate_design(tmp_path, project / "artifacts/p7_forecast_task_v1/execution_v1")
