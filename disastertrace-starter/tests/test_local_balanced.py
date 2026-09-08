"""Balanced coverage, carrier/provenance protection and local audit reconstruction."""

from collections import Counter
from copy import deepcopy

import pytest

from disastertrace.automated.common import canonical
from disastertrace.controlled import generator, public_oracle, renderer
from disastertrace.controlled import runtime as diagnostic
from disastertrace.controlled.schema import FIELDS, METHODS
from disastertrace.local_eval import adapter, audit, data, execution, runtime
from disastertrace.local_eval.storage import read, seal, verify_seal, write


@pytest.fixture(scope="module")
def bindings():
    return [
        {
            "group_id": group,
            "split": "development",
            "source_build_id": "test",
            "inherited_values": dict(zip(FIELDS, (85, 984, 24.8, -86.1))),
            "source_record_id": "fixture-source",
            "source_record_sha256": "a" * 64,
            "parent_source_sha256": "b" * 64,
            "source_url": "https://example.test/fixture",
            "source_field_evidence": {
                field: {"line_start": 1, "line_end": 1, "text": "fixture"} for field in FIELDS
            },
        }
        for group in generator.EVENTS
    ]


@pytest.fixture(scope="module")
def episodes(bindings):
    return data.balanced_episodes(bindings)


def test_balanced_crossing_and_legacy_subset(episodes, bindings):
    assert len(episodes) == 36
    assert len({e["root_id"] for e in episodes}) == 18
    assert len({e["episode_id"] for e in episodes}) == 36
    counts = Counter((e["group_id"], e["family"], e["case"]) for e in episodes)
    assert len(counts) == 18 and set(counts.values()) == {2}
    assert all(e in episodes for e in generator.from_bindings(bindings))


def test_wave_schedule_is_complete_and_carrier_safe(episodes):
    slots = data.schedule(episodes)
    assert len(slots) == len({s["slot_id"] for s in slots}) == 540
    assert slots == data.schedule(episodes)
    counts = Counter((s["family"], s["method"]) for s in slots)
    assert set(counts.values()) == {60}
    for start in range(0, 540, 12):
        batch = slots[start : start + 12]
        assert len({s["trajectory_id"] for s in batch}) == 12
        assert len({s["checkpoint_id"] for s in batch}) == 1
    for trajectory in {s["trajectory_id"] for s in slots}:
        assert [s["checkpoint_id"] for s in slots if s["trajectory_id"] == trajectory] == [
            f"c{i}" for i in range(5)
        ]


@pytest.mark.parametrize("method", METHODS)
def test_fixed_denominators_and_public_gold(episodes, method):
    from disastertrace.controlled.scorer import score

    result = score(episodes, diagnostic.rehearse(episodes, method), method)
    assert result["metrics"]["all_correct_checkpoints"]["numerator"] == 180
    assert result["metrics"]["known_grounded_accuracy"]["denominator"] == 564
    assert result["metrics"]["unknown_accuracy"]["denominator"] == 156
    assert result["metrics"]["schema_success"]["denominator"] == 180


@pytest.mark.parametrize("method", METHODS)
def test_public_messages_contain_only_declared_carrier(episodes, method):
    ep = episodes[0]
    previous = public_oracle.answer(renderer.render_request(ep, "c1", method=method))
    request = renderer.render_request(
        ep, "c2", method=method, previous=previous, history=[previous]
    )
    prep = adapter.prepare(request, data.schedule(episodes)[0], adapter.FixtureTokenizer())
    content = canonical(prep["messages"])
    for private in (
        "group_id",
        "source_build_id",
        "inherited_values",
        "root_id",
        "family",
        "branch",
        "case",
        "provenance",
    ):
        assert '"' + private + '"' not in canonical(request)
    assert ep["episode_id"] not in content
    assert len(prep["messages"]) == 2
    assert ("previous_state" in request) == (method == "structured_state")
    assert ("answer_history" in request) == (method == "answer_history")


def test_context_overflow_fails_without_truncation(episodes):
    request = renderer.render_request(episodes[0], "c0", method="snapshot")
    settings = {**adapter.SETTINGS, "max_model_len": 1}
    with pytest.raises(ValueError, match="truncation"):
        adapter.prepare(request, data.schedule(episodes)[0], adapter.FixtureTokenizer(), settings)


