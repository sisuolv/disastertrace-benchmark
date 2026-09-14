"""Independent fixed-input audit with full denominators and typed cutoff replay."""

import argparse
import hashlib
import inspect
import json
import math
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


class AuditError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise AuditError(message)


def load(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode()
    ).hexdigest()


def save(path, value):
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def verify_inputs(batch):
    from disastertrace.monitoring_fixed_v1.contracts import EvidenceBundle
    from disastertrace.monitoring_fixed_v1.heads import model_messages
    from disastertrace.monitoring_fixed_v1.taf_tasks import TafEvidenceTask, evaluate
    from disastertrace.monitoring_fixed_v1.time_representation import (
        time_messages,
        transform,
    )

    require(
        Path(inspect.getfile(EvidenceBundle)).is_relative_to(batch / "source"),
        "Use the frozen batch/source PYTHONPATH",
    )
    plan = load(batch / "PLAN.json")
    require(
        len(plan["tasks"]) == plan["expected_benchmark_calls_per_model"] == 504,
        "Unexpected opportunity universe",
    )
    for rel, sha in plan["files"].items():
        require(digest(batch / rel) == sha, "Changed frozen file: " + rel)
    require(
        digest(batch / "EVALUATOR_MANIFEST.json") == plan["evaluator_manifest_sha256"],
        "Changed evaluator manifest",
    )
    for rel, sha in load(batch / "EVALUATOR_MANIFEST.json").items():
        require(digest(batch / rel) == sha, "Changed evaluator reference: " + rel)
    references = {
        r["identity"]: r["reference"]
        for r in load(batch / "evaluator/NATIVE_REFERENCES.json")
    }
    items = {}
    for task in plan["tasks"]:
        cid = task["call_id"]
        require(cid not in items, "Duplicate planned call")
        row = load(batch / "policy" / (cid + ".json"))
        if task["input_kind"] == "taf_task":
            item = TafEvidenceTask.freeze(row["input"])
            messages = time_messages(item, task["representation"])
            require(item.task_hash == task["identity"], "TAF identity changed")
            require(
                evaluate(item) == references[item.task_hash], "TAF reference changed"
            )
            require(
                transform(transform(item.view()), decode=True) == item.view(),
                "Inexact time pair",
            )
            require(
                item.view()["as_of"] <= task["logical_started_at"], "Future TAF input"
            )
        else:
            item = EvidenceBundle.restore(row["input"])
            view = item.policy_view()
            require(item.bundle_hash == task["identity"], "Bundle identity changed")
            messages = model_messages(item, task["head"])
            latest = max(
                [view["baseline"]["available_at"]]
                + [a["completed_at"] for a in view["assets"]]
                + [r["completed_at"] for r in view["receipts"]]
            )
            require(
                latest <= task["logical_started_at"] < view["cutoff"],
                "Input not visible at dispatch",
            )
            require(task["logical_cutoff"] == view["cutoff"], "Cutoff changed")
        require(
            messages == row["messages"]
            and fingerprint(messages) == task["messages_sha256"],
            "Input renderer differs from actual frozen messages",
        )
        items[cid] = item
    return plan, items


