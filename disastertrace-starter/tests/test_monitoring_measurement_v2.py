"""Regression contracts for the reviewed measurement boundary, using real journals."""

import copy

import pytest
from test_monitoring_admission import complete, setup_engine
from test_monitoring_typed_session import backend, typed_fixture

from disastertrace.monitoring_fixed_v1.admission import AdmissionEvent, score_admitted
from disastertrace.monitoring_fixed_v1.contracts import EvidenceBundle
from disastertrace.monitoring_v1.journal import EventJournal, read_journal
from disastertrace.monitoring_v1.policies import run_session
from disastertrace.monitoring_v1.session_checkpoint import SessionCoordinator


def revision(bundle, *, issue=40, available=70, value=-12, source="r2"):
    row = bundle.policy_view()
    row["baseline"].update(issued_at=issue, available_at=available, source_revision=source)
    row["baseline"]["forecast"]["value"] = value
    row["baseline"]["content"] = {"value": value}
    row["state"]["forecast"]["value"] = value
    return EvidenceBundle.freeze(row)


def test_old_arrival_and_withdrawal_do_not_replace_current():
    engine, bundle, events = setup_engine()
    old = revision(bundle, issue=30, source="old")
    withdrawal = AdmissionEvent(
        "withdraw",
        75,
        "baseline_withdrawal",
        {"target_id": "t", "product_revision_id": "old-cnl", "issued_at": 35, "reason": "canceled"},
    )
    engine.run(
        events[:1]
        + [AdmissionEvent("late-old", 70, "baseline", {"bundle": old.to_dict()}), withdrawal],
        until=90,
    )
    assert engine.snapshots["o"]["forecast"]["value"] == -3.5


def test_equal_issue_conflict_has_no_id_selected_winner():
    results = []
    for names in [("a", "z"), ("z", "a")]:
        engine, bundle, events = setup_engine()
        one = revision(bundle, issue=50, value=-1, source="new1")
        two = revision(bundle, issue=50, value=-9, source="new2")
        engine.run(
            events[:1]
            + [
                AdmissionEvent(names[0], 70, "baseline", {"bundle": one.to_dict()}),
                AdmissionEvent(names[1], 70, "baseline", {"bundle": two.to_dict()}),
            ],
            until=90,
        )
        results.append(engine.snapshots["o"]["forecast"]["value"])
    assert results == [-3.5, -3.5]


@pytest.mark.parametrize("bad_kind", ["duplicate", "invalid_target", "backdated"])
def test_invalid_batch_leaves_no_registered_events_or_journal(tmp_path, bad_kind):
    with EventJournal(tmp_path / "transaction.jsonl") as journal:
        engine, _bundle, events = setup_engine(journal=journal)
        engine.run(events[:1], until=55)
        before = engine.export()
        journal_before = copy.deepcopy(journal.records)
        good = AdmissionEvent("good", 65, "follow", {"target_id": "t"})
        bad = {
            "duplicate": AdmissionEvent("good", 66, "follow", {"target_id": "t"}),
            "invalid_target": AdmissionEvent("bad", 66, "follow", {"target_id": "missing"}),
            "backdated": AdmissionEvent("bad", 54, "follow", {"target_id": "t"}),
        }[bad_kind]
        with pytest.raises(ValueError):
            engine.run([good, bad], until=80)
        assert engine.export() == before
        assert journal.records == journal_before
        assert len(read_journal(journal.path).records) == len(journal_before)


def test_same_time_cancel_wins_before_uncommitted_completion():
    for identity in ("a-cancel", "z-cancel"):
        engine, bundle, events = setup_engine()
        engine.run(
            events + [complete(bundle), AdmissionEvent(identity, 80, "cancel", {"call_id": "c"})],
            until=90,
        )
        assert engine.snapshots["o"]["forecast"]["value"] == -3.5


def test_cancel_after_committed_completion_is_not_retroactive():
    engine, bundle, events = setup_engine()
    engine.run(
        events + [complete(bundle), AdmissionEvent("cancel", 85, "cancel", {"call_id": "c"})],
        until=90,
    )
    assert engine.snapshots["o"]["forecast"]["value"] == -5
    assert engine.calls["c"]["canceled"] is False


def test_override_cannot_outlive_target_semantics():
    engine, bundle, events = setup_engine()
    engine.run(events + [complete(bundle, expires_at=10000)], until=90)
    assert engine.attempts[-1]["status"] == "invalid_receipt"
    assert engine.snapshots["o"]["forecast"]["value"] == -3.5