@pytest.mark.parametrize("kind", ["normal", "endoftext", "empty", "missing", "multiple", "fences"])
def test_reasoning_extraction_preserves_errors(kind):
    tok = adapter.FixtureTokenizer()
    body = "```json\n{}\n```" if kind == "fences" else "{}"
    tokens = tok.encode("reasoning") + [256] + tok.encode(body) + [257]
    if kind == "empty":
        tokens = []
    if kind == "missing":
        tokens = tok.encode(body)
    if kind == "multiple":
        tokens = [256] + tokens
    if kind == "endoftext":
        tokens[-1] = 258
    result = adapter.extract(tokens, tok)
    assert result["raw_text"] == tok.decode(tokens)
    assert sum(
        result[k]
        for k in ("reasoning_tokens", "content_tokens", "delimiter_tokens", "terminal_tokens")
    ) == len(tokens)
    if kind in ("normal", "endoftext", "fences"):
        assert result["content"] == body
        assert result["reasoning"] == "reasoning"
    else:
        assert result["content"] == ""
        assert result["extraction_error"]


@pytest.fixture
def fake_plan(tmp_path, monkeypatch, episodes):
    plan = {
        "execution_id": "test-execution",
        "settings": deepcopy(adapter.SETTINGS),
        "run_path": str(tmp_path / "production"),
        "deadline_utc": "2099-01-01T00:00:00+00:00",
        "dataset_content_id": "test-dataset",
        "environment_sha256": "test-env",
        "reliability_rule": {
            "planned_per_family_method": 60,
            "min_schema_valid": 58,
            "max_length": 2,
        },
    }
    monkeypatch.setattr(
        execution, "verify", lambda *a, **k: (plan, episodes, data.schedule(episodes))
    )
    return plan


@pytest.fixture
def collected(tmp_path, fake_plan):
    run = tmp_path / "diagnostic"
    runtime.collect(tmp_path / "execution", run, diagnostic=True)
    return run


def test_complete_diagnostic_and_independent_reconstruction(tmp_path, collected):
    report = tmp_path / "report"
    result = audit.report(tmp_path, collected, report)
    assert result["received"] == 540 and result["model_calls"] == 0
    assert audit.report(tmp_path, collected, report, verify=True) == result
    content = read(report / "report.json")
    assert content["errors"] == {"fields": [], "actions": []}
    assert content["reliability"]["thresholds_passed"]
    assert not content["reliability"]["measured_model_reliability"]
    assert all(p["dependent_checkpoint_pairs"] == 60 for p in content["paired_by_source"])
    with pytest.raises(ValueError, match="diagnostics cannot"):
        audit.report(tmp_path, collected, tmp_path / "model-report", require_model=True)


def test_one_use_claim_and_diagnostic_scope(tmp_path, collected, fake_plan):
    with pytest.raises(FileExistsError):
        runtime.collect(tmp_path, collected, diagnostic=True)
    with pytest.raises(ValueError, match="consume production"):
        runtime.collect(tmp_path, fake_plan["run_path"], diagnostic=True)
    with pytest.raises(ValueError, match="canonical"):
        runtime.collect(tmp_path, tmp_path / "wrong")


@pytest.mark.parametrize(
    "mutation", ["origin", "tokens", "usage", "carrier", "binding", "finish", "raw_text", "time"]
)
def test_tampered_capture_rejected(tmp_path, collected, mutation):
    path = collected / "captures/0000.json"
    item = read(path)
    if mutation == "origin":
        item["origin"] = "local_model_vllm"
    if mutation == "tokens":
        item["result"]["prompt_token_ids"] += [12]
    if mutation == "usage":
        item["completion_tokens"] += 1
    if mutation == "carrier":
        item["state_after"] = None
    if mutation == "binding":
        item["prepared_sha256"] = "changed"
    if mutation == "finish":
        item["result"]["finish_reason"] = "length"
    if mutation == "raw_text":
        item["result"]["runtime_output_text"] = "repaired"
    if mutation == "time":
        item["captured_at"] = "2000-01-01T00:00:00+00:00"
    path.write_text(canonical(item))
    with pytest.raises(ValueError):
        audit.audit(tmp_path, collected)


