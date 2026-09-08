"""Constrained decoding must not solve or hide the scored task."""

import json
import shutil
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from disastertrace.automated.common import canonical, strict_json
from disastertrace.constrained_eval import adapter, audit, contract, execution, runtime
from disastertrace.constrained_eval.grammar import GrammarReplay
from disastertrace.controlled import compiler, generator, renderer
from disastertrace.controlled.schema import FIELDS, empty_decision, parse_decision
from disastertrace.local_eval import adapter as free_adapter
from disastertrace.local_eval import audit as free_audit
from disastertrace.local_eval.storage import read

PROJECT = Path(__file__).resolve().parents[1]
PARENT = PROJECT / "artifacts/p3_local_balanced_v1/execution"


@pytest.fixture(scope="module")
def candidate(tmp_path_factory):
    path = tmp_path_factory.mktemp("constrained") / "execution"
    execution.freeze(PARENT, path)
    return path


@pytest.fixture(scope="module")
def tokenizer():
    return runtime.tokenizer_for(PARENT)


@pytest.fixture(scope="module")
def grammar(tokenizer):
    return GrammarReplay(tokenizer, read(PARENT / "model_config/config.json")["vocab_size"])


@pytest.fixture(scope="module")
def diagnostic_run(candidate, tmp_path_factory):
    run = tmp_path_factory.mktemp("replay") / "run"
    runtime.collect(candidate, run, diagnostic=True)
    return run


def sample():
    ep = generator.micro_episodes()[0]
    return compiler.reference_at(ep, "c1")


def test_schema_has_no_private_or_conditional_constraints():
    text = contract.schema_text()
    for forbidden in (
        "const",
        "minimum",
        "maximum",
        "pattern",
        "if",
        "then",
        "oneOf",
        "anyOf",
        "allOf",
        "100",
        "record-",
        "Gold",
    ):
        assert '"' + forbidden + '"' not in text
    assert list(contract.schema()["properties"]) == ["state", "action"]
    assert contract.identity()["request_dependent"] is False
    assert contract.identity()["gold_dependent"] is False


@pytest.mark.parametrize("action", contract.ACTIONS)
def test_grammar_accepts_every_action_independently(grammar, action):
    decision = sample()
    decision["action"] = action
    assert grammar.check_text(contract.serialize_fixture(decision))["terminated"]


@pytest.mark.parametrize(
    "mutation",
    [
        "unknown-with-value",
        "known-null",
        "out-of-range",
        "too-precise",
        "negative-line",
        "arbitrary-id",
        "empty-id",
        "stale-value",
    ],
)
def test_grammar_does_not_perform_scored_checks(grammar, mutation):
    decision = sample()
    slot = decision["state"][FIELDS[0]]
    if mutation == "unknown-with-value":
        slot["status"] = "unknown"
    elif mutation == "known-null":
        slot["value"] = None
    elif mutation == "out-of-range":
        slot["value"] = 9999
    elif mutation == "too-precise":
        slot["value"] = 123.4567
    elif mutation == "negative-line":
        slot["evidence"][0]["line"] = -8
    elif mutation == "arbitrary-id":
        slot["evidence"][0] = {"record_id": "not-delivered-not-a-gold-id", "line": 99999}
    elif mutation == "empty-id":
        slot["evidence"][0]["record_id"] = ""
    else:
        slot["value"] = 1
    raw = contract.serialize_fixture(decision)
    assert grammar.check_text(raw)["terminated"]
    if mutation not in ("arbitrary-id", "stale-value"):
        assert contract.inspect(raw)["task_contract_valid"] is False


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "{}",
        '{"state":{},"action":"prepare"}',
        '{"state":',
        "```json\n{}\n```",
        '{"state":{},"state":{}}',
    ],
)
def test_malformed_or_incomplete_output_not_repaired(grammar, raw):
    result = grammar.check_text(raw)
    assert not result["accepted"]
    assert not contract.inspect(raw)["task_contract_valid"]


def test_property_order_is_decoder_restriction_not_gold_change(grammar):
    decision = sample()
    assert parse_decision(canonical(decision)) == parse_decision(
        contract.serialize_fixture(decision)
    )
    assert grammar.check_text(contract.serialize_fixture(decision))["terminated"]
    assert not grammar.check_text(canonical(decision))["accepted"]