def verify_capture(worker, task, model, plan_hash, tokenizer, batch_size=4, offset=0):
    """Return a disposition for missing/uncommitted calls; reject changed receipts."""
    cid = task["call_id"]
    paths = {
        kind: worker / (cid + "-" + kind + ".json")
        for kind in ("request", "response", "commit")
    }
    present = {kind: path.exists() for kind, path in paths.items()}
    if not any(present.values()):
        return {
            "disposition": "unattempted",
            "request": None,
            "response": None,
            "commit": None,
        }
    require(present["request"], "Response/commit without original request")
    request = load(paths["request"])
    ids = tokenizer.apply_chat_template(
        request["messages"],
        tokenize=True,
        add_generation_prompt=True,
        enable_thinking=False,
    )
    require(
        request["call_id"] == cid
        and request["model"] == model
        and request["plan_sha256"] == plan_hash,
        "Request execution identity",
    )
    require(
        fingerprint(request["messages"]) == task["messages_sha256"],
        "Changed actual messages",
    )
    require(
        ids == request["input_ids"]
        and len(ids) == request["input_tokens"] == task["models"][model]["input_tokens"]
        and fingerprint(ids) == task["models"][model]["input_ids_sha256"],
        "Input token mismatch",
    )
    require(
        request["logical_started_at"] == task["logical_started_at"]
        and request["logical_cutoff"] == task["logical_cutoff"]
        and request["batch_offset"] == offset
        and request["batch_size"] == batch_size,
        "Request schedule mismatch",
    )
    if not present["response"]:
        require(not present["commit"], "Commit without response")
        return {
            "disposition": "unknown_execution",
            "request": request,
            "response": None,
            "commit": None,
        }
    response = load(paths["response"])
    require(
        response["call_id"] == cid
        and response["model"] == model
        and response["plan_sha256"] == plan_hash,
        "Response execution identity",
    )
    output = response["output_ids"]
    require(
        isinstance(output, list) and all(type(i) is int and i >= 0 for i in output),
        "Invalid output token IDs",
    )
    require(
        response["input_tokens"] == len(ids)
        and response["output_tokens"] == len(output) <= 512,
        "Output token count/cap mismatch",
    )
    raw_sha = hashlib.sha256(response["raw"].encode()).hexdigest()
    require(response["raw_sha256"] == raw_sha, "Raw response hash mismatch")
    require(
        tokenizer.decode(output, skip_special_tokens=True) == response["raw"],
        "Output token decoding mismatch",
    )
    eos = response["finish_reason"] == "stop" and (
        bool(output)
        and output[-1] == tokenizer.eos_token_id
        or response["stop_reason"] == tokenizer.eos_token_id
    )
    require(
        type(response["ended_with_eos"]) is bool
        and response["ended_with_eos"] == bool(eos),
        "EOS mismatch",
    )
    elapsed = response["batch_elapsed_us"]
    require(
        type(elapsed) is int
        and elapsed > 0
        and response["logical_started_at"] == task["logical_started_at"]
        and response["logical_completed_at"] == task["logical_started_at"] + elapsed,
        "Completion clock mismatch",
    )
    if not present["commit"]:
        return {
            "disposition": "uncommitted_response",
            "request": request,
            "response": response,
            "commit": None,
        }
    commit = load(paths["commit"])
    require(
        commit["call_id"] == cid and commit["plan_sha256"] == plan_hash,
        "Commit execution identity",
    )
    require(
        commit["request_sha256"] == digest(paths["request"])
        and commit["response_sha256"] == digest(paths["response"])
        and commit["raw_sha256"] == raw_sha,
        "Commit hash mismatch",
    )
    persisted = commit["persisted_elapsed_us"]
    require(
        type(persisted) is int
        and 0 < elapsed == commit["completed_elapsed_us"] <= persisted,
        "Persistence ordering mismatch",
    )
    require(
        commit["logical_persisted_at"] == task["logical_started_at"] + persisted,
        "Logical persistence mismatch",
    )
    wall = commit["wall_after_response_fsync_ns"] - commit["wall_started_ns"]
    require(
        wall >= 0 and abs(wall - persisted * 1000) <= 1_000_000_000,
        "Wall/monotonic timing mismatch",
    )
    return {
        "disposition": "committed",
        "request": request,
        "response": response,
        "commit": commit,
    }


def admission_inputs(batch, items):
    from disastertrace.monitoring_fixed_v1.admission import (
        AdmissionEvent,
        TypedOpportunity,
    )
    from disastertrace.monitoring_fixed_v1.contracts import EvidenceBundle, Target

    bundles = {
        i.policy_view()["opportunity_id"]: i
        for i in items.values()
        if isinstance(i, EvidenceBundle)
    }
    opportunities = []
    fallbacks = {}
    for oid in sorted(bundles):
        row = bundles[oid].policy_view()
        target = Target(**row["target"])
        opportunities.append(TypedOpportunity(oid, target, row["cutoff"]))
        fallbacks[target.target_id] = row["baseline"]["forecast"]
    require(
        len(opportunities) == len(fallbacks) == 48,
        "Fixed diagnostic expects 48 unique targets",
    )
    events = []
    for n, record in enumerate(load(batch / "evaluator/COMMON_BASELINES.json")):
        bundle = EvidenceBundle.restore(record["bundle"])
        events.append(
            AdmissionEvent(
                "common-" + str(n),
                bundle.policy_view()["baseline"]["available_at"],
                "baseline",
                {"bundle": bundle.to_dict()},
            )
        )
    return opportunities, fallbacks, events


