"""Contract regressions; reference-copy scores are fixture-only diagnostics."""

import json
from copy import deepcopy

import pytest

from disastertrace.automated.disasterbench import build_disasterbench, score_disasterbench


@pytest.fixture
def bundle(tmp_path):
    tools = {
        "observe": {
            "desc": "Observe a source",
            "input": {"path": "Source path"},
            "output": {"observation": "Observation", "metadata": "Metadata"},
        },
        "summarize": {
            "desc": "Summarize observations",
            "input": {"path": "Observation"},
            "output": {"report": "Report"},
        },
        "unused": {
            "desc": "Unused distractor",
            "input": {"path": "Source"},
            "output": {"extra": "Extra output"},
        },
    }
    plan = [
        {
            "step": 0,
            "agent": "observe",
            "inputs": {"path": "/data/storm.txt"},
            "outputs": ["observation", "metadata"],
            "dependence": [-1],
            "dependence_content": None,
        },
        {
            "step": 1,
            "agent": "summarize",
            "inputs": {"path": "<GENERATED>-0-<observation>"},
            "outputs": ["report"],
            "dependence": [0],
            "dependence_content": {"0": ["observation"]},
        },
    ]
    rows = [
        {
            "task_id": i,
            "task_desc": f"Analyze storm {i} from /data/storm.txt",
            "structured_plan": deepcopy(plan),
            "source": "benchmark",
        }
        for i in (1, 2)
    ]
    data_path, tools_path = tmp_path / "tasks.jsonl", tmp_path / "tools.json"
    data_path.write_text("\n".join(json.dumps(row) for row in rows))
    tools_path.write_text(json.dumps(tools))
    return build_disasterbench(data_path, tools_path), data_path, tools_path


def fixture_predictions(built):
    """Copies labels solely to validate the scorer, never to simulate an LLM."""
    return [
        {"task_id": ref["task_id"], "structured_plan": deepcopy(ref["structured_plan"])}
        for ref in built["private_references"]
    ]


def score(built, predictions):
    return score_disasterbench(built["public_tasks"], built["private_references"], predictions)


def test_reference_copy_is_only_an_offline_scorer_fixture(bundle):
    built, _, _ = bundle
    result = score(built, fixture_predictions(built))
    assert result["aggregate"]["expected_tasks"] == 2
    assert result["aggregate"]["exact_match_accuracy"] == 1.0
    assert result["interpretation"] == "inherited_label_agreement_not_tool_execution"
    assert all(item["status"] == "correct" for item in result["per_task"])


def test_public_tasks_contain_no_reference_plan_or_gold_selected_tools(bundle):
    built, _, _ = bundle
    public = built["public_tasks"][0]
    assert "structured_plan" not in public
    assert "reference" not in public
    assert set(public["tools"]) == {"observe", "summarize", "unused"}
    assert "<GENERATED>-0-<observation>" not in json.dumps(public)
    assert built["private_references"][0]["label_origin"] == "inherited_upstream_unreviewed"
    assert len(built["profile"]["source_hashes"]["data_sha256"]) == 64


def test_missing_and_invalid_predictions_remain_in_denominator(bundle):
    built, _, _ = bundle
    predictions = fixture_predictions(built)[:1]
    assert score(built, predictions)["aggregate"]["exact_match_accuracy"] == 0.5
    result = score(built, [{"task_id": predictions[0]["task_id"], "structured_plan": []}])
    assert result["aggregate"]["missing_predictions"] == 1
    assert result["aggregate"]["invalid_predictions"] == 1
    assert result["aggregate"]["exact_match_accuracy"] == 0.0
    assert all(item["exact_match"] == 0 for item in result["per_task"])


@pytest.mark.parametrize("bad_plan", [None, "[]", {}, [None], [{}], [1]])
def test_malformed_plan_cannot_pass_vacuously(bundle, bad_plan):
    built, _, _ = bundle
    result = score(
        built, [{"task_id": built["public_tasks"][0]["task_id"], "structured_plan": bad_plan}]
    )
    assert result["aggregate"]["invalid_predictions"] == 1
    assert result["aggregate"]["exact_match_accuracy"] == 0.0


