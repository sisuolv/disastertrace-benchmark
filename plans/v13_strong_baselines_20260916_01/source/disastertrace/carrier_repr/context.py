"""Measure all bound pair prompts without padding, truncation, or model generation."""

from collections import defaultdict
from statistics import mean, median

from disastertrace.forecast_task.common import canonical, fingerprint

from . import adapter, design, package, protocol


def inspect(root):
    plan, public, slots = package.verify(root, code=True)
    tokenizer = package.tokenizer_for(root)
    pairs, records = defaultdict(dict), []
    for slot in slots:
        if not slot["eligible"]:
            records.append({"slot_id": slot["slot_id"], "eligible": False, "prompt_tokens": None})
            continue
        messages = protocol.request(public, slot, [])
        item = adapter.prepare(messages, slot, tokenizer)
        length = len(item["prompt_token_ids"])
        restored = canonical(design.restore(messages))
        record = {
            "slot_id": slot["slot_id"],
            "pair_id": slot["pair_id"],
            "eligible": True,
            "encoding": slot["encoding"],
            "prompt_tokens": length,
            "request_sha256": item["request_sha256"],
            "restored_request_sha256": fingerprint(restored),
        }
        records.append(record)
        pairs[slot["pair_id"]][slot["encoding"]] = record
    differences = []
    for pair in pairs.values():
        if (
            set(pair) != {"json", "text"}
            or pair["json"]["restored_request_sha256"] != pair["text"]["restored_request_sha256"]
        ):
            raise ValueError("paired prompt information or eligibility differs")
        differences.append(pair["text"]["prompt_tokens"] - pair["json"]["prompt_tokens"])
    lengths = [r["prompt_tokens"] for r in records if r["eligible"]]
    return {
        "status": "passed",
        "execution_id": plan["execution_id"],
        "planned_answers": len(slots),
        "eligible_answers": sum(s["eligible"] for s in slots),
        "checked_answers": len(lengths),
        "maximum_prompt_tokens": max(lengths, default=0),
        "minimum_prompt_tokens": min(lengths, default=0),
        "paired_text_minus_json_tokens": {
            "pairs": len(differences),
            "minimum": min(differences, default=0),
            "maximum": max(differences, default=0),
            "mean": mean(differences) if differences else None,
            "median": median(differences) if differences else None,
            "zero_count": differences.count(0),
        },
        "model_calls": 0,
        "no_padding_or_truncation": True,
        "records": records,
    }
