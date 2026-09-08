"""Reconstruct a context-blocked next batch from immutable captured model history."""

import argparse
import importlib
from collections import defaultdict
from pathlib import Path

from disastertrace.forecast_task.common import digest, fingerprint, read, write
from disastertrace.forecast_task.protocol import request

NAMESPACES = ("cohort_live", "compact_live", "prompt_role_live", "qwen_role_live")


def analyze(namespace, execution, run, worker):
    package = importlib.import_module("disastertrace." + namespace + ".package")
    audit = importlib.import_module("disastertrace." + namespace + ".audit")
    execution, run = Path(execution), Path(run)
    plan, public, slots = package.verify(execution, code=True)
    if plan["kind"] != "model":
        raise ValueError("an actual model prefix is required")
    tokenizer = package.tokenizer_for(execution)
    review = audit.worker(execution, run, worker, tokenizer, verified=(plan, public, slots))
    if (not review["completion_present"]
            or "context budget exceeded" not in (review["completion"]["error"] or "")):
        raise ValueError("worker did not terminate through the context guard")
    mapping = {s["slot_id"]: s for s in slots}
    histories, longest = defaultdict(list), []
    for capture in review["captures"]:
        slot = mapping[capture["slot_id"]]
        text = capture["final_text"]
        histories[slot["trajectory_id"]].append({
            "checkpoint_id": public["opportunities"][slot["opportunity_id"]]["checkpoint_id"],
            "final_text": text,
        })
        longest.append({"slot_id": slot["slot_id"], "method": slot["method"],
                        "characters": len(text or ""),
                        "whitespace_characters": sum(ch.isspace() for ch in text or "")})
    index = len(list((run / f"worker-{worker}").glob("batches/*/intent.json")))
    batches = package.batches(slots, public, worker)
    if index >= len(batches):
        raise ValueError("no next scheduled batch")
    settings, projected = plan["settings"], []
    role_policy = settings.get("prompt_role_policy")
    if role_policy not in (None, "system_contract_prepended_to_user_v1"):
        raise ValueError("unknown prompt role policy")
    for slot in batches[index]:
        history = histories[slot["trajectory_id"]]
        messages = request(public, slot["opportunity_id"], slot["method"], history)
        rendered = messages if role_policy is None else [
            {"role": "user", "content": messages[0]["content"] + "\n\n" + messages[1]["content"]}
        ]
        prompt = tokenizer.apply_chat_template(rendered, tokenize=False, add_generation_prompt=True,
                                               enable_thinking=settings["enable_thinking"])
        tokens = tokenizer.encode(prompt, add_special_tokens=False)
        projected.append({
            "slot_id": slot["slot_id"], "method": slot["method"], "opportunity_id": slot["opportunity_id"],
            "prior_answers": len(history), "prior_final_text_characters": sum(len(h["final_text"] or "") for h in history),
            "prompt_tokens": len(tokens), "reserved_output": settings["max_tokens"],
            "context_limit": settings["max_model_len"],
            "would_exceed_context": len(tokens) + settings["max_tokens"] > settings["max_model_len"],
            "reconstructed_logical_messages_sha256": fingerprint(messages),
            "reconstructed_rendered_messages_sha256": fingerprint(rendered),
            "actual_dispatch_intent_saved": False, "actual_model_call": False,
        })
    if not any(item["would_exceed_context"] for item in projected):
        raise ValueError("saved history does not reproduce the context stop")
    result = {
        "schema_version": "cohort_stopped_context_analysis_v1", "execution_id": plan["execution_id"],
        "worker_id": worker, "planned_worker_answers": review["planned"],
        "captured": len(review["captures"]), "unattempted_after_worker_stop": review["planned"] - review["attempted"],
        "next_batch_index": index, "projected_unsubmitted_batch": projected,
        "longest_saved_final_texts": sorted(longest, key=lambda r: (-r["characters"], r["slot_id"]))[:10],
        "projection_is_not_actual_model_input": True, "model_calls": 0,
        "completion_sha256": digest(run / f"worker-{worker}/completion.json"),
        "script_sha256": digest(__file__),
    }
    result["analysis_id"] = fingerprint(result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--namespace", choices=NAMESPACES, required=True)
    parser.add_argument("--execution", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--worker", type=int, choices=(0, 1), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    result = analyze(args.namespace, args.execution, args.run, args.worker)
    if args.verify:
        if result != read(args.output):
            raise ValueError("stopped-prefix reconstruction differs")
    else:
        write(args.output, result)
    print({k: v for k, v in result.items() if k != "longest_saved_final_texts"}, flush=True)
