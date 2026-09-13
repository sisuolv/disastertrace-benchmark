"""Typed acquisition, admission and whole-controller recovery regressions."""

import copy
import json

import pytest
from test_monitoring_admission import complete, setup_engine
from test_monitoring_policies import fixture

from disastertrace.monitoring_fixed_v1.adaptive import TypedAviationRuntime
from disastertrace.monitoring_fixed_v1.admission import AdmissionEngine, AdmissionEvent
from disastertrace.monitoring_fixed_v1.contracts import EvidenceBundle
from disastertrace.monitoring_fixed_v1.support_bridge import native_slot_support
from disastertrace.monitoring_v1.policies import run_session
from disastertrace.monitoring_v1.session_checkpoint import SessionCoordinator


def typed_fixture(**changes):
    data, bank, config = fixture()
    config.update(session_runtime="typed_admission_v1", typed_head="joint", **changes)
    return data, bank, config


def backend(system, request, call_id):
    assert request["schema"] == "disastertrace.frozen_evidence.v1"
    assert "expected_e" not in json.dumps(request)
    assert "fact_truth" in system
    return '{"fact_truth":"unknown","probability":0.3}', {
        "seconds": 0.01,
        "input_tokens": 20,
        "output_tokens": 10,
        "ended_with_eos": True,
    }


def test_typed_step_and_restore_equal_direct_program_session():
    data, bank, config = typed_fixture()
    direct = run_session(data, bank, config)
    session = SessionCoordinator(data, bank, config)
    session.step()
    restored = SessionCoordinator.restore(session.snapshot(), data, bank)
    assert restored.finish() == direct
    assert direct["calls"]
    assert all(c["head"] == "program" for c in direct["calls"])
    assert all(s["forecast"]["units"] == "probability" for s in direct["snapshots"])
    assert all(a["status"] == "accepted" for a in direct["attempts"] if "call_id" in a)


@pytest.mark.parametrize("authorization", ["target_private", "session_shared"])
def test_bundles_bind_actual_paid_cache_receipts_and_native_support(authorization):
    data, bank, config = typed_fixture(authorization_mode=authorization)
    report = run_session(data, bank, config, backend=backend)
    settled = {e["receipt_id"]: e for e in report["resource_events"] if e["event"] != "reserve"}
    source = {r["receipt_id"]: r for r in report["source_receipts"]}
    saw_asset = False
    for call in report["calls"]:
        b = EvidenceBundle.restore(call["bundle"])
        row = b.policy_view()
        assert native_slot_support(b)["status"] == call["expected_e_from_disclosed_products"]
        for receipt in row["receipts"]:
            saw_asset = True
            assert receipt["cost"] == settled[receipt["receipt_id"]]["actual"]
            assert receipt["started_at"] == source[receipt["receipt_id"]]["started_at"]
            assert receipt["completed_at"] <= call["started_at"]
        for asset in row["assets"]:
            if authorization == "target_private":
                assert asset["entitlements"] == [row["target"]["target_id"]]
    assert saw_asset
    assert all(c["admission_status"] == "accepted" for c in report["calls"])


def test_captured_prefix_calls_are_not_reissued_by_typed_branch():
    data, bank, config = typed_fixture()
    called = []

    def unique(*args):
        assert args[2] not in called
        called.append(args[2])
        return backend(*args)

    first = SessionCoordinator(data, bank, config, backend=unique)
    first.step()
    snapshot = first.snapshot()
    restored = SessionCoordinator.restore(snapshot, data, bank, backend=unique)
    restored.finish()
    assert len(called) == len(restored.report["calls"])
    waiting = SessionCoordinator.restore(snapshot, data, bank, backend=unique)
    waiting.step({"acquire": False, "predict": False})
    assert waiting.report["resource_spent"] == first.report["resource_spent"]
    assert snapshot == first.snapshot()


