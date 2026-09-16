"""Reconstruct all worker histories from raw records and retain the global denominator."""

import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from disastertrace.forecast_task.common import digest, fingerprint, read
from disastertrace.forecast_task.protocol import request
from disastertrace.forecast_task.scoring import summarize

from . import adapter, package
from .backend import DIAGNOSTIC_ORIGIN, MODEL_ORIGIN, validate_observation
from .storage import write


def _time(value):
    stamp = datetime.fromisoformat(value)
    if stamp.utcoffset() is None:
        raise ValueError("journal time lacks timezone")
    return stamp


def _identity(record, identity):
    if any(record.get(key) != value for key, value in identity.items()):
        raise ValueError("journal origin/phase/worker ownership differs")


def _files(run, allowed):
    seen, temps = {}, {}
    for path in sorted(run.rglob("*")):
        if path.is_symlink():
            raise ValueError("symlink in worker journal")
        if path.is_file():
            name = path.relative_to(run).as_posix()
            if name in allowed:
                seen[name] = digest(path)
            elif re.fullmatch(r"\.[^.]+\.json\.[0-9a-f]{32}\.tmp", path.name):
                temps[name] = digest(path)
            else:
                raise ValueError("unexplained worker journal file: " + name)
    return seen, temps


def worker(root, run_root, worker_id, tokenizer, *, verified=None):
    root, run_root = Path(root), Path(run_root)
    plan, public, slots = verified or package.verify(root, code=True)
    mode = "model" if plan["kind"] == "model" else "diagnostic"
    if plan["kind"] == "preflight":
        raise ValueError("preflight has no scoring run")
    run = run_root / f"worker-{worker_id}"
    count = sum(s["worker_id"] == worker_id for s in slots)
    claim_path = run_root / "registry" / f"worker-{worker_id}.json"
    if not (run / "manifest.json").exists():
        seen, temps = _files(run, set()) if run.exists() else ({}, {})
        if claim_path.exists():
            claim = read(claim_path)
            if (
                claim["execution_id"] != plan["execution_id"]
                or claim["worker_id"] != worker_id
                or claim["phase_id"] != plan["phase_id"]
                or claim["mode"] != mode
            ):
                raise ValueError("stale claim without manifest")
        return {
            "worker_id": worker_id,
            "status": "absent_manifest",
            "planned": count,
            "captures": [],
            "attempted": 0,
            "raw_returned": 0,
            "parsed_saved": 0,
            "unknown_outcomes": 0,
            "recovered_raw": 0,
            "files": seen,
            "temporary_files": temps,
            "claim_present": claim_path.exists(),
            "completion_present": False,
            "prompt_tokens_reserved": 0,
            "finish_reasons": {},
        }
    manifest = read(run / "manifest.json")
    claim = read(claim_path)
    identity = {
        "execution_id": plan["execution_id"],
        "phase_id": plan["phase_id"],
        "worker_id": worker_id,
        "mode": mode,
        "origin": MODEL_ORIGIN if mode == "model" else DIAGNOSTIC_ORIGIN,
        "run_path": str(Path(plan["run_root"]) / f"worker-{worker_id}")
        if mode == "model"
        else manifest["run_path"],
    }
    _identity(claim, identity)
    if manifest != {**claim, "claim_sha256": fingerprint(claim)}:
        raise ValueError("manifest and exclusive worker claim disagree")
    previous_at = _time(claim["created_at"])
    allowed = {"manifest.json"}
    observed = None
    if (run / "runtime.json").exists():
        runtime = read(run / "runtime.json")
        _identity(runtime, identity)
        observed = runtime["observation"]
        if mode == "model":
            validate_observation(observed, plan)
        elif observed.get("origin") != DIAGNOSTIC_ORIGIN or observed.get("model_calls") != 0:
            raise ValueError("diagnostic runtime provenance differs")
        if _time(runtime["at"]) < previous_at:
            raise ValueError("runtime observation predates claim")
        previous_at = _time(runtime["at"])
        allowed.add("runtime.json")
    histories, captures, attempted, returned, parsed, recovered = defaultdict(list), [], 0, 0, 0, 0
    interrupted = False
    prompt_tokens_reserved = 0
    finishes = Counter()
    for batch_index, batch in enumerate(package.batches(slots, public, worker_id)):
        folder = run / "batches" / f"{batch_index:06d}"
        prefix = f"batches/{batch_index:06d}/"
        if not (folder / "intent.json").exists():
            continue
        if interrupted or batch_index != len([x for x in allowed if x.endswith("/intent.json")]):
            raise ValueError("journal continues after a gap or incomplete batch")
        if observed is None:
            raise ValueError("dispatch intent lacks a runtime observation")
        expected = [
            adapter.prepare(
                request(public, s["opportunity_id"], s["method"], histories[s["trajectory_id"]]),
                s,
                tokenizer,
            )
            for s in batch
        ]
        intent = read(folder / "intent.json")
        _identity(intent, identity)
        if intent["batch_index"] != batch_index or intent["prepared"] != expected:
            raise ValueError("request/carrier/sampling or batch order differs")
        intent_at = _time(intent["at"])
        if intent_at < previous_at:
            raise ValueError("nonmonotonic intent")
        previous_at = intent_at
        allowed.add(prefix + "intent.json")
        if not (folder / "started.json").exists():
            interrupted = True
            continue
        started = read(folder / "started.json")
        _identity(started, identity)
        if started["intent_sha256"] != fingerprint(intent) or _time(started["at"]) < intent_at:
            raise ValueError("started marker binding/time differs")
        if plan["deadline_utc"] and _time(started["at"]) >= _time(plan["deadline_utc"]):
            raise ValueError("dispatch begins after phase deadline")
        previous_at = _time(started["at"])
        attempted += len(batch)
        prompt_tokens_reserved += sum(len(p["prompt_token_ids"]) for p in expected)
        allowed.add(prefix + "started.json")
        if not (folder / "raw.json").exists():
            interrupted = True
            continue
        raw = read(folder / "raw.json")
        _identity(raw, identity)
        if raw["intent_sha256"] != fingerprint(intent) or _time(raw["at"]) < previous_at:
            raise ValueError("raw binding/time differs")
        previous_at = _time(raw["at"])
        results = raw["results"]
        by_id = {r["attempt_id"]: r for r in results}
        if len(by_id) != len(results) or not set(by_id) <= {s["attempt_id"] for s in batch}:
            raise ValueError("duplicate or unknown raw attempt")
        allowed.add(prefix + "raw.json")
        returned += len(results)
        for slot, prepared in zip(batch, expected):
            if slot["attempt_id"] not in by_id:
                continue
            result = by_id[slot["attempt_id"]]
            if mode == "model" and result.get("diagnostic_missing"):
                raise ValueError("diagnostic missing marker in model output")
            capture = adapter.parse_result(
                result, prepared, tokenizer, diagnostic=mode == "diagnostic"
            )
            if result["candidates"]:
                finishes[result["candidates"][0]["finish_reason"]] += 1
                tokens = result["candidates"][0]["output_token_ids"]
                vocab_size = read(root / "resources/tokenizer/config.json")["vocab_size"]
                if any(t >= vocab_size for t in tokens):
                    raise ValueError("output token outside bound model vocabulary")
            parsed_path = folder / "parsed" / (slot["attempt_id"] + ".json")
            if parsed_path.exists():
                saved = read(parsed_path)
                _identity(saved, identity)
                if (
                    saved["attempt_id"] != slot["attempt_id"]
                    or saved["capture"] != capture
                    or saved["raw_sha256"] != fingerprint(raw)
                    or _time(saved["at"]) < previous_at
                ):
                    raise ValueError("parsed cache differs from independent raw reconstruction")
                previous_at = _time(saved["at"])
                allowed.add(prefix + "parsed/" + parsed_path.name)
                parsed += 1
            else:
                recovered += 1
                interrupted = True
            captures.append(
                {
                    **capture,
                    "attempt_id": slot["attempt_id"],
                    "origin": identity["origin"],
                    "worker_id": worker_id,
                }
            )
            histories[slot["trajectory_id"]].append(
                {
                    "checkpoint_id": public["opportunities"][slot["opportunity_id"]][
                        "checkpoint_id"
                    ],
                    "final_text": capture["final_text"],
                }
            )
        if raw["backend_error"] or len(results) != len(batch):
            interrupted = True
    completion = None
    if (run / "completion.json").exists():
        completion = read(run / "completion.json")
        _identity(completion, identity)
        if (
            _time(completion["at"]) < previous_at
            or completion["attempted"] != attempted
            or completion["raw_returned"] != returned
            or completion["parsed_saved"] != parsed
        ):
            raise ValueError("completion counters/time disagree with durable journal")
        if completion["stop_reason"] == "complete" and (len(captures) != count or interrupted):
            raise ValueError("false complete claim")
        allowed.add("completion.json")
    files, temps = _files(run, allowed)
    return {
        "worker_id": worker_id,
        "status": "complete"
        if completion and completion["stop_reason"] == "complete"
        else "stopped_prefix",
        "planned": count,
        "captures": captures,
        "attempted": attempted,
        "raw_returned": returned,
        "parsed_saved": parsed,
        "unknown_outcomes": attempted - returned,
        "recovered_raw": recovered,
        "files": files,
        "temporary_files": temps,
        "claim_present": True,
        "claim_sha256": fingerprint(claim),
        "completion_present": completion is not None,
        "completion": completion,
        "runtime_observation": observed,
        "prompt_tokens_reserved": prompt_tokens_reserved,
        "finish_reasons": dict(finishes),
        "claim_created_at": claim["created_at"],
    }


