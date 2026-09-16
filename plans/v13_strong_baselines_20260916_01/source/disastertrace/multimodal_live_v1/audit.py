"""Reconstruct a complete or interrupted live run without importing Torch."""

import argparse
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from disastertrace.multimodal_v1.scoring import score_trajectory
from disastertrace.multimodal_v1.storage import canonical, digest, read, write
from disastertrace.multimodal_v1.types import ModelCommit


def reconstruct(batch, references):
    plan = read(batch / "REQUEST_PLAN.json")
    execution = read(batch / "EXECUTION.json")
    if digest((batch / "REQUEST_PLAN.json").read_bytes()) != execution["plan_sha256"]:
        raise ValueError("plan changed")
    live = batch / "gpu_run/live"
    if (live / "CLAIM.json").exists():
        claim = read(live / "CLAIM.json")
        if claim["origin"] != "local_vlm_development" or claim["plan_sha256"] != digest(
            canonical(plan).encode()
        ):
            raise ValueError("unbound live claim")
    counts, finish, summaries, captures = Counter(), Counter(), {}, []
    attempts, returned, output_tokens = 0, 0, 0
    for trajectory in plan["trajectories"]:
        carrier, stopped, outcomes, refs = None, False, [], []
        for index, template in enumerate(trajectory["requests"]):
            slot = live / trajectory["id"] / f"{index:04d}"
            expected = dict(template, carrier=carrier)
            expected_hash = digest(canonical(expected).encode())
            intent_path, raw_path = slot / "intent.json", slot / "raw.txt"
            if (slot / "request.json").exists() and read(slot / "request.json") != expected:
                raise ValueError("request/carrier differs from own captured history")
            if stopped and intent_path.exists():
                raise ValueError("descendant dispatch after unknown/preflight failure")
            if raw_path.exists() and not intent_path.exists():
                raise ValueError("raw capture without dispatch intent")
            if intent_path.exists():
                attempts += 1
                intent = read(intent_path)
                if (
                    intent["origin"] != "local_vlm_development"
                    or intent["request_sha256"] != expected_hash
                ):
                    raise ValueError("intent binding failed")
                processor = read(slot / "processor.json")
                if intent["processor_sha256"] != digest((slot / "processor.json").read_bytes()):
                    raise ValueError("processor manifest changed")
                if processor["request_sha256"] != expected_hash:
                    raise ValueError("processor request mismatch")
                if processor["prompt_sha256"] != digest((slot / "prompt.txt").read_bytes()):
                    raise ValueError("prompt changed")
                for asset in processor["assets"]:
                    if (
                        digest((slot / ("image-" + str(asset["index"]) + ".png")).read_bytes())
                        != asset["sha256"]
                    ):
                        raise ValueError("image capture changed")
                if raw_path.exists() and (slot / "generation.json").exists():
                    raw = raw_path.read_bytes().decode("utf-8")
                    try:
                        outcome = {
                            "status": "received_valid",
                            "value": asdict(ModelCommit.parse(raw)),
                        }
                    except (ValueError, TypeError, KeyError, RecursionError) as error:
                        outcome = {"status": "received_invalid", "error_type": type(error).__name__}
                    carrier = {
                        "raw": raw,
                        "invalid": outcome["status"] == "received_invalid",
                        "missing": False,
                    }
                    generation = read(slot / "generation.json")
                    if generation["output_tokens"] != len(generation["output_ids"]):
                        raise ValueError("output token count mismatch")
                    returned += 1
                    output_tokens += generation["output_tokens"]
                    finish[generation["finish_reason"]] += 1
                    if generation["output_tokens"] > execution["settings"]["max_new_tokens"]:
                        raise ValueError("output budget exceeded")
                    captures.append(
                        {
                            "trajectory": trajectory["id"],
                            "checkpoint": template["checkpoint"],
                            "input_tokens": processor["input_tokens"],
                            "visual_tokens": processor["visual_tokens"],
                            "images": len(processor["assets"]),
                            "output_tokens": generation["output_tokens"],
                            "seconds": generation["seconds"],
                            "raw_sha256": digest(raw_path.read_bytes()),
                        }
                    )
                else:
                    outcome, stopped = {"status": "unknown"}, True
            elif (slot / "preflight_error.json").exists() and not stopped:
                outcome = {
                    "status": "failed_preflight",
                    "error_type": read(slot / "preflight_error.json")["error_type"],
                }
                stopped = True
            else:
                outcome, stopped = {"status": "unattempted", "reason": "trajectory_stopped"}, True
            stored_path = slot / "outcome.json"
            if stored_path.exists():
                stored = read(stored_path)
                if {
                    k: v for k, v in stored.items() if k not in {"request_sha256", "origin"}
                } != outcome:
                    raise ValueError("stored outcome disagrees with raw reconstruction")
                if (
                    stored.get("origin") != "local_vlm_development"
                    or stored.get("request_sha256") != expected_hash
                ):
                    raise ValueError("outcome identity mismatch")
            counts[outcome["status"]] += 1
            outcomes.append(outcome)
            refs.append(references[trajectory["branch"]][int(template["checkpoint"][1:])])
        summaries[trajectory["id"]] = score_trajectory(refs, outcomes)
    if attempts > 12 or sum(counts.values()) != 12:
        raise ValueError("fixed opportunity budget violated")
    strict = sum(x["strict_checkpoints"]["numerator"] for x in summaries.values())
    return {
        "status": "reconstructed",
        "origin": "local_vlm_development",
        "planned": 12,
        "event_count": 1,
        "eligible_for_llm_leaderboard": False,
        "counts": dict(counts),
        "generation_intents": attempts,
        "returned": returned,
        "output_tokens": output_tokens,
        "finish_reasons": dict(finish),
        "strict_correct": strict,
        "strict_denominator": 12,
        "trajectories": summaries,
        "captures": captures,
        "interface_gate": counts["received_valid"] == 12 and finish["eos"] == 12,
        "limitations": [
            "one development event",
            "controlled official-data renderings",
            "free greedy decoding",
            "distinct information sets; accuracy differences are not pure modality causal effects",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--references", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = reconstruct(args.batch, read(args.references))
    write(args.output, report)
    print(
        json.dumps(
            {k: v for k, v in report.items() if k not in {"trajectories", "captures"}}, indent=2
        )
    )
