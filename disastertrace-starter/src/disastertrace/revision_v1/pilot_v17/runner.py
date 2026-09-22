"""Fresh bounded execution; all provider attempts are captured by the broker."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import threading
import time

from .agent_view import NativeReader, initial_state, messages_for, public_view
from .commits import consume_response
from .provider import MODELS, append_json, call_broker, canonical, digest, utc_now
from .qualification import install_guard, readset_rows


def load_lines(path):
    path = Path(path)
    return [json.loads(line) for line in path.read_text().splitlines() if line] if path.exists() else []


def verify_lock(run):
    run = Path(run)
    lock = json.loads((run / "PROTOCOL_LOCK.json").read_text())
    for filename, expected in lock["file_sha256"].items():
        if hashlib.sha256(Path(filename).read_bytes()).hexdigest() != expected:
            raise ValueError("locked input/source changed: " + filename)
    return lock


def make_payload(model, messages, settings):
    return {"model": model, "messages": messages, **settings}


def check_dispatch_window(run, now=None):
    protocol = json.loads((Path(run) / "protocol.json").read_text())
    cutoff = protocol.get("dispatch_cutoff_at", protocol["deadline_at"])
    deadline = datetime.fromisoformat(cutoff.replace("Z", "+00:00"))
    if (now or datetime.now(timezone.utc)) >= deadline:
        raise TimeoutError("dispatch cutoff reached; retain missing opportunities for reporting")


def execute_one(run, stage, logical_id, model, view, arm, before, settings,
                variant="O", extra_meta=None):
    check_dispatch_window(run)
    messages, metadata = messages_for(view, arm, before, variant)
    metadata.update({"episode_id": view["episode_id"], "as_of": view["as_of"], "arm": arm,
                     "variant": variant, **(extra_meta or {})})
    payload = make_payload(model, messages, settings)
    started = time.monotonic()
    capture = call_broker(run, "chat", stage=stage, logical_id=logical_id,
                          payload=payload, metadata=metadata)
    if capture.get("broker_error") or capture.get("status") == "UNRESOLVED_PRIOR_ATTEMPT":
        raise RuntimeError("broker rejected or unresolved prior dispatch: " + canonical(capture))
    used_capture = capture
    retry_record = None
    if capture.get("http_status") in (429, 500, 502, 503, 504):
        time.sleep(1)
        check_dispatch_window(run)
        retry_id = "retry:" + logical_id
        retry_record = call_broker(run, "chat", stage="retry", logical_id=retry_id,
                                  retry_of=logical_id, payload=payload, metadata=metadata)
        if not retry_record.get("broker_error") and retry_record.get("status") != "UNRESOLVED_PRIOR_ATTEMPT":
            used_capture = retry_record
    consumed = consume_response(used_capture, view, before)
    return {"logical_id": logical_id, "stage": stage, "model": model, "arm": arm,
            "episode_id": view["episode_id"], "as_of": view["as_of"], "variant": variant,
            "input_metadata": metadata, "request_sha256": digest(payload),
            "capture_logical_id": used_capture["logical_id"], "first_http_status": capture.get("http_status"),
            "retry_logical_id": retry_record.get("logical_id") if retry_record else None,
            "elapsed_including_queue_s": time.monotonic() - started,
            "completed_at": utc_now(), **consumed}


def synthetic_views():
    def source(sid, issue, validity, weather):
        return {"source_id": sid, "station": "KSFO",
                "native_issue_time": "2023-01-10T" + issue[:2] + ":" + issue[2:] + ":00Z",
                "available_at": "2023-01-10T" + issue[:2] + ":" + f"{int(issue[2:])+2:02}" + ":00Z",
                "availability_basis": "synthetic_declared_lag",
                "raw_product": f"TAF KSFO 10{issue}Z {validity} {weather}"}
    old = source("SYNTHETIC-OLD", "1030", "1010/1112", "27005KT P6SM SCT020")
    new = source("SYNTHETIC-NEW", "1110", "1011/1112", "26004KT 2SM BR OVC004")
    view = {"episode_id": "SYNTHETIC-SMOKE", "target_id": "SYNTHETIC-SMOKE-5000m",
            "station": "KSFO", "target_start": "2023-01-10T12:00:00Z",
            "target_end": "2023-01-10T13:00:00Z", "threshold_metres": 5000,
            "as_of": "2023-01-10T11:20:00Z", "history_start": "2023-01-09T00:00:00Z"}
    return [
        {**view, "evidence": [old]},
        {**view, "evidence": [old, new]},
        {**view, "evidence": [old, new, copy.deepcopy(new)]},
        {**view, "evidence": [old, new, source("SYNTHETIC-LATER-PERIOD", "1115", "1018/1118", "30008KT P6SM SKC")]},
    ]


def smoke(run, round_index, settings):
    run = Path(run)
    view = synthetic_views()[round_index]
    before = initial_state()
    if round_index >= 1:
        before["fact_state"] = {"active_source_ids": ["SYNTHETIC-OLD"], "valid_start": "2023-01-10T10:00:00Z",
                                "valid_end": "2023-01-11T12:00:00Z", "relation_status": "RESOLVED"}
        before["probability"], before["probability_origin"] = 0.1, "SYNTHETIC_PREVIOUS_SUBMISSION"
    arm = "FRESH" if round_index == 0 else "STATEFUL"
    results = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs = {pool.submit(execute_one, run, "smoke", f"smoke:{round_index}:{model}",
                            model, view, arm, before, settings): model for model in MODELS}
        for job in as_completed(jobs):
            result = job.result()
            append_json(run / "smoke_steps.jsonl", result)
            results.append(result)
            print(canonical({"stage": "smoke", "round": round_index, "model": result["model"],
                             "valid": result["validation"]["valid"], "errors": result["validation"]["errors"],
                             "elapsed_s": result["elapsed_including_queue_s"]}), flush=True)
    return results


def run_main(run, max_workers=6):
    run = Path(run)
    lock = verify_lock(run)
    protocol = json.loads((run / "protocol.json").read_text())
    episodes = load_lines(run / "episodes.jsonl")
    rows = readset_rows(protocol["readset_path"])
    install_guard(rows)
    reader = NativeReader(protocol["readset_path"])
    existing = {row["logical_id"]: row for row in load_lines(run / "main_steps.jsonl")}
    writer_lock = threading.Lock()
    done = len(existing)
    models = lock["enabled_models"]
    total = len(episodes) * len(models) * 2 * 3

    def trajectory(episode, model, arm):
        nonlocal done
        before = initial_state()
        for index in range(3):
            logical_id = f"main:{episode['episode_id']}:{model}:{arm}:{index}"
            if logical_id in existing:
                record = existing[logical_id]
                if record["before"] != before:
                    raise ValueError("resume parent-state inconsistency")
                before = record["after"]
                continue
            view = public_view(episode, index, reader)
            record = execute_one(run, "main", logical_id, model, view, arm, before,
                                 lock["settings_by_model"][model], extra_meta={"checkpoint_index": index})
            record["checkpoint_index"] = index
            with writer_lock:
                append_json(run / "main_steps.jsonl", record)
                existing[logical_id] = record
                done += 1
                if done % 6 == 0 or not record["validation"]["valid"]:
                    print(canonical({"stage": "main", "complete": done, "expected": total,
                                     "model": model, "valid": record["validation"]["valid"],
                                     "errors": record["validation"]["errors"]}), flush=True)
            before = record["after"]

    futures = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for epi_index, episode in enumerate(episodes):
            rotated = models[epi_index % len(models):] + models[:epi_index % len(models)]
            for model in rotated:
                arms = ["FRESH", "STATEFUL"] if epi_index % 2 == 0 else ["STATEFUL", "FRESH"]
                for arm in arms:
                    futures.append(pool.submit(trajectory, episode, model, arm))
        for job in as_completed(futures):
            job.result()
    return {"completed": done, "expected": total}


def run_e2(run):
    run = Path(run)
    lock = verify_lock(run)
    protocol = json.loads((run / "protocol.json").read_text())
    episodes = {row["episode_id"]: row for row in load_lines(run / "episodes.jsonl")}
    main = {(row["episode_id"], row["model"], row["arm"], row["checkpoint_index"]): row
            for row in load_lines(run / "main_steps.jsonl")}
    old = {row["logical_id"] for row in load_lines(run / "paired_diagnostics.jsonl")}
    install_guard(readset_rows(protocol["readset_path"]))
    reader = NativeReader(protocol["readset_path"])
    jobs, completed = [], 0
    with ThreadPoolExecutor(max_workers=6) as pool:
        for eid in lock["e2_parent_ids"]:
            for model in lock["enabled_models"]:
                for arm in ("FRESH", "STATEFUL"):
                    parent = main[(eid, model, arm, 1)]
                    view = public_view(episodes[eid], 1, reader)
                    for variant in ("R", "D", "S"):
                        logical_id = f"e2:{eid}:{model}:{arm}:{variant}"
                        if logical_id in old:
                            continue
                        jobs.append(pool.submit(execute_one, run, "e2", logical_id, model, view, arm,
                                                parent["before"], lock["settings_by_model"][model], variant,
                                                {"anchor_logical_id": parent["logical_id"], "checkpoint_index": 1}))
        for job in as_completed(jobs):
            result = job.result()
            append_json(run / "paired_diagnostics.jsonl", result)
            completed += 1
            if completed % 6 == 0 or not result["validation"]["valid"]:
                print(canonical({"stage": "e2", "new_complete": completed, "valid": result["validation"]["valid"],
                                 "errors": result["validation"]["errors"]}), flush=True)
    return {"new_completed": completed}


def run_e3(run):
    run = Path(run)
    lock = verify_lock(run)
    protocol = json.loads((run / "protocol.json").read_text())
    episodes = {row["episode_id"]: row for row in load_lines(run / "episodes.jsonl")}
    refs = {row["episode_id"]: row for row in load_lines(run / "reference_manifest.jsonl")}
    main = {(row["episode_id"], row["model"], row["arm"], row["checkpoint_index"]): row
            for row in load_lines(run / "main_steps.jsonl")}
    old = {row["logical_id"] for row in load_lines(run / "repair_diagnostics.jsonl")}
    install_guard(readset_rows(protocol["readset_path"]))
    reader = NativeReader(protocol["readset_path"])
    eligibility, jobs = [], []
    with ThreadPoolExecutor(max_workers=6) as pool:
        for eid in lock["e3_parent_ids"]:
            for model in lock["enabled_models"]:
                previous = main[(eid, model, "STATEFUL", 1)]
                original = main[(eid, model, "STATEFUL", 2)]
                reference = refs[eid]["checkpoints"][1]["fact_state"]
                reason = "ELIGIBLE"
                if not previous["validation"]["valid"]:
                    reason = "INVALID_SUBMISSION_NOT_A_VERIFIED_REASONING_ERROR"
                elif previous["after"]["fact_state"] is None:
                    reason = "NO_EXPLICIT_FACT_STATE_TO_REPAIR"
                elif previous["after"]["fact_state"] == reference:
                    reason = "NO_NATURAL_FACT_ERROR"
                eligibility.append({"episode_id": eid, "model": model, "status": reason})
                if reason != "ELIGIBLE":
                    continue
                view = public_view(episodes[eid], 2, reader)
                for kind in ("repair", "sham"):
                    logical_id = f"e3:{eid}:{model}:{kind}"
                    if logical_id in old:
                        continue
                    before = copy.deepcopy(original["before"])
                    if kind == "repair":
                        before["fact_state"] = copy.deepcopy(reference)
                    # Sham is identity-preserving; both branches retain the same
                    # probability and original accepted parent identity.
                    extra = {"intervention": kind, "anchor_logical_id": original["logical_id"],
                             "checkpoint_index": 2, "original_before_sha256": digest(original["before"]),
                             "repair_changes_probability": False,
                             "state_accuracy_after_repair_may_include_mechanical_carryforward": True,
                             "sham_kind": "identity-preserving carrier, not token-exact repair-length match"}
                    jobs.append(pool.submit(execute_one, run, "e3", logical_id, model, view, "STATEFUL",
                                            before, lock["settings_by_model"][model], "O", extra))
        for job in as_completed(jobs):
            result = job.result()
            append_json(run / "repair_diagnostics.jsonl", result)
            print(canonical({"stage": "e3", "model": result["model"],
                             "valid": result["validation"]["valid"]}), flush=True)
    (run / "repair_eligibility.json").write_text(canonical(eligibility) + "\n")
    return {"eligible": sum(row["status"] == "ELIGIBLE" for row in eligibility), "new_branches": len(jobs)}
