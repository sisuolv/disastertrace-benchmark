"""Stress factors must preserve answers, opportunities and isolated histories."""

from copy import deepcopy
from pathlib import Path

import pytest

from disastertrace.automated.common import canonical, read_jsonl
from disastertrace.constrained_eval import adapter, contract
from disastertrace.constrained_eval import audit as prior_audit
from disastertrace.controlled import compiler, renderer
from disastertrace.controlled.schema import METHODS, empty_decision
from disastertrace.local_eval import data as balanced
from disastertrace.local_eval.storage import read, seal, write
from disastertrace.stress_eval import audit, data, execution, runtime

PROJECT = Path(__file__).resolve().parents[1]
BASE = PROJECT / "artifacts/p3_local_balanced_v1/execution/dataset"
CANDIDATES = PROJECT / "artifacts/p3_local_balanced_v1/stress_offline"


@pytest.fixture(scope="module")
def base():
    return balanced.verify(BASE, full=False)[1]


@pytest.fixture(scope="module")
def candidates():
    return read_jsonl(CANDIDATES / "episodes.jsonl")


@pytest.fixture(scope="module")
def tokenizer():
    return runtime.tokenizer_for(BASE.parent)


@pytest.mark.parametrize("factor", data.FACTORS)
def test_all_candidates_gold_and_wave_schedule(base, candidates, factor):
    episodes = data.select(base, candidates, factor)
    content = data.core(base, episodes, balanced.schedule(base))
    assert len(episodes) == 36
    assert len(content["gold_equivalence"]) == 180
    assert all(
        row["base_reference_sha256"] == row["stress_reference_sha256"]
        for row in content["gold_equivalence"]
    )
    slots = content["schedule"]
    assert len(slots) == len({s["slot_id"] for s in slots}) == 540
    assert {s["slot_id"] for s in slots}.isdisjoint(s["base_slot_id"] for s in slots)
    for offset in range(0, 540, 12):
        batch = slots[offset : offset + 12]
        assert len({s["trajectory_id"] for s in batch}) == 12
        assert len({s["checkpoint_id"] for s in batch}) == 1
    zero = sum(
        r["added_records"] == r["added_deliveries"] == 0 for r in content["effective_factor_counts"]
    )
    assert zero == (6 if factor == "revision_chain" else 0)


@pytest.mark.parametrize(
    "mutation", ["missing", "duplicate", "reorder", "changed", "foreign-factor"]
)
def test_candidate_substitution_rejected(base, candidates, mutation):
    items = deepcopy(candidates)
    factor = data.FACTORS[0]
    if mutation == "missing":
        items.pop()
    elif mutation == "duplicate":
        items[-1] = items[0]
    elif mutation == "reorder":
        items.reverse()
    elif mutation == "changed":
        items[-1]["records"][0]["issued_at"] = "2020-01-01T00:00:00+00:00"
    else:
        factor = "posthoc-error-subset"
    with pytest.raises(ValueError):
        data.select(base, items, factor)


@pytest.mark.parametrize("method", METHODS)
def test_factor_metadata_and_future_records_do_not_leak(base, candidates, method):
    episodes = data.select(base, candidates, "irrelevant_scope")
    ep = episodes[0]
    request = renderer.render_request(ep, "c1", method=method)
    raw = canonical(request)
    for name in (
        "base_episode_id",
        "base_slot_id",
        "factor",
        "profile",
        "gold_equivalence",
        "inherited_values",
    ):
        assert '"' + name + '"' not in raw
    added = {r["record_id"] for r in ep["records"]} - {r["record_id"] for r in base[0]["records"]}
    assert not any(record_id in raw for record_id in added)
    assert compiler.reference_at(ep, "c1") == compiler.reference_at(base[0], "c1")


@pytest.fixture(scope="module")
def dataset(tmp_path_factory):
    path = tmp_path_factory.mktemp("stress-data") / "dataset"
    data.prepare(BASE, CANDIDATES, path, factor="revision_chain")
    return path


def test_full_profile_regeneration_and_denominators(dataset):
    plan, _, slots = data.verify(dataset)
    assert plan["zero_effect_episodes"] == 6 and len(slots) == 540
    checks = read(dataset / "diagnostics.json")
    assert checks["oracle_comparisons"] == 540
    assert checks["diagnostic_responses"] == 5400 and checks["model_calls"] == 0
    assert all(v["metric_denominators"] == 116 for v in checks["opportunity_checks"].values())
    with pytest.raises(ValueError, match="preserve"):
        data.prepare(BASE, CANDIDATES, dataset, factor="revision_chain")


