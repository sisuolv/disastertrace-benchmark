"""The sequential launcher must not turn partial engineering into science."""

import ast

import pytest

from compatibility import SpecializeLegacy
from program import gates_ready


def gates():
    return [{"passed":True,"completed_cases":168,"registered_cases":168,"method_rows":60480,"trajectories":840},
            {"passed":True},{"passed":True},
            {"status":"RETAINED_FOR_B02","frozen_bank_identity":{"values":"hash"}},{"passed":True}]


def test_complete_gate_is_accepted():
    assert gates_ready(*gates())


@pytest.mark.parametrize("index",[0,1,2,4])
def test_failed_dependency_is_not_silently_skipped(index):
    rows=gates();rows[index]["passed"]=False
    assert not gates_ready(*rows)


@pytest.mark.parametrize("change",[{"completed_cases":167},{"method_rows":60479},{"trajectories":839}])
def test_partial_calendar_cannot_open_b02(change):
    rows=gates();rows[0].update(change)
    assert not gates_ready(*rows)


def test_proposed_bank_is_not_a_frozen_decision():
    rows=gates();rows[3]["status"]="WAITING_B00_ACCEPTANCE"
    assert not gates_ready(*rows)


def test_compatibility_specialization_does_not_strip_changed_prediction():
    original=ast.parse("def f(x):\n    return x + 1\n")
    altered=ast.parse("def f(x):\n    return x + 2\n")
    assert ast.dump(original)!=ast.dump(SpecializeLegacy().visit(altered))