def test_integer_lexical_difference_reported(grammar):
    decision = sample()
    decision["state"][FIELDS[0]]["evidence"][0]["line"] = 2.0
    contract.validate_structure(decision)
    assert not contract.inspect(contract.serialize_fixture(decision))["task_contract_valid"]


def test_all_gold_schema_compatibility(grammar):
    for ep in generator.micro_episodes():
        for cp in ep["checkpoints"]:
            raw = contract.serialize_fixture(compiler.reference_at(ep, cp["checkpoint_id"]))
            assert all(contract.inspect(raw).values())
            assert grammar.check_text(raw)["terminated"]


@pytest.mark.parametrize("method", ["snapshot", "structured_state", "answer_history"])
def test_only_decoding_metadata_differs_from_free_prompt(tokenizer, method):
    ep = generator.micro_episodes()[0]
    request = renderer.render_request(ep, "c1", method=method)
    slot = {"slot_id": method + ":test:c1"}
    before = deepcopy(request)
    free = free_adapter.prepare(request, slot, tokenizer)
    constrained = adapter.prepare(request, slot, tokenizer)
    for name in (
        "messages",
        "prompt",
        "prompt_token_ids",
        "output_contract",
        "public_request_sha256",
    ):
        assert free[name] == constrained[name]
    assert {k: v for k, v in constrained["sampling"].items() if k != "guided_decoding"} == free[
        "sampling"
    ]
    assert request == before


def test_guard_preexisting_close_think_does_not_sanitize_carrier(tokenizer):
    ep = generator.micro_episodes()[0]
    prior = sample()
    prior["state"][FIELDS[0]]["evidence"][0]["record_id"] = "</think>"
    request = renderer.render_request(ep, "c2", method="structured_state", previous=prior)
    original = deepcopy(request)
    with pytest.raises(ValueError, match="prematurely"):
        adapter.prepare(request, {"slot_id": "s"}, tokenizer)
    assert request == original


def test_real_vllm_parameter_adapter_and_no_fallback(tokenizer):
    from vllm.engine.arg_utils import EngineArgs

    ep = generator.micro_episodes()[0]
    prepared = adapter.prepare(
        renderer.render_request(ep, "c0", method="snapshot"), {"slot_id": "s"}, tokenizer
    )
    params = adapter.sampling_params(prepared)
    assert params.guided_decoding.json == contract.schema_text()
    assert params.guided_decoding.disable_fallback is True
    args = EngineArgs(model=str(PARENT / "model_config"), **adapter.ENGINE_OPTIONS)
    assert args.reasoning_parser == "qwen3"
    assert args.guided_decoding_disable_fallback is True


def test_actual_vllm_reasoning_gate_and_final_mask(tokenizer, grammar):
    import torch
    from vllm.reasoning.qwen3_reasoning_parser import Qwen3ReasoningParser
    from vllm.v1.structured_output import StructuredOutputManager
    from vllm.v1.structured_output.backend_xgrammar import XgrammarGrammar

    manager = object.__new__(StructuredOutputManager)
    manager.reasoner = Qwen3ReasoningParser(tokenizer)
    manager._full_mask = torch.tensor(-1, dtype=torch.int32)
    manager._grammar_bitmask = grammar.xgr.allocate_token_bitmask(2, grammar.vocab_size)
    g = XgrammarGrammar(
        matcher=grammar.xgr.GrammarMatcher(grammar.compiled),
        vocab_size=grammar.vocab_size,
        ctx=grammar.compiled,
    )
    request = SimpleNamespace(
        use_structured_output=True,
        prompt_token_ids=tokenizer.encode("<think>"),
        all_token_ids=tokenizer.encode("<think>Arbitrary reasoning without JSON."),
        structured_output_request=SimpleNamespace(reasoning_ended=None, grammar=g),
    )
    assert manager.should_fill_bitmask(request) is False
    assert manager.should_advance(request) is False
    manager._fill_bitmasks([(g, 0, False), (g, 1, True)])
    assert bool(torch.all(manager._grammar_bitmask[0] == -1))
    assert not bool(torch.all(manager._grammar_bitmask[1] == -1))
    request.all_token_ids += tokenizer.encode("</think>")
    assert manager.should_advance(request) is False
    assert g.num_processed_tokens == 0
    assert manager.should_fill_bitmask(request) is True
    assert manager.should_advance(request) is True
    assert g.accept_tokens(
        "test",
        tokenizer.encode(contract.serialize_fixture(empty_decision())) + [tokenizer.eos_token_id],
    )
    assert g.is_terminated()
    assert not torch.cuda.is_initialized()


