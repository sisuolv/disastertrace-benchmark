"""One-use live collection with durable intents and no answer replacement."""

import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from disastertrace.multimodal_v1.storage import canonical, digest, now, publish_bytes, write
from disastertrace.multimodal_v1.types import ModelCommit

ORIGIN = "local_vlm_development"


def parsed(raw):
    try:
        return {"status": "received_valid", "value": asdict(ModelCommit.parse(raw))}
    except (ValueError, TypeError, KeyError, RecursionError) as error:
        return {"status": "received_invalid", "error_type": type(error).__name__}


def collect(root, plan, backend):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    # Atomic publication consumes the run even if its worker dies before generation.
    write(
        root / "CLAIM.json",
        {"at": now(), "plan_sha256": digest(canonical(plan).encode()), "origin": ORIGIN},
    )
    outcomes = []
    for trajectory in plan["trajectories"]:
        carrier, stopped = None, False
        for index, template in enumerate(trajectory["requests"]):
            slot = root / trajectory["id"] / f"{index:04d}"
            slot.mkdir(parents=True, exist_ok=False)
            request = json.loads(canonical(template))
            if "carrier" in request:
                raise ValueError("templates cannot inject a carrier")
            request["carrier"] = carrier
            write(slot / "request.json", request)
            request_hash = digest(canonical(request).encode())
            if stopped:
                outcome = {"status": "unattempted", "reason": "trajectory_stopped"}
            else:
                try:
                    inputs = backend.prepare(request, slot)
                except Exception as error:  # noqa: BLE001 - isolate any backend preflight failure
                    write(
                        slot / "preflight_error.json",
                        {
                            "at": now(),
                            "error_type": type(error).__name__,
                            "error": str(error)[:300],
                        },
                    )
                    outcome = {"status": "failed_preflight", "error_type": type(error).__name__}
                else:
                    write(
                        slot / "intent.json",
                        {
                            "at": now(),
                            "request_sha256": request_hash,
                            "processor_sha256": digest((slot / "processor.json").read_bytes()),
                            "origin": ORIGIN,
                        },
                    )
                    try:
                        raw, generation = backend.generate(inputs)
                        if not isinstance(raw, str):
                            raise TypeError("backend returned non-text")
                        # Publish raw before parsing; generation errors never trigger retries.
                        publish_bytes(slot / "raw.txt", raw.encode())
                        write(slot / "generation.json", generation)
                        outcome = parsed(raw)
                    except Exception as error:  # noqa: BLE001 - unknown dispatches must never retry
                        write(
                            slot / "generation_error.json",
                            {
                                "at": now(),
                                "error_type": type(error).__name__,
                                "error": str(error)[:300],
                            },
                        )
                        outcome = {"status": "unknown"}
            outcome.update(request_sha256=request_hash, origin=ORIGIN)
            write(slot / "outcome.json", outcome)
            if outcome["status"].startswith("received_"):
                carrier = {
                    "raw": (slot / "raw.txt").read_text(),
                    "invalid": outcome["status"] == "received_invalid",
                    "missing": False,
                }
            else:
                stopped = True
            row = {
                "trajectory": trajectory["id"],
                "checkpoint": template["checkpoint"],
                "index": index,
                **outcome,
            }
            outcomes.append(row)
            print(json.dumps({k: v for k, v in row.items() if k != "value"}), flush=True)
    summary = {
        "origin": ORIGIN,
        "eligible_for_llm_leaderboard": False,
        "planned": len(outcomes),
        "counts": dict(Counter(x["status"] for x in outcomes)),
        "outcomes": outcomes,
    }
    write(root / "COLLECTION.json", summary)
    return summary
