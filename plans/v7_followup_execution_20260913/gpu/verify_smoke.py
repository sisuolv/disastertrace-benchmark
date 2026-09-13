"""Reconstruct raw tokens, persistence receipts, typed admission and E/F scores."""

import argparse
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path

from disastertrace.monitoring_fixed_v1.admission import (
    AdmissionEngine,
    AdmissionEvent,
    score_admitted,
)
from disastertrace.monitoring_fixed_v1.aviation import visible_e_status
from disastertrace.monitoring_fixed_v1.contracts import EvidenceBundle, fingerprint
from disastertrace.monitoring_fixed_v1.heads import model_messages, parse_response
from disastertrace.monitoring_v1.journal import EventJournal
from gpu_worker import digest, save
from transformers import AutoTokenizer

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from execute_admission import evaluator_outcomes, mission_inputs


def main(batch, out):
    out.mkdir(exist_ok=False, parents=True)
    plan = json.loads((batch / "PLAN.json").read_text())
    plan_sha = digest(batch / "PLAN.json")
    for name, sha in plan["files"].items():
        if digest(batch / name) != sha:
            raise ValueError("Frozen file changed: " + name)
    worker = batch / "worker-0"
    complete = json.loads((worker / "COMPLETE.json").read_text())
    hardware = json.loads((worker / "HARDWARE.json").read_text())
    if (
        complete["model_calls"] != 108
        or complete["plan_sha256"] != plan_sha
        or hardware["count"] != 1
        or "H100" not in hardware["name"]
        or hardware["hostname"] == plan["cci_hostname"]
    ):
        raise ValueError("GPU completion/hardware identity mismatch")
    tokenizer = AutoTokenizer.from_pretrained(
        plan["model"]["directory"], local_files_only=True
    )
    _, _, opportunities, fallbacks = mission_inputs()
    events, records, totals = {}, [], Counter()
    for item in plan["workers"]["0"]:
        cid = item["call_id"]
        request_path, response_path = (
            worker / (cid + "-request.json"),
            worker / (cid + "-response.json"),
        )
        request, response = (
            json.loads(request_path.read_text()),
            json.loads(response_path.read_text()),
        )
        commit = json.loads((worker / (cid + "-commit.json")).read_text())
        bundle = EvidenceBundle.restore(
            json.loads((batch / "policy" / (cid + ".json")).read_text())
        )
        p = bundle.policy_view()
        messages = model_messages(bundle, item["head"])
        ids = tokenizer(
            tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            ),
            add_special_tokens=False,
        )["input_ids"]
        if (
            request["messages"] != messages
            or request["input_ids"] != ids
            or fingerprint(messages) != item["messages_sha256"]
            or request["plan_sha256"] != plan_sha
            or response["plan_sha256"] != plan_sha
            or commit["plan_sha256"] != plan_sha
            or commit["call_id"] != cid
            or commit["head"] != item["head"]
            or response["call_id"] != cid
            or request["bundle_hash"] != bundle.bundle_hash
            or response["bundle_hash"] != bundle.bundle_hash
            or commit["bundle_hash"] != bundle.bundle_hash
            or tokenizer.decode(response["output_ids"], skip_special_tokens=True)
            != response["raw"]
            or response["input_tokens"] != len(ids)
            or response["output_tokens"] != len(response["output_ids"])
            or commit["request_sha256"] != digest(request_path)
            or commit["response_sha256"] != digest(response_path)
            or commit["raw_sha256"]
            != hashlib.sha256(response["raw"].encode()).hexdigest()
            or response["raw_sha256"] != commit["raw_sha256"]
            or not 0 < commit["completed_elapsed_us"] <= commit["persisted_elapsed_us"]
            or commit["wall_after_response_fsync_ns"] < commit["wall_started_ns"]
            or commit["logical_started_at"] != item["logical_started_at"]
        ):
            raise ValueError("Capture/receipt reconstruction failed: " + cid)
        totals["input_tokens"] += len(ids)
        totals["output_tokens"] += len(response["output_ids"])
        group = item["head"] + "." + item["condition"]
        stream = events.setdefault(group, [])
        stream.append(
            AdmissionEvent(
                cid + "-base",
                p["baseline"]["available_at"],
                "baseline",
                {"bundle": bundle.to_dict()},
            )
        )
        started = item["logical_started_at"]
        stream.append(
            AdmissionEvent(
                cid + "-begin",
                started,
                "begin",
                {
                    "call_id": cid,
                    "bundle": bundle.to_dict(),
                    "head": item["head"],
                    "executor": "Qwen3-8B.smoke.v1",
                },
            )
        )
        receipt = {
            "call_id": cid,
            "bundle_hash": bundle.bundle_hash,
            "raw": response["raw"],
            "raw_sha256": commit["raw_sha256"],
            "started_at": started,
            "completed_at": started + commit["completed_elapsed_us"],
            "persisted_at": started + commit["persisted_elapsed_us"],
            "expires_at": p["cutoff"],
            "cost": {
                "requests": 0,
                "bytes": len(response["raw"].encode()),
                "tokens": len(ids) + len(response["output_ids"]),
                "compute_ms": math.ceil(response["inference_seconds"] * 1000),
            },
            "ended_with_eos": response["ended_with_eos"],
            "head": item["head"],
            "executor": "Qwen3-8B.smoke.v1",
        }
        stream.append(
            AdmissionEvent(
                cid + "-complete", receipt["persisted_at"], "completion", receipt
            )
        )
        try:
            if not response["ended_with_eos"]:
                raise ValueError("unfinished")
            parsed = parse_response(response["raw"], bundle, item["head"])
            e_status = parsed.e_status
            probability = None if parsed.forecast is None else parsed.forecast.value
            error = None
        except (ValueError, TypeError) as exc:
            e_status = probability = None
            error = str(exc)
        expected_e = visible_e_status(bundle) if item["head"] != "f_only" else None
        records.append(
            {
                "call_id": cid,
                "original_call_id": item["original_call_id"],
                "opportunity_id": item["opportunity_id"],
                "region": item["region"],
                "head": item["head"],
                "condition": item["condition"],
                "raw": response["raw"],
                "parse_error": error,
                "e_status": e_status,
                "expected_e": expected_e,
                "e_correct": None if expected_e is None else expected_e == e_status,
                "candidate_probability": probability,
                "baseline_probability": p["baseline"]["forecast"]["value"],
                "candidate_changed_baseline": None
                if probability is None
                else probability != p["baseline"]["forecast"]["value"],
                "completed_elapsed_us": commit["completed_elapsed_us"],
                "persisted_elapsed_us": commit["persisted_elapsed_us"],
                "receipt_sha256": digest(worker / (cid + "-commit.json")),
            }
        )
    if any(totals[k] != complete[k] for k in totals):
        raise ValueError("Token total mismatch")
    arms, snapshots, statuses = {}, [], {}
    for group, stream in sorted(events.items()):
        path = out / (group + ".jsonl")
        with EventJournal(path) as journal:
            engine = AdmissionEngine(
                opportunities, fallbacks=fallbacks, journal=journal
            )
            engine.run(
                stream,
                until=max([o.cutoff for o in opportunities] + [e.time for e in stream]),
            )
        replay = AdmissionEngine.from_journal(path)
        if replay.snapshots != engine.snapshots or replay.attempts != engine.attempts:
            raise ValueError("Admission replay mismatch")
        statuses[group] = dict(Counter(r["status"] for r in engine.attempts))
        if not group.startswith("e_only"):
            arms[group] = path
        snapshots.extend({"arm": group, **r} for r in engine.snapshots.values())
    # A common baseline arm is replayed under the identical opportunity registry.
    sample_stream = next(iter(events.values()))
    baseline_path = out / "follow.jsonl"
    with EventJournal(baseline_path) as journal:
        engine = AdmissionEngine(opportunities, fallbacks=fallbacks, journal=journal)
        engine.run(
            [e for e in sample_stream if e.kind == "baseline"],
            until=max(o.cutoff for o in opportunities),
        )
    arms["follow"] = baseline_path
    outcomes = evaluator_outcomes(opportunities)
    save(out / "OUTCOME_REFERENCES.json", outcomes)
    score = score_admitted(outcomes, arms)
    e_scores = {}
    for group in sorted(events):
        if group.startswith("f_only"):
            continue
        selected = [r for r in records if r["head"] + "." + r["condition"] == group]
        e_scores[group] = {
            "registered": len(selected),
            "correct": sum(r["e_correct"] for r in selected),
            "expected_statuses": dict(Counter(r["expected_e"] for r in selected)),
        }
    report = {
        "schema": "disastertrace.independent_head_smoke_report.v1",
        "model_calls": 108,
        "model": "Qwen3-8B",
        "plan_sha256": plan_sha,
        "tokens": dict(totals),
        "all_raw_tokens_inputs_commits_verified": True,
        "all_admission_journals_replayed": True,
        "admission_statuses": statuses,
        "E": e_scores,
        "F": score,
        "parse_failures": sum(r["parse_error"] is not None for r in records),
        "candidate_changes": sum(
            r["candidate_changed_baseline"] is True for r in records
        ),
        "limitations": [
            "12 previously exposed opportunities",
            "one model, one repeat",
            "declared archive timing, not online validation",
            "E-only excluded from F denominator",
            "TAF coverage/version E heads not run",
            "no claim of independent C1/C2 benefit",
        ],
    }
    save(out / "REPORT.json", report)
    save(out / "RECORDS.json", records)
    save(out / "COMMITTED_FORECASTS.json", snapshots)
    print(
        json.dumps(
            {
                "calls": 108,
                "parse_failures": report["parse_failures"],
                "E": e_scores,
                "F_scores": score["scores"],
                "status": statuses,
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    main(args.batch.resolve(), args.output.resolve())
