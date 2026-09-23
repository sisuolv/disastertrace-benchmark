import copy
import importlib.util
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[3] / "publication/autonomy_review_20260909/copy_reconstruction_receipts_v2.py"
spec = importlib.util.spec_from_file_location("publication_receipt_copy", SOURCE)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


def receipt():
    return {"status": "passed", "cli_exits": [0, 0, 0], "execution_id": "fixture-execution",
            "package_id": "fixture-package", "source_files": {"report.json": "fixture-hash"},
            "model_generations": 0, "network_blocked": True,
            "original_project_and_weights_blocked": True, "torch_and_vllm_loaded": False,
            "unexpected_blocked_attempts": {"forbidden_import": 0, "network": 0, "original_path": 0, "subprocess": 0}}


def test_identical_isolated_reconstruction_is_accepted():
    original = receipt()
    helper.validate_cpu_case(copy.deepcopy(original), original, {"execution_id": "fixture-execution"})


@pytest.mark.parametrize("key,value", [
    ("status", "failed"), ("cli_exits", [0, 1, 0]), ("execution_id", "other"),
    ("package_id", "other"), ("source_files", {"report.json": "changed"}),
    ("model_generations", 1), ("network_blocked", False),
    ("original_project_and_weights_blocked", False), ("torch_and_vllm_loaded", True),
    ("unexpected_blocked_attempts", {"forbidden_import": 0, "network": 1, "original_path": 0, "subprocess": 0}),
    ("unexpected_blocked_attempts", {}),
])
def test_wrong_or_nonisolated_reconstruction_cannot_pass(key, value):
    original, result = receipt(), receipt()
    result[key] = value
    with pytest.raises(ValueError):
        helper.validate_cpu_case(result, original, {"execution_id": "fixture-execution"})


def test_original_receipt_requires_nonempty_source_binding():
    original = receipt()
    original["source_files"] = {}
    with pytest.raises(ValueError):
        helper.validate_cpu_case(copy.deepcopy(original), original, {"execution_id": "fixture-execution"})


def test_location_cannot_name_another_execution():
    original = receipt()
    with pytest.raises(ValueError):
        helper.validate_cpu_case(copy.deepcopy(original), original, {"execution_id": "other"})