def test_typed_invalid_outputs_keep_denominator_and_charges():
    data, bank, config = typed_fixture()

    def invalid(*args):
        _, details = backend(*args)
        return "invalid output", details

    report = run_session(data, bank, config, backend=invalid)
    assert len(report["snapshots"]) == len(data["opportunities"])
    assert all(c["admission_status"] == "invalid_response" for c in report["calls"])
    assert all(s["mode"] == "FOLLOW" for s in report["snapshots"])
    assert report["resource_spent"]["tokens"] == 30 * len(report["calls"])


def test_typed_E_only_never_installs_probability():
    data, bank, config = typed_fixture()
    config["typed_head"] = "e_only"

    def e_backend(*args):
        _, details = backend(*args)
        return '{"fact_truth":"unknown"}', details

    report = run_session(data, bank, config, backend=e_backend)
    assert all(c["admission_status"] == "e_only_recorded" for c in report["calls"])
    assert all(s["mode"] == "FOLLOW" for s in report["snapshots"])
    assert all(c["proposed_probability"] is None for c in report["calls"])


def test_private_typed_inputs_do_not_leak_other_target_answers_or_duration():
    data, bank, config = typed_fixture()
    inputs = []
    for bit in (0, 1):
        seen = []

        def private(system, request, cid, bit=bit, seen=seen):
            sensitive = request["target"]["entity"] == "station:KSFO"
            if not sensitive:
                seen.append(request)
            return json.dumps(
                {"fact_truth": "unknown", "probability": 0.8 if sensitive and bit else 0.2}
            ), {
                "seconds": 8 if sensitive and bit else 1,
                "input_tokens": 20,
                "output_tokens": 20 if sensitive and bit else 10,
                "ended_with_eos": True,
            }

        run_session(data, bank, config, backend=private)
        inputs.append(seen)
    assert inputs[0] and inputs[0] == inputs[1]


def test_admission_export_preserves_advance_boundaries_and_can_make_scoring_journal(tmp_path):
    engine, b, events = setup_engine()
    engine.run(events, until=65)
    engine.run([complete(b)], until=90)
    record = engine.export()
    restored = AdmissionEngine.restore(record)
    assert restored.export() == record
    path = tmp_path / "admission.jsonl"
    restored.write_journal(path)
    assert AdmissionEngine.from_journal(path).export() == record
    corrupt = copy.deepcopy(record)
    corrupt["payload"]["history"][-1]["until"] = 80
    with pytest.raises(ValueError, match="integrity"):
        AdmissionEngine.restore(corrupt)


def test_typed_withdrawal_invalidates_prior_context_without_using_an_older_product():
    engine, b, events = setup_engine()
    withdrawal = AdmissionEvent(
        "withdraw",
        75,
        "baseline_withdrawal",
        {"target_id": "t", "product_revision_id": "r1", "reason": "native cancellation"},
    )
    engine.run(events + [withdrawal, complete(b)], until=90)
    assert engine.attempts[-1]["status"] == "stale_base"
    assert engine.snapshots["o"]["baseline_kind"] == "fallback"
    assert engine.snapshots["o"]["mode"] == "FOLLOW"


def test_typed_adapter_rejects_cache_without_a_settled_resource_receipt():
    data, bank, config = typed_fixture()
    first = SessionCoordinator(data, bank, config)
    first.step()
    snapshot = first.snapshot()
    assert TypedAviationRuntime
    # A recomputed envelope hash cannot authorize an unpaid cache entry.
    from disastertrace.monitoring_v1.targets import canonical_hash

    payload = snapshot["payload"]
    receipt = payload["store"]["assets"][0]["receipt_ids"][0]
    payload["ledger"]["events"] = [
        e for e in payload["ledger"]["events"] if e["receipt_id"] != receipt
    ]
    snapshot["sha256"] = canonical_hash(payload)
    with pytest.raises(ValueError):
        SessionCoordinator.restore(snapshot, data, bank)