def test_missing_reasoning_delimiter_remains_a_failure(tokenizer, grammar):
    tokens = tokenizer.encode("Unconstrained reasoning that never ends.")
    assert grammar.check_output(tokens)["accepted"] is None
    assert adapter.extract(tokens, tokenizer)["extraction_error"]


def test_schema_typing_agrees_with_jsonschema():
    from jsonschema import Draft202012Validator

    validator = Draft202012Validator(contract.schema())
    for value in (
        sample(),
        empty_decision(),
        {"state": {}},
        {"state": sample()["state"], "action": []},
    ):
        raw = json.dumps(value)
        assert validator.is_valid(value) == contract.inspect(raw)["structure_valid"]


def test_full_diagnostic_and_independent_report(candidate, diagnostic_run, tmp_path):
    run, report = diagnostic_run, tmp_path / "report"
    result = audit.report(candidate, run, report)
    assert result["received"] == 540 and result["model_calls"] == 0
    assert audit.report(candidate, run, report, verify=True) == result
    summary = read(report / "report.json")
    assert summary["reliability"]["thresholds_passed"]
    assert not summary["reliability"]["measured_model_reliability"]
    assert summary["format_layers"]["snapshot"]["task_contract_valid"] == {
        "numerator": 180,
        "denominator": 180,
    }
    with pytest.raises(ValueError, match="relabeled"):
        audit.audit(candidate, run, require_model=True)
    with pytest.raises(ValueError):
        free_audit.audit(candidate, run)
    with pytest.raises(FileExistsError):
        runtime.collect(candidate, run, diagnostic=True)


def test_offline_plan_cannot_dispatch(candidate, tmp_path):
    with pytest.raises(ValueError, match="offline candidate"):
        runtime.collect(candidate, tmp_path / "production")
    assert not (tmp_path / "production").exists()


@pytest.mark.parametrize(
    "target",
    [
        "constraint.json",
        "model_config/tokenizer_config.json",
        "execution.json",
        "implementation_source/src/disastertrace/constrained_eval/adapter.py",
    ],
)
def test_tampered_frozen_identity_rejected(candidate, tmp_path, target):
    copied = tmp_path / "execution"
    shutil.copytree(candidate, copied)
    path = copied / target
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="content/inventory"):
        execution.verify(copied)


def test_mutant_outputs_invalid_and_truncated_keep_full_denominators(
    candidate, tmp_path, monkeypatch
):
    tokenizer = runtime.tokenizer_for(candidate)
    original = runtime.FixtureBackend

    class Faults(original):
        def generate(self, prepared):
            outputs = super().generate(prepared)
            for prep, result in zip(prepared, outputs):
                request = strict_json(prep["messages"][1]["content"])
                decision = parse_decision(
                    adapter.extract(result["output_token_ids"], tokenizer)["content"]
                )
                known = decision["state"][FIELDS[0]]["status"] == "known"
                if not known:
                    continue
                method = request["method"]
                if method == "snapshot":
                    decision["action"] = "request_evidence"
                    raw = contract.serialize_fixture(decision)
                    result["output_token_ids"] = (
                        tokenizer.encode("</think>")
                        + tokenizer.encode(raw)
                        + [tokenizer.eos_token_id]
                    )
                elif method == "structured_state":
                    result["output_token_ids"] = tokenizer.encode("</think>{invalid") + [
                        tokenizer.eos_token_id
                    ]
                else:
                    result["output_token_ids"] = (
                        tokenizer.encode("x") * adapter.SETTINGS["max_tokens"]
                    )
                    result["finish_reason"] = "length"
                result["runtime_output_text"] = tokenizer.decode(
                    result["output_token_ids"], skip_special_tokens=False
                )
            return outputs

    monkeypatch.setattr(runtime, "FixtureBackend", Faults)
    run = tmp_path / "faults"
    runtime.collect(candidate, run, diagnostic=True)
    files = audit.reconstruct(candidate, run)
    report = files["report.json"]
    for method in ("snapshot", "structured_state", "answer_history"):
        assert report["methods"][method]["metrics"]["schema_success"]["denominator"] == 180
    assert report["methods"]["snapshot"]["metrics"]["schema_success"]["numerator"] == 180
    assert report["errors"]["actions"]
    assert report["finish_reasons"]["length"] > 0
    assert report["extraction_errors"]["missing_or_multiple_reasoning_delimiters"] > 0
    last_valid = {}
    for trace in files["trace.json"]:
        key = (trace["method"], trace["episode_id"])
        if trace["status"] == "invalid":
            assert trace["state_after"] == last_valid.get(key)
        else:
            last_valid[key] = trace["state_after"]
        if trace["method"] == "snapshot" and trace["state_after"]:
            assert trace["state_after"]["action"] == "request_evidence"