def test_comparison_rejects_different_baseline_histories(tmp_path):
    paths = {}
    target_hash = None
    for name, value in [("left", -2), ("right", -9)]:
        paths[name] = tmp_path / (name + ".jsonl")
        with EventJournal(paths[name]) as journal:
            engine, bundle, events = setup_engine(journal=journal)
            target_hash = bundle.policy_view()["target"]["target_id"]
            row = revision(bundle, issue=45, available=70, value=value)
            engine.run(
                events[:1] + [AdmissionEvent("new", 70, "baseline", {"bundle": row.to_dict()})],
                until=90,
            )
            target_hash = engine.targets[target_hash].contract_hash
    outcomes = [
        {
            "opportunity_id": "o",
            "target_contract_hash": target_hash,
            "value": -4,
            "status": "mature",
            "source_revision": "obs",
        }
    ]
    with pytest.raises(ValueError, match="baseline"):
        score_admitted(outcomes, paths)


def test_acquire_only_does_not_require_predictor_quota():
    reports = []
    for cap in (0, 4):
        data, bank, config = typed_fixture(
            predict=False, forecast_call_cap=cap, model_call_budget=4
        )
        reports.append(run_session(data, bank, config))
    assert reports[0]["resource_spent"]["requests"] == reports[1]["resource_spent"]["requests"] > 0
    assert all(not report["calls"] for report in reports)


def test_backend_exception_has_full_denominator_and_unknown_reservation():
    data, bank, config = typed_fixture()

    def broken(*args):
        raise RuntimeError("synthetic transport failure")

    report = run_session(data, bank, config, backend=broken)
    assert len(report["snapshots"]) == len(data["opportunities"])
    assert report["calls"][0]["admission_status"] == "unknown_execution"
    assert report["calls"][0]["raw"] is None
    assert report["resource_reserved"]["tokens"] > 0
    assert len(report["calls"]) == 1


def test_overslot_preserves_response_and_records_real_usage():
    data, bank, config = typed_fixture()

    def slow(*args):
        raw, details = backend(*args)
        return raw, dict(details, seconds=121)

    report = run_session(data, bank, config, backend=slow)
    assert len(report["snapshots"]) == len(data["opportunities"])
    assert report["calls"][0]["raw"]
    assert report["calls"][0]["admission_status"] == "slot_overrun"
    assert report["resource_spent"]["compute_ms"] >= 121000
    assert report["calls"][0]["persisted_at"] < report["calls"][0]["bundle"]["payload"]["cutoff"]


def test_restore_rejects_unregistered_backend_implementation_change():
    data, bank, config = typed_fixture()
    session = SessionCoordinator(data, bank, config, backend=backend)
    session.step()

    def different(*args):
        return backend(*args)

    with pytest.raises(ValueError, match="execution|backend"):
        SessionCoordinator.restore(session.snapshot(), data, bank, backend=different)


def test_restore_rejects_changed_immutable_callback_configuration():
    data, bank, config = typed_fixture()

    def factory(probability):
        def configured(*args):
            _, details = backend(*args)
            return '{"fact_truth":"unknown","probability":' + str(probability) + "}", details

        return configured

    session = SessionCoordinator(data, bank, config, backend=factory(0.3))
    session.step()
    with pytest.raises(ValueError, match="execution"):
        SessionCoordinator.restore(session.snapshot(), data, bank, backend=factory(0.7))


def test_new_noncovering_taf_invalidates_older_covering_product():
    from disastertrace.monitoring_v1.providers.taf_timeline import target_withdrawals

    products = [
        {
            "source_id": "shorter",
            "station": "KAAA",
            "issued_at": 50,
            "valid_start": 110,
            "valid_end": 200,
            "status": "active",
        }
    ]
    targets = [{"target_id": "t", "entity": "KAAA", "physical_start": 100, "physical_end": 105}]
    rows = target_withdrawals(
        products, targets, 90, declared_replay_lag_us=0, version_policy="latest_before_coverage.v2"
    )
    assert len(rows) == 1 and rows[0]["reason"] == "current_version_does_not_cover_target"
    assert rows[0]["issued_at"] == 50


