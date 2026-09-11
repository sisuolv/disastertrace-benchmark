import importlib.util
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2] / "artifacts/autonomy_10h_v1"
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location("closure_supplement", ROOT / "seal_autonomy_supplement.py")
supplement = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(supplement)


def test_newly_bound_analysis_can_complete_original_inventory():
    supplement.covered_inputs({"analysis.json": "analysis-hash", "raw.json": "raw-hash"},
                              {"raw.json": "raw-hash"}, {"analysis.json": "analysis-hash"})


@pytest.mark.parametrize("accepted,additional", [({}, {}), ({}, {"analysis.json": "wrong"}),
                                              ({"analysis.json": "old"}, {"analysis.json": "new"})])
def test_missing_or_conflicting_evidence_cannot_be_hidden(accepted, additional):
    with pytest.raises(ValueError):
        supplement.covered_inputs({"analysis.json": "new"}, accepted, additional)


def test_conflict_rejected_even_when_input_does_not_use_it():
    with pytest.raises(ValueError, match="conflicts"):
        supplement.covered_inputs({}, {"old.json": "original"}, {"old.json": "changed"})