def begin_event(task, bundle, executor, head=None):
    from disastertrace.monitoring_fixed_v1.admission import AdmissionEvent

    return AdmissionEvent(
        task["call_id"] + "-begin",
        task["logical_started_at"],
        "begin",
        {
            "call_id": task["call_id"],
            "bundle": bundle.to_dict(),
            "executor": executor,
            "head": head or task["head"],
        },
    )


def completion_event(
    task, bundle, executor, raw, elapsed, persisted, tokens, ended_with_eos, head=None
):
    from disastertrace.monitoring_fixed_v1.admission import AdmissionEvent

    row = {
        "call_id": task["call_id"],
        "bundle_hash": bundle.bundle_hash,
        "raw": raw,
        "raw_sha256": hashlib.sha256(raw.encode()).hexdigest(),
        "started_at": task["logical_started_at"],
        "completed_at": task["logical_started_at"] + elapsed,
        "persisted_at": task["logical_started_at"] + persisted,
        "expires_at": task["logical_cutoff"],
        "cost": {
            "requests": 0,
            "bytes": len(raw.encode()),
            "tokens": tokens,
            "compute_ms": math.ceil(elapsed / 1000),
        },
        "ended_with_eos": ended_with_eos,
        "head": head or task["head"],
        "executor": executor,
    }
    return AdmissionEvent(
        task["call_id"] + "-complete", row["persisted_at"], "completion", row
    )


def replay(out, name, opportunities, fallbacks, common, extra):
    from disastertrace.monitoring_fixed_v1.admission import AdmissionEngine
    from disastertrace.monitoring_v1.journal import EventJournal

    path = out / (name + ".jsonl")
    events = list(common) + list(extra)
    with EventJournal(path) as journal:
        engine = AdmissionEngine(opportunities, fallbacks=fallbacks, journal=journal)
        engine.run(
            events,
            until=max([o.cutoff for o in opportunities] + [e.time for e in events]),
        )
    rebuilt = AdmissionEngine.from_journal(path)
    require(
        rebuilt.export() == engine.export(), "Independent admission replay mismatch"
    )
    require(
        not any(r["status"] == "invalid_begin" for r in engine.attempts),
        "Invalid fixed-input invocation",
    )
    require(len(engine.snapshots) == len(opportunities), "Missing sealed opportunity")
    return path, engine


def program_controls(batch, plan, items, out):
    from disastertrace.monitoring_fixed_v1.aviation import (
        FrozenFrequencyPredictor,
        visible_e_status,
    )
    from disastertrace.monitoring_fixed_v1.contracts import canonical

    predictor = FrozenFrequencyPredictor(load(batch / "evaluator/BANK.json"))
    opportunities, fallbacks, common = admission_inputs(batch, items)
    arms = {}
    records = []
    path, _ = replay(out, "follow", opportunities, fallbacks, common, [])
    arms["follow"] = path
    for condition in ("common_only", "fixed_one", "all_registered"):
        extra = []
        for task in plan["tasks"]:
            if (
                task["input_kind"] != "bundle"
                or task["head"] != "f_only"
                or task["condition"] != condition
            ):
                continue
            bundle = items[task["call_id"]]
            value, detail = predictor.predict_with_details(bundle)
            extra.extend(
                [
                    begin_event(task, bundle, "frozen_frequency", "program"),
                    completion_event(
                        task,
                        bundle,
                        "frozen_frequency",
                        canonical(value.to_dict()),
                        1000,
                        2000,
                        0,
                        True,
                        "program",
                    ),
                ]
            )
            records.append(
                {
                    "condition": condition,
                    "opportunity_id": bundle.policy_view()["opportunity_id"],
                    "forecast": value.to_dict(),
                    "details": detail,
                    "expected_e": visible_e_status(bundle),
                }
            )
        path, engine = replay(
            out, "program_" + condition, opportunities, fallbacks, common, extra
        )
        arms["program_" + condition] = path
        require(len(engine.calls) == 48, "Program baseline denominator")
    save(out / "PROGRAM_RECORDS.json", records)
    return arms


