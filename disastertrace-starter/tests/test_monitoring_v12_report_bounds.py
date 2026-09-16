"""Exhaustive hidden-outcome completions independently check sensitivity bounds."""
import importlib.util
import itertools
from pathlib import Path

import pytest


def analyzer():
    path=Path(__file__).resolve().parents[2]/"plans/v12_execution_20260915_01/analyze_stage_c.py"
    spec=importlib.util.spec_from_file_location("v12_report_bounds",path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_missing_outcome_interval_equals_exhaustive_binary_completions():
    rows=[{"settled":True,"y":1,"probabilities":{"reference":.8,"candidate":.9}},
          {"settled":False,"y":None,"probabilities":{"reference":.9,"candidate":.1}},
          {"settled":False,"y":None,"probabilities":{"reference":.1,"candidate":.7}}]
    result=analyzer().paired(rows,"reference","candidate")
    possibilities=[]
    for y1,y2 in itertools.product((0,1),repeat=2):
        values=[1,y1,y2]
        possibilities.append(sum((r["probabilities"]["reference"]-y)**2-(r["probabilities"]["candidate"]-y)**2
            for r,y in zip(rows,values))/len(rows))
    assert result["prediction_specific_missing_Y_bounds"]==pytest.approx([min(possibilities),max(possibilities)])
    assert result["mean_brier_improvement"]==pytest.approx(.03)
    assert result["positive_contribution_per_settled_opportunity"]==pytest.approx(.03)
    assert result["negative_contribution_per_settled_opportunity"]==0


def test_negative_only_gain_cannot_be_reported_as_positive_gain():
    rows=[{"settled":True,"y":0,"probabilities":{"F_COMMON":.5,"LLM_SELECTOR":.1}},
          {"settled":True,"y":0,"probabilities":{"F_COMMON":.3,"LLM_SELECTOR":.1}}]
    result=analyzer().paired(rows,"F_COMMON","LLM_SELECTOR")
    assert result["mean_brier_improvement"]==pytest.approx(.16)
    assert result["positive"]==0
    assert result["positive_contribution_per_settled_opportunity"]==0
    assert result["negative_contribution_per_settled_opportunity"]==pytest.approx(.16)
    assert result["bank_difference_involved"] is True
    assert result["prediction_specific_missing_Y_bounds"]==pytest.approx([.16,.16])