@pytest.mark.parametrize(
    "field,value",
    [
        ("agent", "unused"),
        ("inputs", {"path": "/wrong/path"}),
        ("outputs", ["metadata", "observation"]),
        ("dependence", [0]),
        ("dependence_content", {"0": ["metadata"]}),
    ],
)
def test_tool_parameter_output_and_dependency_errors_fail(bundle, field, value):
    built, _, _ = bundle
    predictions = fixture_predictions(built)
    predictions[0]["structured_plan"][0][field] = value
    assert score(built, predictions)["aggregate"]["exact_match_accuracy"] == 0.5


def test_step_order_and_extra_fields_are_not_silently_repaired(bundle):
    built, _, _ = bundle
    predictions = fixture_predictions(built)
    predictions[0]["structured_plan"].reverse()
    predictions[1]["structured_plan"][0]["agent_name"] = "observe"
    assert score(built, predictions)["aggregate"]["exact_match_accuracy"] == 0.0


def test_only_dependence_list_order_is_ignored(bundle):
    built, _, _ = bundle
    third = {
        "step": 2,
        "agent": "summarize",
        "inputs": {"path": "<GENERATED>-0-<observation>"},
        "outputs": ["report"],
        "dependence": [0, 1],
        "dependence_content": {"0": ["observation"], "1": ["report"]},
    }
    built["private_references"][0]["structured_plan"].append(third)
    predictions = fixture_predictions(built)
    predictions[0]["structured_plan"][2]["dependence"] = [1, 0]
    assert score(built, predictions)["aggregate"]["exact_match_accuracy"] == 1.0
    predictions[0]["structured_plan"][2]["dependence_content"] = {
        "0": ["report"],
        "1": ["observation"],
    }
    assert score(built, predictions)["aggregate"]["exact_match_accuracy"] == 0.5


def test_boolean_step_ids_and_top_level_extras_are_invalid(bundle):
    built, _, _ = bundle
    predictions = fixture_predictions(built)
    predictions[0]["structured_plan"][0]["step"] = False
    predictions[1]["reasoning"] = "Extra field is outside the frozen response contract."
    assert score(built, predictions)["aggregate"]["invalid_predictions"] == 2


def test_duplicate_unknown_and_unidentifiable_prediction_ids_are_rejected(bundle):
    built, _, _ = bundle
    predictions = fixture_predictions(built)
    for invalid in [predictions + predictions[:1], [{"task_id": "unknown"}], [{}], [None]]:
        with pytest.raises(ValueError):
            score(built, invalid)


def test_reference_and_public_task_ids_must_match_exactly(bundle):
    built, _, _ = bundle
    with pytest.raises(ValueError):
        score_disasterbench(built["public_tasks"], built["private_references"][:1], [])
    with pytest.raises(ValueError):
        score_disasterbench([], [], [])


def test_inconsistent_reference_labels_are_quarantined_without_repair(bundle):
    _, data_path, tools_path = bundle
    rows = [json.loads(line) for line in data_path.read_text().splitlines()]
    rows[0]["structured_plan"][1]["step"] = 0
    rows[1]["structured_plan"][1]["dependence_content"] = {"0": ["missing_output"]}
    data_path.write_text("\n".join(json.dumps(row) for row in rows))
    built = build_disasterbench(data_path, tools_path)
    assert built["profile"]["source_tasks"] == 2
    assert built["profile"]["admitted_tasks"] == 0
    assert built["profile"]["quarantined_tasks"] == 2
    assert built["public_tasks"] == []
    assert built["private_references"] == []
    assert built["profile"]["schema_issues"]


def test_duplicate_source_ids_quarantine_all_collisions(bundle):
    _, data_path, tools_path = bundle
    row = json.loads(data_path.read_text().splitlines()[0])
    data_path.write_text(json.dumps(row) + "\n" + json.dumps(row))
    built = build_disasterbench(data_path, tools_path)
    assert built["profile"]["admitted_tasks"] == 0
    assert built["profile"]["quarantined_tasks"] == 2


def test_non_json_and_duplicate_json_keys_are_quarantined(bundle):
    _, data_path, tools_path = bundle
    data_path.write_text('{"task_id": 1, "task_id": 2}\nnot json\n')
    built = build_disasterbench(data_path, tools_path)
    assert built["profile"]["quarantined_tasks"] == 2