def stratified_scores(outcomes, arms):
    from disastertrace.monitoring_fixed_v1.admission import (
        AdmissionEngine,
        score_admitted,
    )
    from disastertrace.monitoring_fixed_v1.contracts import paired_scores

    audit = score_admitted(outcomes, arms)
    engines = {name: AdmissionEngine.from_journal(path) for name, path in arms.items()}
    first = next(iter(engines.values()))
    rows = {r["opportunity_id"]: r for r in outcomes}
    result = {}
    for threshold in (1000, 5000):
        selected = [
            {
                "opportunity_id": oid,
                "target": o.target.to_dict(),
                "outcome": rows[oid]["value"]
                if rows[oid]["status"] == "mature"
                else None,
            }
            for oid, o in first.opportunities.items()
            if o.target.threshold == threshold
        ]
        score = paired_scores(
            selected,
            {
                name: {
                    r["opportunity_id"]: engine.snapshots[r["opportunity_id"]][
                        "forecast"
                    ]
                    for r in selected
                }
                for name, engine in engines.items()
            },
        )
        score["positive_opportunities"] = sum(r["outcome"] == 1 for r in selected)
        score["unique_targets"] = len({r["target"]["target_id"] for r in selected})
        score["missing_quality"] = dict(
            Counter(
                rows[r["opportunity_id"]]["quality_status"]
                for r in selected
                if r["outcome"] is None
            )
        )
        result[str(threshold)] = score
    return {
        "by_threshold_m": result,
        "common_baseline_and_canonical_outcome_audit": True,
        "contract_sha256": audit["contract_sha256"],
        "outcome_sha256": audit["outcome_sha256"],
    }


def prepare(batch, out):
    plan, items = verify_inputs(batch)
    require(
        not any(
            (batch / key / "SMOKE_REQUEST.json").exists() for key in plan["models"]
        ),
        "Initial evaluator protocol must precede inference",
    )
    out.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(Path(__file__), out / "verify_large_diagnostic.py")
    arms = program_controls(batch, plan, items, out)
    scores = stratified_scores(load(batch / "evaluator/CANONICAL_OUTCOMES.json"), arms)
    save(out / "PROGRAM_SCORES.json", scores)
    save(
        out / "PROTOCOL.json",
        {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "plan_sha256": digest(batch / "PLAN.json"),
            "scorer_sha256": digest(Path(__file__)),
            "frozen_source_verified": True,
            "all_dispatch_inputs_and_native_time_pairs_verified": True,
            "program_admission_and_journal_replay_verified": True,
            "program_latency": "declared 1ms computation plus 1ms persistence; no measured wall-time claim",
            "expected_tasks_per_model": 504,
            "expected_unique_forecast_opportunities_per_arm": 48,
            "denominator": "all planned calls; missing/invalid/unfinished/late remain; no F score for E-only",
            "adoption": "typed_auto_propose.v1; full common updates through cutoff; failed F uses effective common baseline",
            "E_scoring": "exact reference match with valid EOS and timely durable response; unscored raw correctness separate",
            "F_scoring": "canonical mature outcome mask; typed effective cutoff forecast; thresholds separate",
            "timing": "whole generation batch plus response fsync, excluding prompt tokenization and model load; not end-to-end latency",
            "strong_controls": "same frozen research frequency map f(B), f(B,E1), f(B,all_registered); all_registered is not an F upper bound or equal-budget adaptive arm",
            "inference_calls_at_freeze": 0,
            "independent_confirmation": False,
            "files": {p.name: digest(p) for p in out.iterdir() if p.is_file()},
        },
    )
    print(
        json.dumps(
            {"prepared": str(out), "preflight_passed": True, "F_controls": scores}
        )
    )