@pytest.mark.parametrize(
    "mutation", ["origin", "tokens", "validity", "carrier", "guide", "runtime-constraint"]
)
def test_capture_and_preparation_tampering_rejected(candidate, diagnostic_run, tmp_path, mutation):
    run = tmp_path / "tampered"
    shutil.copytree(diagnostic_run, run)
    path = run / "captures/0000.json"
    if mutation == "origin":
        path = run / "claim.json"
    elif mutation == "guide":
        path = run / "batches/000.json"
    elif mutation == "runtime-constraint":
        path = run / "runtime.json"
    value = read(path)
    if mutation == "origin":
        value["origin"] = "local_model_vllm_constrained_v1"
    elif mutation == "tokens":
        value["result"]["output_token_ids"][0] += 1
    elif mutation == "validity":
        value["output_validity"]["structure_valid"] = False
    elif mutation == "carrier":
        value["state_after"]["action"] = "prepare"
    elif mutation == "guide":
        value["prepared"][0]["sampling"]["guided_decoding"]["json"] = "{}"
    else:
        value["observation"]["constraint"]["schema_sha256"] = "0" * 64
    path.write_text(canonical(value))
    with pytest.raises(ValueError):
        audit.audit(candidate, run)


def test_unresolved_batch_is_scored_without_retry(candidate, tmp_path, monkeypatch):
    original = runtime.FixtureBackend

    class Interrupted(original):
        calls = 0

        def generate(self, prepared):
            self.calls += 1
            if self.calls == 2:
                raise RuntimeError("diagnostic intentional interruption")
            return super().generate(prepared)

    monkeypatch.setattr(runtime, "FixtureBackend", Interrupted)
    run = tmp_path / "interrupted"
    with pytest.raises(RuntimeError, match="intentional interruption"):
        runtime.collect(candidate, run, diagnostic=True)
    files = audit.reconstruct(candidate, run)
    summary = files["audit.json"]
    assert summary["attempted"] == 24 and summary["received"] == 12
    assert len(summary["pending_slots"]) == 12 and summary["unsubmitted"] == 516
    assert not summary["complete"]
    assert all(
        score["metrics"]["schema_success"]["denominator"] == 180
        for score in files["report.json"]["methods"].values()
    )
    with pytest.raises(FileExistsError):
        runtime.collect(candidate, run, diagnostic=True)


def test_new_live_scope_has_fresh_claim_and_diagnostic_does_not_consume_it(tmp_path):
    path, run = tmp_path / "execution", tmp_path / "production"
    plan = execution.freeze(
        PARENT, path, live=True, run_path=run, deadline_utc="2030-01-01T00:00:00+00:00"
    )
    assert execution.verify(path)[0] == plan
    assert plan["scope"]["model_calls"] == 540
    assert plan["authorization"] == execution.LIVE_AUTHORIZATION
    assert plan["retries"] == plan["diagnostic_probes"] == 0
    with pytest.raises(ValueError, match="consume production"):
        runtime.collect(path, run, diagnostic=True)
    assert not run.exists()
    with pytest.raises(ValueError, match="canonical"):
        runtime.collect(path, tmp_path / "noncanonical")
    assert not (tmp_path / "noncanonical").exists()
