"""Integration checks use the cached, predeclared NHC pilot acquisition."""

import json
from pathlib import Path

import pytest

from disastertrace.automated.common import read_jsonl
from disastertrace.automated.workflow import build, report, run, score

REFERENCES = Path(__file__).resolve().parents[2] / "references"


@pytest.fixture(scope="module")
def cohort_build(tmp_path_factory):
    output = tmp_path_factory.mktemp("cohort-build") / "build"
    summary = build(REFERENCES, output, nhc_snapshot=REFERENCES / "nhc_cohort_v1")
    return output, summary


def test_cohort_build_keeps_event_assignments_and_source_coverage(cohort_build):
    path, summary = cohort_build
    assert summary["planned_weather_events"] == 12
    assert 1 < summary["independent_weather_events"] <= 12
    assert summary["dynamic_episodes"] == 2 * summary["independent_weather_events"]
    assert summary["dynamic_checkpoints"] == 10 * summary["independent_weather_events"]
    episodes = read_jsonl(path / "episodes/dynamic_episodes.jsonl")
    by_group = {}
    for episode in episodes:
        by_group.setdefault(episode["group_id"], set()).add(episode["split"])
    assert all(len(splits) == 1 for splits in by_group.values())
    assert by_group["AL092021"] == {"development"}
    assert {ep["split"] for ep in episodes} == {"development", "heldout"}
    assert (path / "profiles/cohort.json").is_file()
    assert (path / "splits/event_groups.json").is_file()


@pytest.mark.parametrize("split", ["development", "heldout"])
def test_selected_split_has_full_denominators_and_event_report(cohort_build, tmp_path, split):
    path, _ = cohort_build
    selected = [
        ep for ep in read_jsonl(path / "episodes/dynamic_episodes.jsonl") if ep["split"] == split
    ]
    run_path, score_path = tmp_path / "run", tmp_path / "score.json"
    config = run(path, run_path, track="dynamic", backend="rule", split=split, max_queries=1000)
    assert config["selected_episode_ids"] == [ep["episode_id"] for ep in selected]
    assert config["logical_queries"] == len(selected) * 5
    result = score(path, run_path, score_path)
    assert result["metrics"]["grounded_state"]["denominator"] == len(selected) * 25
    assert result["event_summary"]["n_events"] == len(selected) // 2
    assert set(result["event_summary"]["by_split"]) == {split}
    content = report(path, [score_path], tmp_path / "report.md")
    assert "Event-level results" in content
    assert split in content


def test_changed_split_cannot_reinterpret_a_saved_run(cohort_build, tmp_path):
    path, _ = cohort_build
    run_path = tmp_path / "run"
    run(path, run_path, track="dynamic", backend="rule", split="development", max_queries=1000)
    config_path = run_path / "run.json"
    config = json.loads(config_path.read_text())
    config["split"] = "heldout"
    config_path.write_text(json.dumps(config))
    with pytest.raises(ValueError):
        score(path, run_path, tmp_path / "invalid.json")


def test_planning_track_does_not_claim_weather_split(cohort_build, tmp_path):
    with pytest.raises(ValueError, match="split"):
        run(
            cohort_build[0],
            tmp_path / "invalid",
            track="disasterbench",
            backend="empty-control",
            split="heldout",
            max_queries=1,
        )


def test_model_preparation_is_network_free_and_only_contains_first_legal_request(
    cohort_build, tmp_path, monkeypatch
):
    from disastertrace.automated.model_workflow import prepare_model
    from disastertrace.automated.provider import ProviderClient

    def forbidden(*args, **kwargs):
        pytest.fail("preparation attempted a model call")

    monkeypatch.setattr(ProviderClient, "complete", forbidden)
    config = Path(__file__).resolve().parents[1] / "configs/provider.example.json"
    path = tmp_path / "prepared.json"
    result = prepare_model(cohort_build[0], config, path, split="development", max_queries=7)
    assert result["model_calls"] == 0
    assert result["model_configuration_complete"] is False
    assert result["endpoint_connectivity_tested"] is False
    wire = result["first_request_only"]["payload"]
    public = json.loads(wire["messages"][1]["content"])
    assert public["evidence"] == []
    assert public["previous_state"] is None
    assert "records" not in public and "reference" not in public
    with pytest.raises(ValueError, match="exists"):
        prepare_model(cohort_build[0], config, path, split="development", max_queries=7)


def test_collection_rejects_placeholder_without_calling_model(cohort_build, tmp_path):
    from disastertrace.automated.model_workflow import collect_from_build

    config = Path(__file__).resolve().parents[1] / "configs/provider.example.json"
    output = tmp_path / "collection"
    with pytest.raises(ValueError, match="example model"):
        collect_from_build(cohort_build[0], config, output, max_queries=7)
    assert not output.exists()


def test_fixture_transport_collection_import_and_score_preserve_actual_requests(
    cohort_build, tmp_path, monkeypatch
):
    from disastertrace.automated import collection
    from disastertrace.automated.dynamic import diagnostic_response
    from disastertrace.automated.model_workflow import collect_from_build
    from disastertrace.automated.provider import ProviderClient

    requests = []

    def transport(url, body, headers, timeout, max_response_bytes):
        payload = json.loads(body)
        public = json.loads(payload["messages"][1]["content"])
        requests.append(public)
        response = {
            "model": "offline-fixture-not-an-llm",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": diagnostic_response(public, "rule"),
                    },
                    "finish_reason": "stop",
                }
            ],
        }
        return 200, json.dumps(response).encode()

    monkeypatch.setattr(
        collection, "ProviderClient", lambda config: ProviderClient(config, transport=transport)
    )
    config = json.loads(
        (Path(__file__).resolve().parents[1] / "configs/provider.example.json").read_text()
    )
    config["model"] = "offline-fixture-not-an-llm"
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config))
    output = tmp_path / "model-run"
    result = collect_from_build(cohort_build[0], config_path, output, max_queries=7)
    assert len(requests) == result["collection"]["attempts_started"] == 7
    assert result["collection"]["transport_kind"] == "injected_transport_unverified"
    assert result["eligible_for_llm_leaderboard"] is False
    assert result["metrics"]["schema_success"]["numerator"] == 7
    assert result["metrics"]["schema_success"]["denominator"] == 30
    traces = read_jsonl(output / "imported_run/trace.jsonl")
    assert [row["request"] for row in traces[:7]] == requests
    assert all(row["provider_requests"] == 0 for row in traces)
    assert requests[1]["previous_state"] is not None
    assert requests[5]["previous_state"] is None
