"""Regression coverage for comparisons of nested and checkpoint-level opportunities."""

import hashlib
import importlib.util
import json
from copy import deepcopy
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "contract_equivalence", PROJECT / "scripts/verify_p2_output_contract.py"
)
COMPARISON = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(COMPARISON)


@pytest.mark.parametrize("depth", [1, 2, 3])
def test_denominators_include_matched_pairs_inside_lists(depth):
    value = {"numerator": 2, "denominator": 5, "value": 0.4}
    for _ in range(depth):
        value = [value]
    result = COMPARISON.denominators({"matched_pairs": value})
    assert result == {"/matched_pairs" + "/0" * depth: 5}


def test_checkpoint_opportunities_detect_redistribution_with_equal_totals():
    keys = {denominator for _, denominator in COMPARISON.METRICS.values()}
    base = {
        "episode_id": "episode",
        "root_id": "pair",
        "group_id": "source",
        "family": "U1",
        "branch": "active",
        "slots": {"maximum_wind_mph": {}},
        "counts": dict.fromkeys(keys, 0),
    }
    first, second = deepcopy(base), deepcopy(base)
    first["checkpoint_id"], second["checkpoint_id"] = "c1", "c2"
    first["counts"]["updates"] = 1
    methods = {"snapshot": {"per_checkpoint": [first, second]}}
    changed = deepcopy(methods)
    changed["snapshot"]["per_checkpoint"][0]["counts"]["updates"] = 0
    changed["snapshot"]["per_checkpoint"][1]["counts"]["updates"] = 1
    assert COMPARISON.checkpoint_opportunities(methods) != COMPARISON.checkpoint_opportunities(
        changed
    )


def test_score_key_order_is_not_a_metric_change_but_changed_values_are(tmp_path):
    old, new = tmp_path / "old", tmp_path / "new"
    old.mkdir()
    new.mkdir()
    (old / "score.json").write_text('{"numerator":2,"denominator":5}')
    (new / "score.json").write_text('{"denominator":5,"numerator":2}')
    result = COMPARISON.identical_files(old, new, ["score.json"], json_content=True)
    assert result["score.json"]["old_sha256"] != result["score.json"]["new_sha256"]
    with pytest.raises(ValueError, match="bytes changed"):
        COMPARISON.identical_files(old, new, ["score.json"])
    (new / "score.json").write_text('{"denominator":5,"numerator":3}')
    with pytest.raises(ValueError, match="JSON content changed"):
        COMPARISON.identical_files(old, new, ["score.json"], json_content=True)


@pytest.mark.parametrize("tamper", ["failed", "hash", "missing_test", "skipped"])
def test_reuse_rejects_incomplete_or_changed_pipeline_before_execution(
    tmp_path, monkeypatch, tamper
):
    monkeypatch.syspath_prepend(str(PROJECT / "scripts"))
    spec = importlib.util.spec_from_file_location(
        "contract_reproduction", PROJECT / "scripts/reproduce_p2_output_contract.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    names = [
        "tests",
        "lint",
        "format",
        "dependencies",
        "build",
        "p2_prepare",
        "p2_verify",
        "execution_prepare",
        "execution_verify",
        "execution_rehearse",
        "execution_audit",
        "execution_report",
        "report_verify",
    ]
    records = []
    for name in names:
        content = "1 passed in 0.1s" if name == "tests" else "fixture only"
        if name == "tests" and tamper == "skipped":
            content = "1 passed, 1 skipped in 0.1s"
        (tmp_path / (name + ".log")).write_text(content)
        records.append(
            {
                "name": name,
                "exit_code": int(name == "tests" and tamper == "failed"),
                "log_sha256": hashlib.sha256(content.encode()).hexdigest(),
            }
        )
    (tmp_path / "commands.json").write_text(
        json.dumps(
            {
                "tests_requested": tamper != "missing_test",
                "records": records,
            }
        )
    )
    (tmp_path / "status.json").write_text("{}")
    if tamper == "hash":
        (tmp_path / "tests.log").write_text("changed fixture log")
    with pytest.raises(ValueError):
        module.verify_completed_pipeline(tmp_path)