@pytest.fixture(scope="module")
def frozen(dataset, tmp_path_factory):
    path = tmp_path_factory.mktemp("stress-freeze") / "execution"
    execution.freeze(PROJECT / "artifacts/p4_constrained_output_v1/execution_live", dataset, path)
    return path


def test_offline_freeze_binds_data_parent_and_unchanged_settings(frozen):
    plan, episodes, slots = execution.verify(frozen)
    assert plan["scope"] == execution.SCOPE and plan["run_path"] is None
    assert plan["settings"] == adapter.SETTINGS
    assert plan["dataset_content_id"] != plan["base_dataset_content_id"]
    assert len(episodes) == 36 and len(slots) == 540
    with pytest.raises(ValueError, match="offline candidate"):
        runtime.collect(frozen, frozen.parent / "forbidden-model-call")


@pytest.mark.parametrize("mutation", ["scope", "factor-metadata", "parent", "loaded-source"])
def test_execution_tampering_rejected_after_resealing(frozen, tmp_path, monkeypatch, mutation):
    import shutil

    from disastertrace.automated.common import fingerprint

    path = tmp_path / "execution"
    shutil.copytree(frozen, path)
    plan = read(path / "execution.json")
    if mutation == "scope":
        plan["scope"]["model_calls"] = 1
    elif mutation == "factor-metadata":
        plan["stress_profile"].pop("factor")
    elif mutation == "parent":
        plan["base_dataset_content_id"] = "other-base"
    else:
        monkeypatch.setattr(execution, "source_inventory", dict)
    plan["execution_id"] = fingerprint({k: v for k, v in plan.items() if k != "execution_id"})
    (path / "execution.json").write_text(canonical(plan))
    (path / "manifest.json").unlink()
    seal(path)
    with pytest.raises(ValueError):
        execution.verify(path)


@pytest.fixture
def fake_execution(monkeypatch, tmp_path, base, candidates, tokenizer):
    episodes = data.select(base, candidates, "late_stale_replay")
    slots = data.schedule(episodes, balanced.schedule(base))
    plan = {
        "execution_id": "test-stress-execution",
        "dataset_content_id": "test-stress-data",
        "base_dataset_content_id": "test-base",
        "stress_profile": {"factor": "late_stale_replay", "level": 4},
        "settings": deepcopy(adapter.SETTINGS),
        "scope": execution.SCOPE,
        "run_path": None,
        "deadline_utc": None,
        "environment_sha256": "test-environment",
        "reliability_rule": execution.RELIABILITY,
    }
    monkeypatch.setattr(execution, "verify", lambda *a, **k: (plan, episodes, slots))

    class Fixture:
        origin = "diagnostic_stress_fixture"

        def __init__(self, path):
            self.tokenizer = tokenizer
            self.observation = {"constraint": contract.identity()}

        generate = runtime.FixtureBackend.generate

    monkeypatch.setattr(runtime, "FixtureBackend", Fixture)
    monkeypatch.setattr(audit, "tokenizer_for", lambda *a, **k: tokenizer)
    monkeypatch.setattr(runtime, "tokenizer_for", lambda *a, **k: tokenizer)
    return plan, slots


def test_complete_diagnostic_and_model_origin_rejection(tmp_path, fake_execution):
    run, report = tmp_path / "run", tmp_path / "report"
    runtime.collect(tmp_path, run, diagnostic=True)
    result = audit.report(tmp_path, run, report)
    assert result["received"] == 540 and result["model_calls"] == 0
    assert audit.report(tmp_path, run, report, verify=True) == result
    content = read(report / "report.json")
    assert content["errors"] == {"fields": [], "actions": []}
    assert content["stress_profile"]["factor"] == "late_stale_replay"
    with pytest.raises(ValueError, match="diagnostics cannot"):
        audit.audit(tmp_path, run, require_model=True)
    with pytest.raises(FileExistsError):
        runtime.collect(tmp_path, run, diagnostic=True)
    with pytest.raises(ValueError, match="offline candidate"):
        runtime.collect(tmp_path, tmp_path / "live")