def test_selector_exception_keeps_full_denominator_and_unknown_cost():
    data, bank, config = typed_fixture(
        selector_kind="llm",
        isolation_mode="actual_cost_clock",
        allocation_mode="global_budget",
        authorization_mode="session_shared",
    )

    def failed_selector(*args):
        raise ConnectionError("synthetic selector disconnect")

    report = run_session(data, bank, config, backend=failed_selector)
    assert len(report["snapshots"]) == len(data["opportunities"])
    assert len(report["selector_calls"]) == 1
    assert report["selector_calls"][0]["execution_status"] == "unknown_execution"
    assert report["resource_reserved"]["tokens"] > 0
    assert not report["calls"]


def test_selector_overrun_preserves_raw_and_measured_cost():
    data, bank, config = typed_fixture(
        selector_kind="llm",
        isolation_mode="actual_cost_clock",
        allocation_mode="global_budget",
        authorization_mode="session_shared",
    )

    def overrun(*args):
        return '{"query_order":[],"forecast_handles":[]}', {
            "seconds": 0.01,
            "input_tokens": 900000,
            "output_tokens": 10,
            "ended_with_eos": True,
        }

    report = run_session(data, bank, config, backend=overrun)
    assert len(report["snapshots"]) == len(data["opportunities"])
    assert len(report["selector_calls"]) == 1
    assert report["selector_calls"][0]["raw"]
    assert report["selector_calls"][0]["execution_status"] == "resource_overrun"
    assert report["resource_spent"]["tokens"] == 900010


def test_source_overrun_is_charged_once_and_not_authorized():
    data, bank, config = typed_fixture(predict=False)
    for product in data["query_results"]:
        product["oversized_test_payload"] = "x" * 4096
    report = run_session(data, bank, config)
    assert len(report["snapshots"]) == len(data["opportunities"])
    assert report["resource_spent"]["requests"] > 0
    assert report["resource_spent"]["bytes"] > 2048
    assert all(r["execution_status"] == "resource_overrun" for r in report["source_receipts"])
    assert len({r["receipt_id"] for r in report["source_receipts"]}) == len(
        report["source_receipts"]
    )
    assert set(report["e_counts"]) == {"undetermined"}


def test_extreme_predictor_overrun_does_not_reverse_later_clock():
    data, bank, config = typed_fixture()

    def very_slow(*args):
        raw, details = backend(*args)
        return raw, dict(details, seconds=100000)

    report = run_session(data, bank, config, backend=very_slow)
    assert len(report["snapshots"]) == len(data["opportunities"])
    assert len(report["calls"]) == 1


def test_full_native_conflict_cannot_hide_behind_equal_projection():
    engine, bundle, events = setup_engine()
    first = revision(bundle, issue=50, value=-1, source="new1").policy_view()
    first["provider_version"] = "native_h15_snapshot.v1"
    first["baseline"]["content"] = {
        "native_taf": {"projection": {"same": True}},
        "mapping_details": {"same": True},
        "calibration_bank_sha256": "c" * 64,
    }
    second = copy.deepcopy(first)
    first["baseline"]["content"]["native_semantics_sha256"] = "a" * 64
    second["baseline"]["content"]["native_semantics_sha256"] = "b" * 64
    second["baseline"]["source_revision"] = "new2"
    engine.run(
        events[:1]
        + [
            AdmissionEvent("a", 70, "baseline", {"bundle": EvidenceBundle.freeze(first).to_dict()}),
            AdmissionEvent(
                "b", 70, "baseline", {"bundle": EvidenceBundle.freeze(second).to_dict()}
            ),
        ],
        until=90,
    )
    assert engine.attempts[-1]["status"] == "baseline_conflict"


def test_native_current_before_coverage_and_alias_conflicts():
    from disastertrace.monitoring_v1.providers.versions import current_taf

    old = {
        "source_id": "old",
        "station": "KAAA",
        "issued_at": 1,
        "valid_start": 2,
        "valid_end": 200,
        "status": "active",
        "native_semantics_sha256": "a",
    }
    new = dict(old, source_id="new", issued_at=2, valid_start=110, native_semantics_sha256="b")
    args = {"station": "KAAA", "cutoff": 50, "start": 100, "end": 105, "lag_us": 0}
    assert current_taf([old, new], **args)["status"] == "current_version_does_not_cover_target"
    alias = dict(old, source_id="alias")
    assert current_taf([old, alias], **args)["status"] == "active"
    assert (
        current_taf([old, dict(alias, native_semantics_sha256="different")], **args)["status"]
        == "conflict"
    )
