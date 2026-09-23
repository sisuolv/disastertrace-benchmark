"""Review counterexamples exercised through production registries and sessions."""

import copy
import json

import pytest
from test_monitoring_admission import setup_engine
from test_monitoring_joint_targets import context
from test_monitoring_outcomes_v2 import outcome
from test_monitoring_typed_session import typed_fixture

from disastertrace.monitoring_fixed_v1.admission import AdmissionEvent, score_admitted
from disastertrace.monitoring_fixed_v1.contracts import finite
from disastertrace.monitoring_fixed_v1.joint_targets import parse_joint_response
from disastertrace.monitoring_fixed_v1.outcomes import ComparisonContract, OutcomeRegistry
from disastertrace.monitoring_v1.execution import bind_execution, observe_reserved_backend
from disastertrace.monitoring_v1.journal import EventJournal
from disastertrace.monitoring_v1.policies import run_session
from disastertrace.monitoring_v1.resources import BudgetLedger, Cost
from disastertrace.monitoring_v1.session_checkpoint import SessionCoordinator


@pytest.mark.parametrize("export_kind", ["export", "opportunity_rows"])
def test_outcome_exports_do_not_mutate_canonical_results(export_kind):
    engine, _, _ = setup_engine()
    registry = OutcomeRegistry(engine.targets.values())
    row = dict(outcome(), references=[{"source": {"line": 7}}])
    registry.register(row)
    before = copy.deepcopy(registry.export())
    if export_kind == "export":
        exported = registry.export()["payload"]["records"]
    else:
        exported = registry.opportunity_rows(engine.opportunities.values(), {"o": "final.v1"})
    exported[0]["references"][0]["source"]["line"] = 8
    exported[0]["value"] = -100
    assert registry.export() == before
    assert registry.register(row) is False


def test_comparison_export_does_not_expand_permissions():
    comparison = ComparisonContract({"nested": {"bank": "original"}}, {"acquire": [False]})
    before = copy.deepcopy(comparison.export())
    exported = comparison.export()["payload"]
    exported["allowed_interventions"]["acquire"].append(True)
    exported["invariants"]["nested"]["bank"] = "changed"
    assert comparison.export() == before
    with pytest.raises(ValueError):
        comparison.validate({"nested": {"bank": "original"}}, {"acquire": True})


class DeclaredBackend:
    def __init__(self):
        self.execution_contract = {
            "model": "test",
            "weights": "a",
            "tokenizer": "b",
            "adapter": "test.v1",
            "generation": {"temperature": 0},
            "runtime": {"implementation": "test"},
        }

    def __call__(self, system, request, call_id):
        return '{"fact_truth":"unknown","probability":0.3}', {
            "seconds": 0.001,
            "input_tokens": 1,
            "output_tokens": 1,
            "ended_with_eos": True,
        }


def test_execution_binding_is_not_a_reference_to_mutable_backend_config():
    backend = DeclaredBackend()
    bound = bind_execution({}, backend)
    before = copy.deepcopy(bound)
    backend.execution_contract["generation"]["temperature"] = 1
    assert bound == before
    with pytest.raises(ValueError, match="execution contract"):
        bind_execution(bound, backend)


def test_coordinator_restore_rejects_mutated_declared_identity():
    data, bank, config = typed_fixture(forecast_call_cap=1)
    backend = DeclaredBackend()
    session = SessionCoordinator(data, bank, config, backend=backend)
    session.step()
    original = copy.deepcopy(session.config["execution_contract"])
    backend.execution_contract["runtime"]["implementation"] = "replacement"
    assert session.config["execution_contract"] == original
    with pytest.raises(ValueError, match="execution contract"):
        SessionCoordinator.restore(session.snapshot(), data, bank, backend=backend)


@pytest.mark.parametrize("method", ["settle", "settle_observed"])
@pytest.mark.parametrize("tokens", [0, 5, 20])
@pytest.mark.parametrize("restored", [False, True])
def test_unknown_requires_original_response_reconciliation(tmp_path, method, tokens, restored):
    with EventJournal(tmp_path / "ledger.jsonl") as journal:
        ledger = BudgetLedger({"tokens": 100}, journal=journal)
        ledger.reserve("c", Cost(tokens=10), "t")
        binding = {"request_sha256": "a" * 64, "execution_sha256": "b" * 64}
        ledger.bind_request("c", binding)
        ledger.mark_unknown("c", {"error": "disconnected"})
        if restored:
            ledger = BudgetLedger.restore(journal)
        before = copy.deepcopy(ledger.events)
        with pytest.raises(ValueError, match="reconcil"):
            getattr(ledger, method)("c", Cost(tokens=tokens))
        assert ledger.events == before and ledger.reserved.tokens == 10
        proof = {**binding, "response_sha256": "c" * 64, "observed_at": 20}
        with pytest.raises(ValueError):
            ledger.reconcile_unknown("c", Cost(tokens=tokens), dict(proof, request_sha256="d" * 64))
        assert ledger.reconcile_unknown("c", Cost(tokens=tokens), proof)
        assert ledger.reconcile_unknown("c", Cost(tokens=tokens), proof) is False
        assert ledger.reserved.tokens == 0 and ledger.spent.tokens == tokens
        assert BudgetLedger.restore(journal).events == ledger.events


