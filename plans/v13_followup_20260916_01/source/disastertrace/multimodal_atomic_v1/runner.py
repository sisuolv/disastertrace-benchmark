"""Exclusive, raw-first collection of independent tasks without answer repair."""

import time
from collections import Counter

from disastertrace.multimodal_v1.storage import canonical, digest, now, publish_bytes, write

from .scoring import parsed

ORIGIN = "local_vlm_atomic_development"


def collect(root, tasks, backend, execution_sha, not_after):
    root.mkdir(parents=True, exist_ok=False)
    write(
        root / "CLAIM.json",
        {"at": now(), "execution_sha256": execution_sha, "task_ids": [t["task_id"] for t in tasks]},
    )
    outcomes = []
    for task in tasks:
        slot = root / task["task_id"]
        slot.mkdir()
        write(slot / "request.json", task)
        request_sha = digest(canonical(task).encode())
        if time.time() + backend.settings["max_generation_seconds"] >= not_after:
            outcome = {"status": "unattempted", "reason": "execution_deadline"}
        else:
            try:
                inputs = backend.prepare(task, slot)
            except Exception as error:  # noqa: BLE001 - preserve each independent failure
                write(
                    slot / "preflight_error.json",
                    {"at": now(), "type": type(error).__name__, "message": str(error)[:300]},
                )
                outcome = {"status": "failed_preflight"}
            else:
                if time.time() + backend.settings["max_generation_seconds"] >= not_after:
                    outcome = {"status": "unattempted", "reason": "execution_deadline"}
                else:
                    write(
                        slot / "intent.json",
                        {
                            "at": now(),
                            "origin": ORIGIN,
                            "request_sha256": request_sha,
                            "execution_sha256": execution_sha,
                            "processor_sha256": digest((slot / "processor.json").read_bytes()),
                        },
                    )
                    try:
                        raw, generation = backend.generate(inputs)
                        if not isinstance(raw, str):
                            raise TypeError("backend returned non-text")
                        publish_bytes(slot / "raw.txt", raw.encode())
                        write(slot / "generation.json", generation)
                        outcome = parsed(raw, task["family"])
                    except Exception as error:  # noqa: BLE001 - unknown never implies a retry
                        write(
                            slot / "generation_error.json",
                            {
                                "at": now(),
                                "type": type(error).__name__,
                                "message": str(error)[:300],
                            },
                        )
                        outcome = {"status": "unknown"}
        outcome.update(origin=ORIGIN, request_sha256=request_sha)
        write(slot / "outcome.json", outcome)
        outcomes.append({"task_id": task["task_id"], **outcome})
        print(task["task_id"], outcome["status"], flush=True)
    result = {
        "origin": ORIGIN,
        "planned": len(tasks),
        "counts": dict(Counter(o["status"] for o in outcomes)),
        "outcomes": outcomes,
    }
    write(root / "COLLECTION.json", result)
    return result
