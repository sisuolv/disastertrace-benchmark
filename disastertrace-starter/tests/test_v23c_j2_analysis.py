from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.score_v23_j2 import decision, run_synthetic_acceptance


def test_zero_value_gate_does_not_use_large_h_as_go_signal():
    result = run_synthetic_acceptance(seed=20260927, zero_n=20000)
    assert result["acceptance"] is True
    assert result["zero_world"]["H"] > 0.005
    assert result["zero_world"]["decision"] in {"STOP", "INCONCLUSIVE"}
    assert result["positive_world"]["decision"] == "GO"


def test_decision_requires_positive_lower_bound_and_delta():
    assert decision(0.004, [0.004] * 200, delta=0.005)["decision"] != "GO"
    assert decision(0.02, [0.02] * 200, delta=0.005)["decision"] == "GO"


def test_synthetic_cli_writes_auditable_result(tmp_path):
    output = tmp_path / "synthetic.json"
    completed = subprocess.run(
        [sys.executable, "disastertrace-starter/scripts/score_v23_j2.py", "--synthetic-only", "--output", str(output)],
        capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stderr
    data = json.loads(output.read_text())
    assert data["seed"] == 20260927
    assert data["zero_n"] == 20000
    assert data["acceptance"] is True