@pytest.mark.parametrize("mutation", ["gold", "future", "seed", "method"])
def test_tampered_intent_rejected(tmp_path, collected, mutation):
    path = collected / "batches/000.json"
    item = read(path)
    if mutation == "gold":
        item["requests"][0]["private_gold"] = {}
    if mutation == "future":
        item["requests"][0]["checkpoint_time"] = "2099-01-01T00:00:00+00:00"
    if mutation == "seed":
        item["prepared"][0]["sampling"]["seed"] += 1
    if mutation == "method":
        item["slots"][0]["method"] = "invalid"
    path.write_text(canonical(item))
    with pytest.raises(ValueError):
        audit.audit(tmp_path, collected)


def test_interrupted_batch_preserves_unresolved_opportunities(tmp_path, fake_plan, monkeypatch):
    def fail(self, prepared):
        raise RuntimeError("deliberate interruption after durable intent")

    monkeypatch.setattr(runtime.FixtureBackend, "generate", fail)
    run = tmp_path / "interrupted"
    with pytest.raises(RuntimeError):
        runtime.collect(tmp_path, run, diagnostic=True)
    files = audit.reconstruct(tmp_path, run)
    assert files["audit.json"]["pending_slots"] == list(range(12))
    assert files["audit.json"]["unsubmitted"] == 528
    assert not files["report.json"]["complete"]
    assert (
        sum(
            m["metrics"]["schema_success"]["denominator"]
            for m in files["report.json"]["methods"].values()
        )
        == 540
    )
    with pytest.raises(FileExistsError):
        runtime.collect(tmp_path, run, diagnostic=True)


def test_invalid_output_is_not_repaired_or_carried(tmp_path, fake_plan, monkeypatch):
    original = runtime.FixtureBackend.generate

    def invalid(self, prepared):
        result = original(self, prepared)
        for item in result:
            tokens = [256] + self.tokenizer.encode("```json\n{}\n```") + [257]
            item.update(output_token_ids=tokens, runtime_output_text=self.tokenizer.decode(tokens))
        return result

    monkeypatch.setattr(runtime.FixtureBackend, "generate", invalid)
    run = tmp_path / "invalid"
    runtime.collect(tmp_path, run, diagnostic=True)
    report = audit.reconstruct(tmp_path, run)["report.json"]
    assert report["complete"]
    assert not report["reliability"]["thresholds_passed"]
    assert len(report["errors"]["fields"]) == 2160
    assert len(report["errors"]["actions"]) == 540
    assert all(m["metrics"]["schema_success"]["numerator"] == 0 for m in report["methods"].values())


def test_sealed_package_and_exclusive_write(tmp_path):
    write(tmp_path / "data.json", {"example": 1})
    seal(tmp_path)
    verify_seal(tmp_path)
    with pytest.raises(FileExistsError):
        write(tmp_path / "data.json", {"example": 2})
    (tmp_path / "extra.json").write_text("{}")
    with pytest.raises(ValueError):
        verify_seal(tmp_path)


@pytest.mark.parametrize(
    "field,value",
    [
        ("planned_responses", 270),
        ("model_calls", 540),
        ("heldout_model_calls", 1),
        ("oracle_comparisons", 1),
    ],
)
def test_resealed_dataset_metadata_tampering_is_rejected(tmp_path, field, value):
    import shutil
    from pathlib import Path

    from disastertrace.automated.common import fingerprint
    from disastertrace.local_eval.storage import inventory

    original = Path(__file__).resolve().parents[1] / "artifacts/p3_local_balanced_v1/dataset"
    shutil.copytree(original, tmp_path / "data")
    root = tmp_path / "data"
    plan = read(root / "plan.json")
    plan[field] = value
    (root / "plan.json").write_text(canonical(plan))
    manifest = {
        "schema_version": "local_eval_manifest_v1",
        "files": inventory(root, exclude=("manifest.json",)),
    }
    manifest["package_id"] = fingerprint(manifest)
    (root / "manifest.json").write_text(canonical(manifest))
    with pytest.raises(ValueError, match="metadata"):
        data.verify(root, full=False)


def test_real_source_balanced_data_acceptance():
    from pathlib import Path

    original = Path(__file__).resolve().parents[1] / "artifacts/p3_local_balanced_v1/dataset"
    plan, episodes, slots = data.verify(original)
    assert plan["oracle_comparisons"] == 720
    assert plan["diagnostic_responses"] == 5400
    assert len(episodes) == 36 and len(slots) == 540
