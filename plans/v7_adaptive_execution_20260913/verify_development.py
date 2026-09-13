"""Independent input/capture audit and typed cutoff scoring, without model calls."""

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from disastertrace.monitoring_fixed_v1.admission import (
    AdmissionEngine,
    AdmissionEvent,
    TypedOpportunity,
    score_admitted,
)
from disastertrace.monitoring_fixed_v1.aviation import FrozenFrequencyPredictor
from disastertrace.monitoring_fixed_v1.contracts import (
    EvidenceBundle,
    Forecast,
    Target,
    canonical,
    fingerprint,
)
from disastertrace.monitoring_fixed_v1.heads import parse_response
from disastertrace.monitoring_fixed_v1.representations import model_messages
from disastertrace.monitoring_fixed_v1.support_bridge import native_slot_support
from disastertrace.monitoring_fixed_v1.taf_tasks import TafEvidenceTask, evaluate, score_answer
from disastertrace.monitoring_fixed_v1.taf_tasks import messages as taf_messages
from disastertrace.monitoring_v1.calibration import predict
from disastertrace.monitoring_v1.journal import EventJournal

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, row):
    with path.open("x") as f:
        f.write(json.dumps(row, indent=2, allow_nan=False) + "\n")


def inputs(batch):
    plan = json.loads((batch / "PLAN.json").read_text())
    for rel, expected in plan["files"].items():
        if digest(batch / rel) != expected:
            raise ValueError("Frozen input/source binding changed: " + rel)
    tasks = []
    for worker, rows in plan["workers"].items():
        for row in rows:
            payload = json.loads((batch / "policy" / (row["call_id"] + ".json")).read_text())
            if row["input_kind"] == "bundle":
                item = EvidenceBundle.restore(payload)
                request = model_messages(item, row["head"], row["representation"])
                reference = native_slot_support(item)
                if row["representation"] == "native_task_focus.v1":
                    view = json.loads(request[1]["content"])
                    disclosed = [
                        a for s in view["registered_native_slots"] for a in s["native_sources"]
                    ]
                    assert {a["asset_id"]: a["content"] for a in disclosed} == {
                        a["asset_id"]: a["content"] for a in item.policy_view()["assets"]
                    }
                    assert "fact_truth" not in request[1]["content"]
                identity = item.bundle_hash
            else:
                item = TafEvidenceTask.freeze(payload)
                request, reference = taf_messages(item), evaluate(item)
                identity = item.task_hash
                assert "gold" not in request[1]["content"]
                assert not any(
                    word in item.view()["task_id"]
                    for word in ("full", "partial", "none", "both", "only")
                )
            assert identity == row["bundle_hash"]
            assert fingerprint(request) == row["messages_sha256"]
            tasks.append((worker, row, item, request, reference))
    assert len(tasks) == plan["expected_calls"] == 252
    return plan, tasks


