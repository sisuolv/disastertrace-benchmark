import copy
import importlib.util
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2] / "artifacts/autonomy_10h_v1"
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("paired_coverage", ROOT / "analyze_pair_coverage.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def row(slot, received, correct):
    return {"slot_id": str(slot), "opportunity_id": "op" + str(slot), "episode_id": "episode",
            "storm_id": "storm", "method": "snapshot",
            "score": {"received": received, "all_correct": correct}}


def test_all_coverage_cells_and_delta_reconcile():
    before = [row(0, True, True), row(1, True, False), row(2, True, True), row(3, True, False),
              row(4, True, True), row(5, False, False), row(6, False, False)]
    after = [row(0, True, True), row(1, True, True), row(2, True, False), row(3, True, False),
             row(4, False, False), row(5, True, True), row(6, False, False)]
    originals = copy.deepcopy((before, after))
    tables = module.partition(before, list(reversed(after)))
    for table in tables.values():
        assert table["planned"] == 7
        assert table["before_correct"] == table["after_correct"] == 3
        assert [c["slots"] for c in table["coverage_cells"].values()] == [4, 1, 1, 1]
        assert set(table["both_returned_correctness_pairs"].values()) == {1}
        assert table["both_returned_before_accuracy"] == table["both_returned_after_accuracy"] == 0.5
        assert table["strict_correct_difference"] == 0
    assert (before, after) == originals


def test_missing_correct_answers_explain_full_denominator_difference():
    table = module.partition([row(0, True, True), row(1, True, True), row(2, False, False)],
                             [row(0, True, False), row(1, False, False), row(2, True, True)])["all"]
    assert table["strict_correct_difference"] == -1
    assert table["difference_on_both_returned_slots"] == -1
    assert table["difference_on_one_sided_return_slots"] == 0


def test_no_common_returns_has_no_conditional_accuracy():
    table = module.partition([row(0, True, True)], [row(0, False, False)])["all"]
    assert table["strict_correct_difference"] == -1
    assert table["difference_on_one_sided_return_slots"] == -1
    assert table["both_returned_before_accuracy"] is None
    assert table["both_returned_after_accuracy"] is None


@pytest.mark.parametrize("side", [0, 1])
def test_duplicate_slots_rejected(side):
    cases = [[row(0, True, True)], [row(0, True, True)]]
    cases[side].append(copy.deepcopy(cases[side][0]))
    with pytest.raises(ValueError, match="duplicate"):
        module.partition(*cases)


def test_changed_pair_identity_rejected():
    before, after = row(0, True, True), row(0, True, True)
    after["storm_id"] = "different"
    with pytest.raises(ValueError, match="identity"):
        module.partition([before], [after])


def test_unpaired_slots_rejected():
    with pytest.raises(ValueError, match="slot set"):
        module.partition([row(0, True, True)], [row(1, True, True)])


def test_missing_but_correct_is_rejected():
    with pytest.raises(ValueError, match="missing answer"):
        module.partition([row(0, False, True)], [row(0, True, True)])


def test_numeric_flags_rejected():
    before = row(0, 1, True)
    with pytest.raises(ValueError, match="booleans"):
        module.partition([before], [row(0, True, True)])