def model_report(batch, plan, items, model, out):
    from disastertrace.monitoring_fixed_v1.aviation import visible_e_status
    from disastertrace.monitoring_fixed_v1.heads import parse_response
    from disastertrace.monitoring_fixed_v1.taf_tasks import (
        evaluate,
        parse_answer,
        score_answer,
    )
    from transformers import AutoTokenizer

    out.mkdir(exist_ok=False)
    worker = batch / model
    spec = plan["models"][model]
    for row in spec["files"]:
        if "safetensors" not in row["path"]:
            require(
                digest(Path(spec["directory"]) / row["path"]) == row["sha256"],
                "Tokenizer/model metadata changed",
            )
    tokenizer = AutoTokenizer.from_pretrained(spec["directory"], local_files_only=True)
    plan_hash = digest(batch / "PLAN.json")
    smoke_request = worker / "SMOKE_REQUEST.json"
    smoke_response = worker / "SMOKE_RESPONSE.json"
    smoke_ok = None
    if smoke_request.exists():
        expected_ids = tokenizer.apply_chat_template(
            [{"role": "user", "content": "Return exactly READY."}],
            tokenize=True,
            add_generation_prompt=True,
            enable_thinking=False,
        )
        smoke = load(smoke_request)
        require(
            smoke["prompt_token_ids"] == expected_ids
            and smoke["plan_sha256"] == plan_hash,
            "Compatibility request identity mismatch",
        )
    if smoke_response.exists():
        require(smoke_request.exists(), "Compatibility answer without request")
        smoke = load(smoke_response)
        require(
            tokenizer.decode(smoke["output_ids"], skip_special_tokens=True)
            == smoke["raw"],
            "Compatibility output token mismatch",
        )
        smoke_ok = smoke["raw"].strip() == "READY" and smoke["finish_reason"] == "stop"
    hardware = (
        load(worker / "HARDWARE.json") if (worker / "HARDWARE.json").exists() else None
    )
    if hardware is not None:
        require(
            hardware["plan_sha256"] == plan_hash
            and hardware["runtime_versions"] == plan["runtime_versions"],
            "Hardware/runtime contract mismatch",
        )
        require(
            hardware["tensor_parallel_size"] == 4
            and len(hardware["gpus"]) == 4
            and all("H100" in row["name"] for row in hardware["gpus"])
            and hardware["model_files_verified"] == spec["files"],
            "Weights/GPU receipt mismatch",
        )
    opportunities, fallbacks, common = admission_inputs(batch, items)
    streams = defaultdict(list)
    records = []
    batches = {}
    for n, task in enumerate(plan["tasks"]):
        cid, item = task["call_id"], items[task["call_id"]]
        record = {
            k: task[k]
            for k in (
                "call_id",
                "input_kind",
                "head",
                "condition",
                "identity",
                "representation",
            )
        }
        record.update(
            e_expected=None,
            e_answer=None,
            e_correct=None,
            e_raw_correct=None,
            parse_error=None,
            candidate_probability=None,
            proposed_action=None,
        )
        try:
            captured = verify_capture(
                worker,
                task,
                model,
                plan_hash,
                tokenizer,
                batch_size=min(4, len(plan["tasks"]) - n // 4 * 4),
                offset=n // 4 * 4,
            )
            record["integrity_error"] = None
        except (AuditError, KeyError, ValueError, TypeError) as exc:
            record["integrity_error"] = str(exc)
            captured = {
                "disposition": "integrity_error",
                "request": None,
                "response": None,
                "commit": None,
            }
        response, commit = captured["response"], captured["commit"]
        record["disposition"] = captured["disposition"]
        record["timely"] = bool(
            commit and commit["logical_persisted_at"] <= task["logical_cutoff"]
        )
        record["ended_with_eos"] = bool(response and response["ended_with_eos"])
        record["input_tokens"] = (
            None if not captured["request"] else captured["request"]["input_tokens"]
        )
        record["output_tokens"] = None if not response else response["output_tokens"]
        record["raw"] = None if not response else response["raw"]
        record["persisted_elapsed_us"] = (
            None if not commit else commit["persisted_elapsed_us"]
        )
        admitted_response = (
            commit is not None and record["ended_with_eos"] and record["timely"]
        )
        if commit:
            require(
                hardware is not None, "Committed inference without hardware receipt"
            )
            timing = (response["batch_elapsed_us"], commit["wall_started_ns"])
            previous = batches.setdefault(n // 4 * 4, timing)
            require(previous == timing, "Inconsistent shared batch timing")
            record["commit_sha256"] = digest(worker / (cid + "-commit.json"))
        if task["input_kind"] == "taf_task":
            result = score_answer(record["raw"] or "", item)
            record["e_expected"] = evaluate(item)["answer"]
            record["e_answer"] = (
                parse_answer(record["raw"], item) if result["valid"] else None
            )
            record["parse_error"] = result.get("error")
            record["e_raw_correct"] = result["correct"]
            record["e_correct"] = admitted_response and result["correct"]
        else:
            view = item.policy_view()
            oid = view["opportunity_id"]
            group = task["head"] + "__" + task["condition"]
            stream = streams[group]
            record.update(
                opportunity_id=oid,
                target_id=view["target"]["target_id"],
                threshold_m=view["target"]["threshold"],
                baseline_at_dispatch=view["baseline"]["forecast"]["value"],
            )
            if captured["request"]:
                stream.append(begin_event(task, item, model))
            if commit:
                stream.append(
                    completion_event(
                        task,
                        item,
                        model,
                        record["raw"],
                        response["batch_elapsed_us"],
                        commit["persisted_elapsed_us"],
                        response["input_tokens"] + response["output_tokens"],
                        record["ended_with_eos"],
                    )
                )
            answer = None
            if response:
                try:
                    answer = parse_response(record["raw"], item, task["head"])
                except (ValueError, TypeError, OverflowError) as exc:
                    record["parse_error"] = str(exc)
            if task["head"] != "f_only":
                record["e_expected"] = visible_e_status(item)
                record["e_answer"] = None if answer is None else answer.e_status
                record["e_raw_correct"] = record["e_expected"] == record["e_answer"]
                record["e_correct"] = admitted_response and record["e_raw_correct"]
            if answer is not None and answer.forecast is not None:
                record["candidate_probability"] = answer.forecast.value
                record["proposed_action"] = "OVERRIDE"
                record["candidate_equals_dispatch_baseline"] = (
                    answer.forecast.value == record["baseline_at_dispatch"]
                )
        records.append(record)
    arms = program_controls(batch, plan, items, out)
    snapshots = []
    statuses = {}
    for group, stream in sorted(streams.items()):
        path, engine = replay(out, group, opportunities, fallbacks, common, stream)
        if not group.startswith("e_only__"):
            arms[group] = path
        statuses[group] = dict(Counter(r["status"] for r in engine.attempts))
        snapshots.extend({"group": group, **s} for s in engine.snapshots.values())
        attempts = {r.get("call_id"): r for r in engine.attempts if "call_id" in r}
        for record in records:
            if (
                record["input_kind"] == "bundle"
                and record["head"] + "__" + record["condition"] == group
            ):
                snapshot = engine.snapshots[record["opportunity_id"]]
                record["admission_status"] = attempts.get(record["call_id"], {}).get(
                    "status", "no_durable_response"
                )
                record["effective_at_cutoff"] = snapshot["forecast"]["value"]
                record["effective_mode_at_cutoff"] = snapshot["mode"]
    e_scores = {}
    for record in records:
        if record["head"] == "f_only":
            continue
        group = "__".join(
            [record["head"], record["condition"], record["representation"]]
        )
        if record["input_kind"] == "bundle":
            group += "__" + str(record["threshold_m"])
        selected = e_scores.setdefault(
            group,
            {
                "registered": 0,
                "correct": 0,
                "raw_correct": 0,
                "always_unknown_correct": 0,
            },
        )
        selected["registered"] += 1
        selected["correct"] += bool(record["e_correct"])
        selected["raw_correct"] += bool(record["e_raw_correct"])
        selected["always_unknown_correct"] += record["e_expected"] == "undetermined"
    time_pairs = []
    grouped = defaultdict(dict)
    for record in records:
        if record["input_kind"] == "taf_task":
            grouped[record["identity"]][record["representation"]] = record
    for identity, pair in sorted(grouped.items()):
        require(
            set(pair) == {"epoch_us", "iso_utc"}
            and pair["epoch_us"]["e_expected"] == pair["iso_utc"]["e_expected"],
            "Unpaired native time diagnostic",
        )
        time_pairs.append(
            {
                "identity": identity,
                "head": pair["epoch_us"]["head"],
                "epoch_correct": pair["epoch_us"]["e_correct"],
                "iso_correct": pair["iso_utc"]["e_correct"],
            }
        )
    complete = (
        load(worker / "COMPLETE.json") if (worker / "COMPLETE.json").exists() else None
    )
    if complete:
        require(
            complete["plan_sha256"] == plan_hash
            and complete["benchmark_calls"] == 504
            and complete["compatibility_calls"] == 1,
            "Completion receipt mismatch",
        )
    report = {
        "model": model,
        "name": spec["name"],
        "plan_sha256": plan_hash,
        "registered": len(records),
        "compatibility_requests": int(smoke_request.exists()),
        "compatibility_responses": int(smoke_response.exists()),
        "compatibility_ready": smoke_ok,
        "dispositions": dict(Counter(r["disposition"] for r in records)),
        "committed": sum(r["disposition"] == "committed" for r in records),
        "timely": sum(r["timely"] for r in records),
        "ended_with_eos": sum(r["ended_with_eos"] for r in records),
        "parse_errors": sum(r["parse_error"] is not None for r in records),
        "integrity_errors": sum(r["integrity_error"] is not None for r in records),
        "input_tokens_received": sum(r["input_tokens"] or 0 for r in records),
        "output_tokens_received": sum(r["output_tokens"] or 0 for r in records),
        "unique_measured_batches": len(batches),
        "generation_batch_seconds": sum(t[0] for t in batches.values()) / 1_000_000,
        "E": e_scores,
        "time_pairs": time_pairs,
        "admission_statuses": statuses,
        "F": stratified_scores(load(batch / "evaluator/CANONICAL_OUTCOMES.json"), arms),
        "candidate_changes": sum(
            r.get("candidate_equals_dispatch_baseline") is False for r in records
        ),
        "equal_probability_override_proposals": sum(
            r.get("candidate_equals_dispatch_baseline") is True for r in records
        ),
        "all_completed": bool(complete)
        and all(r["disposition"] == "committed" for r in records),
        "limits": [
            "Exposed development sample; no independent-process confirmation.",
            "Fixed-input response and typed adoption, not adaptive LLM acquisition.",
            "All-registered program is a strong information comparator, not a forecasting upper bound.",
            "Two differently tuned/quantized architectures; no pure model-size causal claim.",
            "Generation timing excludes tokenizer preparation and model load; not end-to-end latency.",
            "Each opportunity receives the whole batch latency; GPU usage sums unique batches only.",
        ],
    }
    save(out / "RECORDS.json", records)
    save(out / "SNAPSHOTS.json", snapshots)
    save(out / "REPORT.json", report)
    return report


def score(batch, prepared, out):
    plan, items = verify_inputs(batch)
    protocol = load(prepared / "PROTOCOL.json")
    require(
        protocol["plan_sha256"] == digest(batch / "PLAN.json")
        and protocol["scorer_sha256"] == digest(Path(__file__)),
        "Scorer differs from pre-inference protocol",
    )
    for rel, sha in protocol["files"].items():
        require(digest(prepared / rel) == sha, "Changed frozen evaluation control")
    job_path = batch / "submission_01/FINAL_JOB.json"
    job = load(job_path)
    require(
        job["name"] == (batch / "submission_01/job-id.txt").read_text().strip()
        and job["state"] in {"SUCCEEDED", "FAILED", "DELETED"},
        "GPU job is not terminal",
    )
    out.mkdir(parents=True, exist_ok=False)
    reports = {
        key: model_report(batch, plan, items, key, out / key)
        for key in plan["model_order"]
    }
    validation = {
        "plan_sha256": digest(batch / "PLAN.json"),
        "protocol_sha256": digest(prepared / "PROTOCOL.json"),
        "integrity_passed": all(not r["integrity_errors"] for r in reports.values()),
        "all_planned_completed": all(r["all_completed"] for r in reports.values()),
        "registered": sum(r["registered"] for r in reports.values()),
        "committed": sum(r["committed"] for r in reports.values()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "real_model_results": any(r["committed"] for r in reports.values()),
        "gpu_job_state": job["state"],
        "gpu_job_receipt_sha256": digest(job_path),
        "process_confirmation": False,
    }
    save(out / "VALIDATION.json", validation)
    print(
        json.dumps(
            {
                "validation": validation,
                "models": {
                    k: {
                        f: r[f]
                        for f in (
                            "registered",
                            "committed",
                            "timely",
                            "parse_errors",
                            "candidate_changes",
                        )
                    }
                    for k, r in reports.items()
                },
            }
        )
    )
    require(
        validation["integrity_passed"],
        "One or more captures failed independent integrity checks",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["prepare", "score"])
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--prepared", type=Path)
    args = parser.parse_args()
    if args.mode == "prepare":
        prepare(args.batch.resolve(), args.out.resolve())
    else:
        score(args.batch.resolve(), args.prepared.resolve(), args.out.resolve())
