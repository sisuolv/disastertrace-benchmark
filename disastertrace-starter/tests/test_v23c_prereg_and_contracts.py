"""C1 red/green contracts for the v23-C preregistration revision."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
CONFIG = ROOT / "config" / "v23b"
SCRIPT = ROOT / "scripts" / "generate_v23b_llm_prompts.py"
ROSTER_SCRIPT = ROOT / "scripts" / "build_v23_source_roster.py"
FEATURES = ROOT / "src" / "disastertrace" / "revision_v1" / "v23_source_features.py"


def test_policy_v2_has_uncertainty_age_disagreement_and_fallback():
    path = CONFIG / "POLICY_CLASS_v2.json"
    assert path.exists(), "v2 policy contract must be present"
    data = json.loads(path.read_text())
    assert data["version"] == "v23c-pi-2"
    families = {item["family"] for item in data["policies"]}
    assert {"uncertainty", "age", "disagreement"} <= families
    assert all(item.get("fallback") == "S_fixed_from_training_fold" for item in data["policies"])
    assert len(data["policies"]) <= 50


def test_f_spec_v2_has_two_recent_metars_and_full_state_space():
    path = CONFIG / "F_SPEC_v2.json"
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["version"] == "v23c-F-stat-2"
    assert "metar_recent_1_visibility" in data["features"]
    assert "metar_recent_2_visibility" in data["features"]
    assert "metar_recent_1_age_s" in data["features"]
    assert "metar_recent_2_age_s" in data["features"]
    assert data["state_space"]["all_checkpoint_purchase_combinations"] is True
    assert data["calibration"]["method"] == "Platt"
    assert data["calibration"]["C_grid"] == [0.01, 0.1, 1, 10]


def test_analysis_plan_v2_defines_llm_and_k6_decisions():
    path = CONFIG / "ANALYSIS_PLAN_v2.json"
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["version"] == "v23c-analysis-2"
    assert data["decision_rules"]["G_adapt_HARM"]
    assert "D_llm" in data["quantities"]
    assert "K6" in data["decision_rules"]
    assert data["synthetic_controls"]["N_zero"] == 20000
    assert data["bootstrap"]["replicates"] >= 400


def test_prompt_v2_contains_absolute_day_time_and_excludes_k6_template(tmp_path):
    roster = tmp_path / "roster.jsonl"
    row = {
        "target_id": "KDEN_20250101_00_5000m",
        "checkpoint_id": "-6h",
        "cutoff_us": 1735668000000000,
        "physical_start_us": 1735689600000000,
        "physical_end_us": 1735693200000000,
        "lead_hours": 6,
        "station": "KDEN",
        "taf": {"raw": "TAF KDEN 010000Z 0100/0200 00000KT P6SM"},
        "recent_metars": [{
            "available_at_us": 1735667400000000,
            "observation_time_us": 1735666800000000,
            "report_type": "routine",
            "raw": "KDEN 312300Z 00000KT 10SM",
        }],
        "source_only": True,
        "features_do_not_include_outcome": True,
    }
    roster.write_text(json.dumps(row) + "\n")
    out = tmp_path / "out"
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--input", str(roster), "--out-dir", str(out), "--v2"],
        capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stderr
    prompt = json.loads((out / "m1_prompts.jsonl").read_text().splitlines()[0])["prompt"]
    assert "Current time (UTC):" in prompt
    assert "Target window (UTC):" in prompt
    assert "For a later acquisition decision" not in prompt
    assert "K6 output template" not in prompt
    assert '"action"' not in prompt


def test_preflight_checks_tracked_and_untracked_contracts():
    text = FEATURES.read_text()
    assert "git ls-files --error-unmatch" in text
    assert "git status --porcelain" in text


def test_build_script_has_synthetic_end_to_end_fixture_mode(tmp_path):
    fixture = tmp_path / "fixture.json"
    fixture.write_text(json.dumps({"targets": [{"target_id": "t"}], "checkpoints": [{"checkpoint_id": "c"}]}) + "\n")
    completed = subprocess.run(
        [sys.executable, str(ROSTER_SCRIPT), "--synthetic-fixture", str(fixture), "--output", str(tmp_path / "out")],
        capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads((tmp_path / "out" / "SYNTHETIC_RESULT.json").read_text())
    assert result["targets"] == 1
    assert result["checkpoints"] == 1
