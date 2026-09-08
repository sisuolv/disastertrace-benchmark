"""The live extension must preserve failures, identities and the offline boundary."""

from copy import deepcopy

import pytest

from disastertrace.controlled.generator import micro_episodes
from disastertrace.local_eval.storage import read
from disastertrace.repeat_eval import package as parent
from disastertrace.repeat_live import audit, package, runtime, statistics


@pytest.fixture
def candidate(tmp_path):
    episode = micro_episodes()[0]
    base = tmp_path / "parent"
    parent.freeze(
        {"base": [episode], "irrelevant_scope": [deepcopy(episode)]},
        base,
        tmp_path / "old-registry",
        fixture=True,
    )
    output = tmp_path / "execution"
    package.freeze(base, output, tmp_path / "registry")
    return output


@pytest.mark.parametrize(
    "mode", ["correct", "invalid-control", "wrong-valid", "extraction-control"]
)
def test_diagnostic_reconstructs_without_model_relabelling(candidate, tmp_path, mode):
    run = tmp_path / mode
    runtime.collect(candidate, run, mode=mode)
    result = audit.reconstruct(candidate, run)
    assert result["summary"]["received"] == 60
    assert statistics.summarize(result)["counts"]["checkpoints"] == 60
    assert result["summary"]["additional_model_calls"] == 0
    with pytest.raises(ValueError, match="model"):
        audit.reconstruct(candidate, run, require_model=True)


@pytest.mark.parametrize(
    "fault,received,unknown",
    [
        ("before_raw", 0, 12),
        ("after_raw", 12, 0),
        ("after_first_parse", 12, 0),
        ("partial_raw", 6, 6),
    ],
)
def test_failure_prefix_preserves_denominators(candidate, tmp_path, fault, received, unknown):
    run = tmp_path / "failed"
    with pytest.raises(RuntimeError):
        runtime.collect(candidate, run, fault=fault)
    result = audit.reconstruct(candidate, run)
    assert result["summary"]["received"] == received
    assert result["summary"]["outcome_unknown"] == unknown
    assert statistics.summarize(result)["counts"]["checkpoints"] == 60
    with pytest.raises(FileExistsError):
        runtime.collect(candidate, tmp_path / "second")


def test_offline_model_dispatch_and_fixture_authorization_rejected(candidate, tmp_path):
    with pytest.raises(ValueError):
        runtime.collect(candidate, tmp_path / "model", mode="model")
    with pytest.raises(ValueError):
        package.freeze(
            candidate / "parent",
            tmp_path / "live",
            tmp_path / "registry2",
            live=True,
            run_path=tmp_path / "prod",
            deadline_utc="2040-01-01T00:00:00+00:00",
        )


def test_new_identity_same_sampling_keys(candidate):
    plan, _, slots = package.verify(candidate)
    old, _, previous = parent.verify(candidate / "parent")
    assert plan["execution_id"] != old["execution_id"]
    assert [s["sampling_key"] for s in slots] == [s["sampling_key"] for s in previous]
    assert not ({s["slot_id"] for s in slots} & {s["slot_id"] for s in previous})


@pytest.mark.parametrize(
    "field,value",
    [("generation_authorized", 1), ("retries", True), ("repeats", 3), ("max_model_attempts", 60)],
)
def test_resealed_plan_cannot_change_scope(candidate, field, value):
    from disastertrace.automated.common import canonical, fingerprint
    from disastertrace.local_eval.storage import seal

    path = candidate / "execution.json"
    plan = read(path)
    plan[field] = value
    plan["execution_id"] = fingerprint({k: v for k, v in plan.items() if k != "execution_id"})
    path.write_text(canonical(plan) + "\n")
    (candidate / "manifest.json").unlink()
    seal(candidate)
    with pytest.raises(ValueError):
        package.verify(candidate)


def test_runtime_raw_survives_invalid_backend_identity(candidate, tmp_path, monkeypatch):
    original = runtime.FixtureBackend.generate

    def duplicate(self, prepared):
        rows = original(self, prepared)
        rows[1]["attempt_id"] = rows[0]["attempt_id"]
        return rows

    monkeypatch.setattr(runtime.FixtureBackend, "generate", duplicate)
    run = tmp_path / "bad-id"
    with pytest.raises(ValueError):
        runtime.collect(candidate, run)
    assert len(read(run / "raw/0000.json")["results"]) == 12
    with pytest.raises(ValueError):
        audit.reconstruct(candidate, run)


@pytest.mark.parametrize("mutation", ["seed", "repeat", "prompt", "carrier"])
def test_auditor_rebuilds_actual_requests(candidate, tmp_path, mutation):
    from disastertrace.automated.common import canonical

    run = tmp_path / mutation
    runtime.collect(candidate, run)
    path = run / "intents/0000.json"
    intent = read(path)
    if mutation == "seed":
        intent["prepared"][0]["sampling"]["seed"] += 1
    elif mutation == "repeat":
        intent["slots"][0]["repeat"] += 1
    elif mutation == "prompt":
        intent["prepared"][0]["prompt_token_ids"].append(42)
    else:
        intent["requests"][0]["previous_state"] = {"leaked": True}
    path.write_text(canonical(intent) + "\n")
    with pytest.raises(ValueError):
        audit.reconstruct(candidate, run)
