import importlib.util
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2] / "artifacts/autonomy_10h_v1"
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("final_closure_check", ROOT / "seal_autonomy_supplement.py")
sealer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sealer)


@pytest.mark.skipif(not (ROOT / "publication_reconstruction_02/COPY_RECEIPT.json").exists(),
                    reason="requires the complete accepted local publication evidence")
def test_final_supplement_covers_deadline_input_before_validation():
    result = sealer.main_record()
    name = "artifacts/p7_forecast_live_v1/AUTONOMY_WINDOW.json"
    dispatch = sealer.read(ROOT / "dispatch_deadlines_v3.json")
    assert result["status"] == "passed"
    assert result["evidence_sha256"][name] == dispatch["input_files_sha256"][name]
    assert len(result["archive_cpu_reconstruction_cases"]) == 6
