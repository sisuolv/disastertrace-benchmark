"""Ownership failures for the actual irregular native-task preview."""

import importlib.util
from copy import deepcopy
from pathlib import Path

import pytest

from disastertrace.forecast_task.common import read

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("p7_gpu_preview", HERE / "prepare_gpu_preview.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_complete_preview_reconstructs():
    layout = read(HERE / "GPU_LAYOUT_PREVIEW.json")
    assert MODULE.build(HERE / "execution_v1") == layout
    assert sum(w["planned_answers"] for w in layout["workers"]) == 1542
    assert max(w["planned_answers"] for w in layout["workers"]) == 390


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "split", "dispatch"])
def test_corrupt_worker_ownership_is_rejected(mutation):
    layout = deepcopy(read(HERE / "GPU_LAYOUT_PREVIEW.json"))
    slots = read(HERE / "execution_v1/schedule.json")
    first, second = layout["workers"][:2]
    if mutation in ("missing", "split"):
        removed = first["source_slot_indices"].pop()
        first["source_slot_ids"].pop()
        first["planned_answers"] -= 1
        if mutation == "split":
            second["source_slot_indices"].append(removed)
            second["source_slot_ids"].append(slots[removed]["slot_id"])
            second["planned_answers"] += 1
    elif mutation == "duplicate":
        first["source_slot_indices"].append(first["source_slot_indices"][0])
        first["source_slot_ids"].append(first["source_slot_ids"][0])
        first["planned_answers"] += 1
    else:
        layout["generation_authorized"] = True
    with pytest.raises(ValueError):
        MODULE.validate(layout, slots)
