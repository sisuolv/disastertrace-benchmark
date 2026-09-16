"""CPU reconstruction from frozen requests and raw captures, including missing slots."""

from collections import Counter
from datetime import datetime

from disastertrace.multimodal_v1.storage import canonical, digest, read

from .runner import ORIGIN
from .scoring import aggregate, parsed, score


def validate_plan(plan):
    ids = [t["task_id"] for t in plan["tasks"]]
    assigned = [tid for group in plan["assignments"].values() for tid in group]
    if len(set(ids)) != len(ids) or Counter(assigned) != Counter(ids):
        raise ValueError("tasks must be assigned exactly once")
    if len(ids) != plan["max_generations"]:
        raise ValueError("generation budget mismatch")
    if len(plan["assignments"]) != 4 or any(len(v) != 10 for v in plan["assignments"].values()):
        raise ValueError("expected four balanced workers")


def reconstruct(batch):
    execution = read(batch / "EXECUTION.json")
    execution_sha = digest((batch / "EXECUTION.json").read_bytes())
    for name, expected in execution["bound_files"].items():
        if digest((batch / name).read_bytes()) != expected:
            raise ValueError("frozen execution input changed: " + name)
    plan, refs = read(batch / "REQUEST_PLAN.json"), read(batch / "references.json")
    validate_plan(plan)
    tasks = {t["task_id"]: t for t in plan["tasks"]}
    rows, tokens, seconds, intents = [], 0, 0.0, 0
    hardware_ids = []
    for worker, ids in plan["assignments"].items():
        root = batch / "gpu_runs" / worker
        if (root / "HARDWARE.json").exists():
            hardware_ids.append(read(root / "HARDWARE.json")["nvidia_smi"])
        if (root / "live/CLAIM.json").exists():
            claim = read(root / "live/CLAIM.json")
            if claim["execution_sha256"] != execution_sha or claim["task_ids"] != ids:
                raise ValueError("worker claim identity mismatch")
        captured = (
            sorted(p.name for p in (root / "live").iterdir() if p.is_dir())
            if (root / "live").exists()
            else []
        )
        if set(captured) - set(ids):
            raise ValueError("unexpected unplanned capture")
        for tid in ids:
            task, slot = tasks[tid], root / "live" / tid
            outcome, finish = {"status": "unattempted"}, None
            if (slot / "request.json").exists() and read(slot / "request.json") != task:
                raise ValueError("captured request differs from public frozen task")
            if (slot / "intent.json").exists():
                intent = read(slot / "intent.json")
                if intent["origin"] != ORIGIN or intent["execution_sha256"] != execution_sha:
                    raise ValueError("incorrect model origin or execution")
                if intent["request_sha256"] != digest(canonical(task).encode()):
                    raise ValueError("intent request hash mismatch")
                if intent["processor_sha256"] != digest((slot / "processor.json").read_bytes()):
                    raise ValueError("processor capture hash mismatch")
                if datetime.fromisoformat(intent["at"]).timestamp() >= execution["not_after_unix"]:
                    raise ValueError("generation outside frozen window")
                if read(slot / "processor.json")["request_sha256"] != intent["request_sha256"]:
                    raise ValueError("processor bound to a different request")
                intents += 1
                outcome = {"status": "unknown"}
            if (slot / "raw.txt").exists():
                if not (slot / "intent.json").exists():
                    raise ValueError("raw capture without dispatch intent")
                outcome = parsed((slot / "raw.txt").read_text(), task["family"])
            if (slot / "generation.json").exists():
                if not (slot / "raw.txt").exists():
                    raise ValueError("generation metadata without raw text")
                generation = read(slot / "generation.json")
                if generation["output_tokens"] != len(generation["output_ids"]):
                    raise ValueError("output token count mismatch")
                if len(generation["output_ids"]) > execution["settings"]["max_new_tokens"]:
                    raise ValueError("output token cap exceeded")
                finish = generation["finish_reason"]
                tokens += generation["output_tokens"]
                seconds += generation["seconds"]
            if (slot / "preflight_error.json").exists() and outcome["status"] == "unattempted":
                outcome = {"status": "failed_preflight"}
            if (slot / "outcome.json").exists():
                cached = read(slot / "outcome.json")
                if cached["origin"] != ORIGIN or cached["request_sha256"] != digest(
                    canonical(task).encode()
                ):
                    raise ValueError("cached outcome identity mismatch")
                differs = cached["status"] != outcome["status"] or cached.get(
                    "value"
                ) != outcome.get("value")
                # Raw is still an observation if metadata publication was interrupted.
                interrupted_metadata = (
                    cached["status"] == "unknown"
                    and (slot / "raw.txt").exists()
                    and not (slot / "generation.json").exists()
                )
                if differs and not interrupted_metadata:
                    raise ValueError("cached outcome differs from raw reconstruction")
            row = score(task, refs[tid], outcome, finish)
            row["worker"] = worker
            rows.append(row)
    if intents > execution["max_generations"]:
        raise ValueError("dispatch budget exceeded")
    return {
        "schema": "mm-atomic-report-v1",
        "origin": ORIGIN,
        "execution_sha256": execution_sha,
        "eligible_for_leaderboard": False,
        "independent_events": 1,
        "planned": len(tasks),
        "dispatches": intents,
        "status_counts": dict(Counter(r["status"] for r in rows)),
        "finish_counts": dict(Counter(r["finish_reason"] or "absent" for r in rows)),
        "output_tokens": tokens,
        "generation_seconds_sum": seconds,
        "by_family": aggregate(rows),
        "rows": rows,
        "revision_diagnostic_gate": all(r["strict_correct"] for r in rows),
        "revision_gate_definition": "all 40 prespecified atomic tasks strict-correct with EOS",
        "limits": [
            "one development event",
            "six map-site cells: five inside, one outside",
            "logic facts are privileged synthetic inputs",
            "selection sees metadata only",
            "static tasks do not measure temporal revision or cross-event generalization",
            "query grids supplied: locator success is not independent localization",
            "no inferential statistics or combined capability ranking",
        ],
    }
