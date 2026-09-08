"""Reconstruct an unsubmitted next batch from a stopped worker's saved prefix."""

import argparse
from collections import defaultdict
from pathlib import Path

from disastertrace.forecast_model import adapter, audit, package
from disastertrace.forecast_model.storage import now, write
from disastertrace.forecast_task.common import fingerprint, read
from disastertrace.forecast_task.protocol import request


def analyze(execution, run, worker):
    execution, run = Path(execution), Path(run)
    plan, public, slots = package.verify(execution, code=True)
    tokenizer = package.tokenizer_for(execution)
    review = audit.worker(execution, run, worker, tokenizer, verified=(plan, public, slots))
    if not review["completion_present"] or "context budget exceeded" not in (review["completion"]["error"] or ""):
        raise ValueError("worker did not terminate through the declared context guard")
    mapping = {s["slot_id"]: s for s in slots}
    histories = defaultdict(list)
    longest = []
    for capture in review["captures"]:
        slot = mapping[capture["slot_id"]]
        text = capture["final_text"]
        histories[slot["trajectory_id"]].append({"checkpoint_id": public["opportunities"][slot["opportunity_id"]]["checkpoint_id"],
                                               "final_text": text})
        longest.append({"slot_id": slot["slot_id"], "method": slot["method"],
                        "final_text_characters": len(text) if text else 0,
                        "content_tokens": capture["extraction"]["content_tokens"] if capture["extraction"] else 0})
    index = len(list((run / f"worker-{worker}").glob("batches/*/intent.json")))
    batches = package.batches(slots, public, worker)
    if index >= len(batches):
        raise ValueError("no next scheduled batch after stopped prefix")
    projected = []
    for slot in batches[index]:
        history = histories[slot["trajectory_id"]]
        messages = request(public, slot["opportunity_id"], slot["method"], history)
        prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=True)
        ids = tokenizer.encode(prompt, add_special_tokens=False)
        projected.append({"slot_id": slot["slot_id"], "method": slot["method"],
                          "opportunity_id": slot["opportunity_id"], "prior_answers": len(history),
                          "prior_final_text_characters": sum(len(h["final_text"]) if h["final_text"] else 0 for h in history),
                          "prompt_tokens": len(ids), "reserved_output": 8192, "context_limit": 32768,
                          "would_exceed_context": len(ids) + 8192 > 32768,
                          "reconstructed_messages_sha256": fingerprint(messages),
                          "actual_dispatch_intent_saved": False, "actual_model_call": False})
    if not any(item["would_exceed_context"] for item in projected):
        raise ValueError("saved prefix does not reproduce the context failure")
    return {"status": "reconstructed_stopped_context", "at": now(), "execution_id": plan["execution_id"],
            "worker_id": worker, "planned_worker_answers": review["planned"], "captured": len(review["captures"]),
            "unattempted_after_worker_stop": review["planned"] - review["attempted"],
            "next_batch_index": index, "projected_unsubmitted_batch": projected,
            "longest_saved_final_texts": sorted(longest, key=lambda item: (-item["final_text_characters"], item["slot_id"]))[:10],
            "projection_is_not_actual_model_input": True, "model_calls": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execution", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--worker", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.execution, args.run, args.worker)
    result["analysis_id"] = fingerprint(result)
    write(args.output, result)
    print({k: v for k, v in result.items() if k != "longest_saved_final_texts"}, flush=True)
