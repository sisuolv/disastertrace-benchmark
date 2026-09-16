"""Sequential own-history trajectories with independent failure boundaries.

This offline adapter has no model transport. A future model adapter must perform
its context checks in prepare(), before a durable dispatch intent is published.
"""

import fcntl
import json
import re
from collections import Counter
from pathlib import Path

from .storage import canonical, digest, publish_bytes, read, write


class ContextLimit(ValueError):
    pass


def _received(slot, parser):
    raw = (slot / "raw.txt").read_bytes()
    intent = read(slot / "intent.json")
    result = {"raw_sha256": digest(raw), "request_sha256": intent["request_sha256"]}
    try:
        text = raw.decode("utf-8")
        if len(raw) > 65536:
            raise ValueError("answer exceeds common byte cap")
        result.update(status="received_valid", value=parser(text))
    except (ValueError, TypeError, KeyError, RecursionError) as error:
        result.update(status="received_invalid", error_type=type(error).__name__)
    return result


def run_trajectories(root, trajectories, backend, parser, *, backend_id, after_raw=None):
    if not trajectories or any(not re.fullmatch(r"[a-zA-Z0-9_-]+", key) for key in trajectories):
        raise ValueError("invalid trajectory identity")
    if any(not isinstance(rows, list) or not rows for rows in trajectories.values()):
        raise ValueError("each trajectory requires planned checkpoints")
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    with (root / "runner.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        plan = {
            "trajectories": trajectories,
            "trajectory_order": list(trajectories),
            "backend_id": backend_id,
            "origin": "offline_diagnostic",
        }
        if (root / "plan.json").exists():
            if read(root / "plan.json") != plan:
                raise ValueError("resume plan or backend identity changed")
        else:
            write(root / "plan.json", plan)
        outcomes = []
        for trajectory, templates in trajectories.items():
            carrier, stopped = None, False
            for index, template in enumerate(templates):
                slot = root / trajectory / f"{index:04d}"
                slot.mkdir(parents=True, exist_ok=True)
                request = json.loads(canonical(template))
                if "carrier" in request:
                    raise ValueError("caller cannot supply another trajectory's carrier")
                request["carrier"] = carrier
                req_hash = digest(canonical(request).encode())
                req_path, intent_path = slot / "request.json", slot / "intent.json"
                raw_path, outcome_path = slot / "raw.txt", slot / "outcome.json"
                if req_path.exists() and read(req_path) != request:
                    raise ValueError("captured request or self-history changed")
                if intent_path.exists() and read(intent_path) != {"request_sha256": req_hash}:
                    raise ValueError("dispatch intent does not bind this request")
                if raw_path.exists() and not intent_path.exists():
                    raise ValueError("unbound raw response")
                if stopped:
                    if intent_path.exists() or raw_path.exists():
                        raise ValueError("dependent checkpoint dispatched after trajectory stop")
                    result = {"status": "unattempted", "reason": "trajectory_stopped"}
                elif raw_path.exists():
                    result = _received(slot, parser)
                elif intent_path.exists():
                    result = {"status": "unknown", "request_sha256": req_hash}
                elif outcome_path.exists():
                    result = read(outcome_path)
                    if (
                        result.get("status") != "failed_preflight"
                        or result.get("request_sha256") != req_hash
                    ):
                        raise ValueError("unverifiable pre-dispatch outcome")
                else:
                    if not req_path.exists():
                        write(req_path, request)
                    try:
                        if hasattr(backend, "prepare"):
                            backend.prepare(json.loads(canonical(request)))
                    except Exception as error:
                        result = {
                            "status": "failed_preflight",
                            "request_sha256": req_hash,
                            "error_type": type(error).__name__,
                        }
                        write(slot / "preflight_error.json", {"error_type": type(error).__name__})
                    else:
                        write(intent_path, {"request_sha256": req_hash})
                        try:
                            raw = backend(json.loads(canonical(request)))
                            if not isinstance(raw, str):
                                raise TypeError("backend must return raw text")
                            publish_bytes(raw_path, raw.encode("utf-8"))
                        except Exception as error:
                            write(
                                slot / "transport_error.json", {"error_type": type(error).__name__}
                            )
                            result = {"status": "unknown", "request_sha256": req_hash}
                        else:
                            if after_raw is not None:
                                after_raw(slot)
                            result = _received(slot, parser)
                if outcome_path.exists():
                    if read(outcome_path) != result:
                        raise ValueError("outcome differs from captured evidence")
                else:
                    write(outcome_path, result)
                if result["status"] == "failed_preflight":
                    if (
                        not (slot / "preflight_error.json").exists()
                        or read(slot / "preflight_error.json").get("error_type")
                        != result["error_type"]
                    ):
                        raise ValueError("preflight outcome lacks failure evidence")
                if result["status"].startswith("received_"):
                    carrier = {
                        "raw": raw_path.read_bytes().decode("utf-8", errors="replace"),
                        "invalid": result["status"] == "received_invalid",
                        "missing": False,
                    }
                else:
                    stopped = True
                outcomes.append({"trajectory": trajectory, "checkpoint": index, **result})
        return {
            "origin": "offline_diagnostic",
            "eligible_for_llm_leaderboard": False,
            "planned": len(outcomes),
            "counts": dict(Counter(x["status"] for x in outcomes)),
            "outcomes": outcomes,
        }
