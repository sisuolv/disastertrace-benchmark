"""Fresh program histories and full-denominator scoring; never model captures."""

from collections import defaultdict

from .common import fingerprint
from .protocol import request
from .public_resolver import POLICIES, final_text
from .scoring import summarize


def collect_program(public, slots, policy):
    if policy not in POLICIES:
        raise ValueError("unknown diagnostic policy")
    histories, captures, requests = defaultdict(list), [], {}
    for slot in slots:
        history = histories[slot["trajectory_id"]]
        messages = request(public, slot["opportunity_id"], slot["method"], history)
        request_hash = fingerprint(messages)
        requests[request_hash] = messages
        text = final_text(messages, policy)
        captures.append(
            {
                "slot_id": slot["slot_id"],
                "origin": "public_program_diagnostic",
                "policy": policy,
                "request_sha256": request_hash,
                "final_text": text,
            }
        )
        history.append(
            {
                "checkpoint_id": public["opportunities"][slot["opportunity_id"]]["checkpoint_id"],
                "final_text": text,
            }
        )
    return captures, requests


def run_programs(public, private, slots):
    captures, scores, requests = {}, {}, {}
    for policy in POLICIES:
        captured, rendered = collect_program(public, slots, policy)
        score = summarize(slots, captured, public, private)
        if policy == "latest_explicit":
            if score["counts"]["all_correct"] != len(slots):
                raise ValueError("independent public resolver disagrees with references")
            if score["counts"]["shape_valid"] != len(slots):
                raise ValueError("legal diagnostic violated the output contract")
        captures[policy], scores[policy] = captured, score
        requests.update(rendered)
    return {"captures": captures, "scores": scores, "requests": requests}