def aggregate(root, run_root, *, tokenizer=None):
    root, run_root = Path(root), Path(run_root)
    verified = package.verify(root, code=True)
    plan, public, slots = verified
    tokenizer = tokenizer or package.tokenizer_for(root)
    if run_root.exists():
        for child in run_root.iterdir():
            if child.is_symlink() or child.name not in {
                "registry",
                "provenance.json",
                "worker-0",
                "worker-1",
                "worker-2",
                "worker-3",
            }:
                raise ValueError("unknown global worker/run entry")
        if (run_root / "registry").exists():
            _files(run_root / "registry", {f"worker-{i}.json" for i in range(4)})
    workers = [worker(root, run_root, i, tokenizer, verified=verified) for i in range(4)]
    platform_jobs = None
    if plan["kind"] == "model":
        from .provenance import validate_phase

        platform_jobs = validate_phase(read(run_root / "provenance.json"), plan, workers, slots)
    captures = [capture for w in workers for capture in w["captures"]]
    if len({c["attempt_id"] for c in captures}) != len(captures):
        raise ValueError("global attempt identity collision")
    mapping = {c["slot_id"]: c for c in captures}
    if len(mapping) != len(captures):
        raise ValueError("global duplicate source slot")
    ordered = [mapping[s["slot_id"]] for s in slots if s["slot_id"] in mapping]
    score = summarize(slots, ordered, public, read(root / "task/data/private_reference.json"))
    counts = {
        k: sum(w[k] for w in workers)
        for k in (
            "planned",
            "attempted",
            "raw_returned",
            "parsed_saved",
            "unknown_outcomes",
            "recovered_raw",
            "prompt_tokens_reserved",
        )
    }
    counts["unattempted"] = len(slots) - counts["attempted"]
    counts["max_requested_output_tokens"] = counts["attempted"] * adapter.SETTINGS["max_tokens"]
    counts.update(
        {
            name: sum(c["extraction"][name] for c in ordered if c["extraction"] is not None)
            for name in (
                "reasoning_tokens",
                "content_tokens",
                "delimiter_tokens",
                "terminal_tokens",
            )
        }
    )
    counts["output_tokens"] = sum(
        counts[k]
        for k in ("reasoning_tokens", "content_tokens", "delimiter_tokens", "terminal_tokens")
    )
    counts["extraction_errors"] = sum(
        bool(c["extraction"] and c["extraction"]["extraction_error"]) for c in ordered
    )
    if counts["attempted"] > 1542 or counts["max_requested_output_tokens"] > 12632064:
        raise ValueError("global generation bound exceeded")
    report = {
        "schema_version": "forecast_second_model_global_audit_v1",
        "execution_id": plan["execution_id"],
        "phase_id": plan["phase_id"],
        "kind": plan["kind"],
        "counts": counts,
        "workers": workers,
        "scores": score,
        "status_counts": dict(Counter(w["status"] for w in workers)),
        "analysis": "closed_loop_native_trajectories; descriptive two-storm development only",
    }
    report["platform_jobs"] = platform_jobs
    report["finish_reasons"] = dict(sum((Counter(w["finish_reasons"]) for w in workers), Counter()))
    report["report_id"] = fingerprint(report)
    return report


def report(root, run_root, output, *, verify=False):
    result = aggregate(root, run_root)
    if verify:
        if read(output) != result:
            raise ValueError("saved global report differs from reconstruction")
    else:
        write(output, result)
    return {
        "report_id": result["report_id"],
        "counts": result["counts"],
        "score_counts": result["scores"]["counts"],
    }