def test_stopped_prefix_retains_all_opportunities(tmp_path, fake_execution, monkeypatch):
    def stop(self, prepared):
        raise RuntimeError("intent persisted but no response returned")

    monkeypatch.setattr(runtime.FixtureBackend, "generate", stop)
    run = tmp_path / "stopped"
    with pytest.raises(RuntimeError, match="intent persisted"):
        runtime.collect(tmp_path, run, diagnostic=True)
    files = audit.reconstruct(tmp_path, run)
    assert files["audit.json"]["pending_slots"] == list(range(12))
    assert files["audit.json"]["unsubmitted"] == 528
    assert (
        sum(
            m["metrics"]["schema_success"]["denominator"]
            for m in files["report.json"]["methods"].values()
        )
        == 540
    )


def test_predispatch_context_failure_is_unattempted_and_reported(
    tmp_path, fake_execution, monkeypatch
):
    original = adapter.prepare

    def reject(request, slot, tokenizer, settings):
        if slot["slot_index"] == 12:
            raise ValueError("local context budget would require truncation")
        return original(request, slot, tokenizer, settings)

    monkeypatch.setattr(adapter, "prepare", reject)
    run = tmp_path / "context-stop"
    with pytest.raises(ValueError, match="truncation"):
        runtime.collect(tmp_path, run, diagnostic=True)
    report = audit.reconstruct(tmp_path, run)["report.json"]
    assert report["attempted"] == report["received"] == 12
    assert report["unsubmitted"] == 528 and not report["complete"]
    assert "truncation" in read(run / "completion.json")["stop_reason"]


def test_wrong_but_valid_answers_propagate_without_repair(tmp_path, fake_execution, monkeypatch):
    original = runtime.FixtureBackend.generate

    def wrong(self, prepared):
        outputs = original(self, prepared)
        for row in outputs:
            ids = (
                self.tokenizer.encode("</think>")
                + self.tokenizer.encode(contract.serialize_fixture(empty_decision()))
                + [self.tokenizer.eos_token_id]
            )
            row.update(output_token_ids=ids, runtime_output_text=self.tokenizer.decode(ids))
        return outputs

    monkeypatch.setattr(runtime.FixtureBackend, "generate", wrong)
    run = tmp_path / "wrong"
    runtime.collect(tmp_path, run, diagnostic=True)
    report = audit.reconstruct(tmp_path, run)["report.json"]
    assert report["complete"] and report["reliability"]["thresholds_passed"]
    assert all(
        m["metrics"]["all_correct_checkpoints"]["numerator"] < 180
        for m in report["methods"].values()
    )
    assert all(
        read(p)["state_after"] == empty_decision() for p in (run / "captures").glob("*.json")
    )


@pytest.mark.parametrize("mutation", ["origin", "carrier", "tokens", "factor"])
def test_capture_or_factor_tampering_rejected(tmp_path, fake_execution, mutation):
    run = tmp_path / "tampered"
    runtime.collect(tmp_path, run, diagnostic=True)
    path = run / "captures/0000.json"
    item = read(path)
    if mutation == "origin":
        item["origin"] = "local_model_vllm_constrained_v1"
    elif mutation == "carrier":
        item["state_after"] = None
    elif mutation == "tokens":
        item["result"]["output_token_ids"] += [99]
    else:
        item["execution_id"] = "different-factor-execution"
    path.write_text(canonical(item))
    with pytest.raises(ValueError):
        audit.audit(tmp_path, run)


def test_prior_auditor_rejects_stress_origin(tmp_path, fake_execution, monkeypatch):
    plan, slots = fake_execution
    monkeypatch.setattr(prior_audit.execution, "verify", lambda *a, **k: (plan, [], slots))
    run = tmp_path / "claim-only"
    write(
        run / "claim.json",
        {"started_at": "2026-09-08T00:00:00+00:00", "origin": "diagnostic_stress_fixture"},
    )
    with pytest.raises(ValueError, match="unrecognized capture origin"):
        prior_audit.audit(tmp_path, run)


def test_dataset_mutation_rejected_even_after_resealing(dataset, tmp_path):
    import shutil

    path = tmp_path / "altered"
    shutil.copytree(dataset, path)
    item = read(path / "plan.json")
    item["zero_effect_episodes"] = 0
    (path / "plan.json").write_text(canonical(item))
    (path / "manifest.json").unlink()
    seal(path)
    with pytest.raises(ValueError, match="metadata or identity"):
        data.verify(path, full=False)