@pytest.mark.parametrize("history", [[True, False], [False, True, False]])
def test_scoring_rejects_illegal_initial_or_transient_intervention(tmp_path, history):
    path = tmp_path / "admission.jsonl"
    with EventJournal(path) as journal:
        engine, _, events = setup_engine(
            journal=journal,
            experiment={
                "invariants": {"data": "frozen"},
                "interventions": {"acquire": history[0]},
            },
        )
        for i, value in enumerate(history[1:]):
            events.append(
                AdmissionEvent(
                    "change-" + str(i),
                    61 + i,
                    "policy_intervention",
                    {
                        "parent_checkpoint_sha256": "a" * 64,
                        "changes": {"acquire": value},
                    },
                )
            )
        engine.run(events, until=90)
    row = {"opportunity_id": "o", **outcome()}
    comparison = ComparisonContract({"data": "frozen"}, {"acquire": [False]})
    with pytest.raises(ValueError, match="intervention"):
        score_admitted([row], {"arm": path}, comparison=comparison)
    allowed = ComparisonContract({"data": "frozen"}, {"acquire": [False, True]})
    assert score_admitted([row], {"arm": path}, comparison=allowed)["scores"]["settled"] == 1


def test_scoring_checks_actual_protocol_even_for_one_arm(tmp_path):
    path = tmp_path / "protocol.jsonl"
    with EventJournal(path) as journal:
        engine, _, events = setup_engine(
            journal=journal,
            protocol="persistent_override",
            experiment={
                "invariants": {"data": "frozen"},
                "interventions": {"protocol": "base_bound_override"},
            },
        )
        engine.run(events, until=90)
    comparison = ComparisonContract({"data": "frozen"}, {"protocol": ["base_bound_override"]})
    with pytest.raises(ValueError, match="protocol"):
        score_admitted([{"opportunity_id": "o", **outcome()}], {"arm": path}, comparison=comparison)


@pytest.mark.parametrize("duration", [1e308, 10**400])
def test_huge_duration_is_recorded_as_unknown_without_losing_denominator(duration):
    data, bank, config = typed_fixture(forecast_call_cap=1, model_call_budget=1)

    def backend(*args):
        return '{"fact_truth":"unknown","probability":0.2}', {
            "seconds": duration,
            "input_tokens": 1,
            "output_tokens": 1,
            "ended_with_eos": True,
        }

    report = run_session(data, bank, config, backend=backend)
    assert len(report["snapshots"]) == len(data["opportunities"])
    assert report["calls"][0]["admission_status"] == "invalid_backend_response"
    assert report["resource_reserved"]["tokens"] > 0


@pytest.mark.parametrize("duration", [1e308, 10**400])
def test_raw_backend_huge_duration_retains_unknown_reservation(duration):
    ledger = BudgetLedger({"tokens": 100, "compute_ms": 1000})
    ledger.reserve("c", Cost(tokens=10, compute_ms=100), "t")

    def backend(*args):
        return "{}", {"seconds": duration, "input_tokens": 1, "output_tokens": 1}

    _, _, _, status = observe_reserved_backend(backend, "system", {}, "c", ledger)
    assert status == "unknown_execution"
    assert ledger.entries["c"]["outcome"] == "unknown_execution"
    assert ledger.reserved.tokens == 10


@pytest.mark.parametrize("isolation", ["public_schedule", "actual_cost_clock"])
def test_failed_execution_cannot_finish_before_observed_wait(monkeypatch, isolation):
    from disastertrace.monitoring_fixed_v1 import adaptive

    data, bank, config = typed_fixture(
        forecast_call_cap=1,
        model_call_budget=1,
        isolation_mode=isolation,
        call_compute_cap_ms=1000,
        public_call_slot_ms=30000,
    )
    clock = [0.0]
    monkeypatch.setattr(adaptive.time, "perf_counter", lambda: clock[0])

    def backend(*args):
        clock[0] += 40
        raise RuntimeError("observed slow failure")

    report = run_session(data, bank, config, backend=backend)
    call = report["calls"][0]
    assert call["persisted_at"] - call["started_at"] >= 40_000_000
    assert report["resource_reserved"]["tokens"] > 0
    assert len(report["snapshots"]) == len(data["opportunities"])


def test_huge_joint_probability_is_a_protocol_value_error():
    raw = json.dumps({"answers": [{"target_id": "t0", "probability": 10**400}]})
    with pytest.raises(ValueError, match="Probability"):
        parse_joint_response(raw, context(), ["t0"], head="f_only")


def test_finite_rejects_unrepresentable_integer_without_overflow():
    assert not finite(10**400)
    assert finite(10) and finite(0.2)


@pytest.mark.parametrize("duration", [1e308, 10**400])
def test_source_transport_huge_duration_is_also_an_unknown_receipt(duration):
    from disastertrace.monitoring_v1.source_execution import observe_source

    class Source:
        def __init__(self):
            self.source_contract = {"transport": "synthetic-bound-source.v1"}

        def __call__(self, request, receipt_id):
            return {"status": "available"}, {"seconds": duration, "elapsed_seconds": duration}

    ledger = BudgetLedger({"requests": 2, "bytes": 1000, "compute_ms": 1000})
    ledger.reserve("q", Cost(requests=1, bytes=100, compute_ms=10), "t")
    _, _, _, status, _ = observe_source(
        Source(), {"catalog": {"latency_ms": 1}}, "q", ledger, {"status": "available"}
    )
    assert status == "unknown_execution"
    assert ledger.reserved.requests == 1 and not ledger.entries["q"]["settled"]