def main(batch, dataset, out, preflight):
    out.mkdir(parents=True, exist_ok=False)
    plan, tasks = inputs(batch)
    if preflight:
        report = {
            "inputs": len(tasks),
            "all_source_and_message_hashes_verified": True,
            "focused_native_values_equal_full_values": True,
            "answer_labels_absent_from_native_task_ids": True,
            "new_model_calls": 0,
            "plan_sha256": digest(batch / "PLAN.json"),
        }
        save(out / "PREFLIGHT.json", report)
        print(json.dumps(report))
        return
    records, arm_rows, common = [], defaultdict(list), {}
    native_records, hardware = [], {}
    for worker in plan["workers"]:
        path = batch / ("worker-" + worker)
        hw = json.loads((path / "HARDWARE.json").read_text())
        assert hw["count"] == 1 and "H100" in hw["name"] and hw["hostname"] != plan["cci_hostname"]
        assert hw["runtime_versions"] == plan["runtime_versions"] and hw["model_files_verified"]
        hardware[worker] = hw
    for worker, row, item, messages, reference in tasks:
        directory, cid = batch / ("worker-" + worker), row["call_id"]
        request_path = directory / (cid + "-request.json")
        response_path = directory / (cid + "-response.json")
        commit_path = directory / (cid + "-commit.json")
        base = {k: row[k] for k in ("call_id", "head", "condition", "representation", "input_kind")}
        base.update(worker=worker, planned=True)
        if not all(p.exists() for p in (request_path, response_path, commit_path)):
            base.update(status="missing_or_uncommitted", valid=False, correct=False)
            records.append(base)
            if row["input_kind"] == "bundle":
                common[item.policy_view()["opportunity_id"]] = item
                if row["head"] != "e_only":
                    arm_rows[(row["head"], row["representation"], row["condition"])].append(
                        (row, item, None, None)
                    )
            continue
        request, response, commit = (
            json.loads(p.read_text()) for p in (request_path, response_path, commit_path)
        )
        assert request["messages"] == messages
        assert request["input_tokens"] == response["input_tokens"] == row["input_tokens"]
        assert response["output_tokens"] == len(response["output_ids"])
        assert (
            request["bundle_hash"]
            == response["bundle_hash"]
            == commit["bundle_hash"]
            == row["bundle_hash"]
        )
        assert (
            request["plan_sha256"]
            == response["plan_sha256"]
            == commit["plan_sha256"]
            == digest(batch / "PLAN.json")
        )
        assert commit["request_sha256"] == digest(request_path) and commit[
            "response_sha256"
        ] == digest(response_path)
        assert (
            response["raw_sha256"]
            == commit["raw_sha256"]
            == hashlib.sha256(response["raw"].encode()).hexdigest()
        )
        assert commit["logical_started_at"] == row["logical_started_at"]
        assert 0 < commit["completed_elapsed_us"] <= commit["persisted_elapsed_us"]
        assert commit["wall_started_ns"] <= commit["wall_after_response_fsync_ns"]
        base.update(
            raw=response["raw"],
            status="captured",
            receipt_sha256=digest(commit_path),
            completed_elapsed_us=commit["completed_elapsed_us"],
            persisted_elapsed_us=commit["persisted_elapsed_us"],
        )
        if row["input_kind"] == "taf_task":
            score = score_answer(response["raw"], item)
            if not response["ended_with_eos"]:
                score.update(valid=False, correct=False, error="unfinished_response")
            base.update(score, expected=reference["answer"], task_id=item.view()["task_id"])
            native_records.append(base)
        else:
            p = item.policy_view()
            common[p["opportunity_id"]] = item
            try:
                parsed = parse_response(response["raw"], item, row["head"])
                if response["ended_with_eos"] is not True:
                    raise ValueError("Unfinished response")
                base.update(
                    valid=True,
                    e_status=parsed.e_status,
                    e_correct=None
                    if row["head"] == "f_only"
                    else parsed.e_status == reference["status"],
                    probability=None if parsed.forecast is None else parsed.forecast.value,
                )
            except (ValueError, TypeError) as exc:
                base.update(
                    valid=False,
                    error=str(exc),
                    e_status=None,
                    e_correct=False if row["head"] != "f_only" else None,
                    probability=None,
                )
            base.update(
                opportunity_id=p["opportunity_id"],
                expected_e=None if row["head"] == "f_only" else reference["status"],
                baseline_probability=p["baseline"]["forecast"]["value"],
            )
            base["F_changed"] = (
                base["probability"] is not None
                and base["probability"] != base["baseline_probability"]
            )
            if row["head"] != "e_only":
                arm_rows[(row["head"], row["representation"], row["condition"])].append(
                    (row, item, response, commit)
                )
        records.append(base)
    opportunities = [
        TypedOpportunity(oid, Target(**b.policy_view()["target"]), b.policy_view()["cutoff"])
        for oid, b in sorted(common.items())
    ]
    for oid, bundle in list(common.items()):
        row = bundle.policy_view()
        row["assets"], row["receipts"] = [], []
        common[oid] = EvidenceBundle.freeze(row)
    bank = json.loads(
        (ROOT / "plans/v7_execution_20260913/evidence_bundle/matrix_01/BANK.json").read_text()
    )
    fallbacks = {
        o.target.target_id: Forecast(
            o.target.contract_hash,
            "event_probability",
            "probability",
            predict(
                bank,
                common[o.opportunity_id].policy_view()["baseline"]["content"][
                    "legacy_target_contract"
                ],
                None,
            )["probability"],
        ).to_dict()
        for o in opportunities
    }
    baseline_events = [
        AdmissionEvent(
            "baseline-" + fingerprint(oid)[:24],
            b.policy_view()["baseline"]["available_at"],
            "baseline",
            {"bundle": b.to_dict()},
        )
        for oid, b in sorted(common.items())
    ]
    arms = {}
    for key, members in arm_rows.items():
        name = "__".join(key)
        events = list(baseline_events)
        for row, bundle, response, commit in members:
            if response is None:
                continue
            cid, started = row["call_id"], row["logical_started_at"]
            events.append(
                AdmissionEvent(
                    cid + "-begin",
                    started,
                    "begin",
                    {
                        "call_id": cid,
                        "bundle": bundle.to_dict(),
                        "head": row["head"],
                        "executor": "pinned_qwen3_8b.actual",
                    },
                )
            )
            persisted = started + commit["persisted_elapsed_us"]
            events.append(
                AdmissionEvent(
                    cid + "-completion",
                    persisted,
                    "completion",
                    {
                        "call_id": cid,
                        "bundle_hash": bundle.bundle_hash,
                        "raw": response["raw"],
                        "raw_sha256": response["raw_sha256"],
                        "started_at": started,
                        "completed_at": started + commit["completed_elapsed_us"],
                        "persisted_at": persisted,
                        "expires_at": row["logical_cutoff"],
                        "cost": {
                            "requests": 0,
                            "bytes": 0,
                            "tokens": response["input_tokens"] + response["output_tokens"],
                            "compute_ms": (commit["completed_elapsed_us"] + 999) // 1000,
                        },
                        "ended_with_eos": response["ended_with_eos"],
                        "head": row["head"],
                        "executor": "pinned_qwen3_8b.actual",
                    },
                )
            )
        path = out / (name + ".jsonl")
        with EventJournal(path) as journal:
            engine = AdmissionEngine(opportunities, fallbacks=fallbacks, journal=journal)
            engine.run(
                events, until=max([o.cutoff for o in opportunities] + [e.time for e in events])
            )
        arms[name] = path
    program = FrozenFrequencyPredictor(bank)
    for condition in ("follow", "common_only", "fixed_one", "all_registered"):
        events = list(baseline_events)
        if condition != "follow":
            for _, row, b, _, _ in tasks:
                if (
                    row["input_kind"] != "bundle"
                    or row["head"] != "f_only"
                    or row["representation"] != "full_bundle"
                    or row["condition"] != condition
                ):
                    continue
                cid, at = "program-" + row["call_id"], row["logical_started_at"]
                raw = canonical(program.predict(b).to_dict())
                events.append(
                    AdmissionEvent(
                        cid + "-begin",
                        at,
                        "begin",
                        {
                            "call_id": cid,
                            "bundle": b.to_dict(),
                            "head": "program",
                            "executor": "frozen_frequency.v1",
                        },
                    )
                )
                events.append(
                    AdmissionEvent(
                        cid + "-complete",
                        at + 1000,
                        "completion",
                        {
                            "call_id": cid,
                            "bundle_hash": b.bundle_hash,
                            "raw": raw,
                            "raw_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                            "started_at": at,
                            "completed_at": at + 1000,
                            "persisted_at": at + 1000,
                            "expires_at": row["logical_cutoff"],
                            "cost": {"requests": 0, "bytes": 0, "tokens": 0, "compute_ms": 1},
                            "ended_with_eos": True,
                            "head": "program",
                            "executor": "frozen_frequency.v1",
                        },
                    )
                )
        path = out / ("program_" + condition + ".jsonl")
        with EventJournal(path) as journal:
            engine = AdmissionEngine(opportunities, fallbacks=fallbacks, journal=journal)
            engine.run(events, until=max(o.cutoff for o in opportunities))
        arms["program_" + condition] = path
    raw_outcomes = {
        o["target_id"]: o for o in json.loads((dataset / "private/OUTCOMES.json").read_text())
    }
    outcomes = [
        {
            "opportunity_id": o.opportunity_id,
            "target_contract_hash": o.target.contract_hash,
            "value": raw_outcomes[o.target.target_id]["outcome"],
            "status": "mature"
            if raw_outcomes[o.target.target_id]["status"] == "settled_final_archived_report"
            else "missing",
            "source_revision": fingerprint(raw_outcomes[o.target.target_id]),
        }
        for o in opportunities
    ]
    scores = score_admitted(outcomes, arms)
    groups = defaultdict(list)
    for r in records:
        groups[r["head"], r["representation"], r["condition"]].append(r)
    summary = [
        {
            "head": h,
            "representation": rep,
            "condition": cond,
            "n": len(rows),
            "valid": sum(r["valid"] for r in rows),
            "E_correct": sum(r.get("e_correct") is True for r in rows),
            "native_task_correct": sum(r.get("correct") is True for r in rows),
            "E_predictions": dict(Counter(r.get("e_status") for r in rows)),
            "F_changed": sum(r.get("F_changed", False) for r in rows),
        }
        for (h, rep, cond), rows in sorted(groups.items())
    ]
    report = {
        "schema": "disastertrace.new_calendar_model_report.v1",
        "expected_calls": len(tasks),
        "committed_calls": sum(r["status"] == "captured" for r in records),
        "missing_calls": sum(r["status"] != "captured" for r in records),
        "invalid_calls": sum(not r["valid"] for r in records),
        "summary": summary,
        "plan_sha256": digest(batch / "PLAN.json"),
        "F_scores": scores["scores"],
        "F_admissions": {k: dict(Counter(v)) for k, v in scores["admission_statuses"].items()},
        "hardware": hardware,
        "independent_confirmation": False,
        "adaptive_LLM_experiment": False,
        "native_E_cases_include_physical_weather_forecasts": False,
        "new_paid_api_calls": 0,
        "model_retries": 0,
    }
    save(out / "OUTCOME_REFERENCES.json", outcomes)
    save(out / "SCORES.json", scores)
    save(out / "RECORDS.json", records)
    save(out / "REPORT.json", report)
    print(json.dumps(report))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--dataset", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    main(args.batch, args.dataset, args.output, args.preflight)
