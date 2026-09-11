"""Reconstruct decisions and read histories from frozen inputs and raw outputs."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

from common import ROOT, dump
from evidence_core import certificates, score
from model_adapter import sha_file


def decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result
    try:
        value = json.loads(raw, object_pairs_hook=pairs)
    except (ValueError, TypeError):
        return None, "invalid_json"
    if not isinstance(value, dict):
        return None, "non_object"
    if list(value) == ["read"] and isinstance(value["read"], str):
        return value, "read"
    if (set(value) == {"decision", "citations"} and isinstance(value["decision"], str)
            and value["decision"] in ("yes", "no", "unknown") and isinstance(value["citations"], list)
            and all(type(x) is str for x in value["citations"])):
        return value, "final"
    return None, "invalid_schema"


def reconstruct(batch, task, worker, public):
    slot = batch / "runs" / worker / "trajectories" / task["id"]
    bundle = public[task["episode"]][task["condition"]]
    state = bundle["initial"]
    read_ids = list(state["public"]["read_ids"])
    answer, status, wrappers = None, "not_executed", []
    calls = []
    if not slot.exists():
        return read_ids, answer, status, calls, wrappers
    turns = sorted(slot.glob("turn-*"))
    for index, turn in enumerate(turns):
        if json.loads((turn / "request.json").read_text()) != state:
            raise ValueError("request differs from frozen public state")
        if not (turn / "intent.json").exists():
            status = "preparation_failed"
            break
        intent = json.loads((turn / "intent.json").read_text())
        if intent["request_sha256"] != sha_file(turn / "request.json"):
            raise ValueError("request hash changed")
        if not (turn / "response.json").exists():
            status = "runtime_error" if (turn / "ERROR.json").exists() else "incomplete_capture"
            break
        response = json.loads((turn / "response.json").read_text())
        processor = json.loads((turn / "processor.json").read_text())
        raw = (turn / "raw.txt").read_text()
        if response["raw_sha256"] != sha_file(turn / "raw.txt"):
            raise ValueError("raw response changed")
        if processor["prompt_sha256"] != sha_file(turn / "prompt.txt"):
            raise ValueError("actual prompt changed")
        value, kind = decode(raw)
        calls.append({"turn": index, "seconds": response["seconds"], "output_tokens": response["generated_tokens"],
            "input_tokens": processor["input_tokens"], "visual_tokens": processor["visual_tokens"],
            "images": len(processor["assets"]), "ended_eos": response["ended_eos"], "kind": kind})
        try:
            candidate = json.loads(raw)
            if set(candidate) == {"final_contract"}:
                recovered, recovered_kind = decode(json.dumps(candidate["final_contract"]))
                if recovered_kind == "final":
                    wrappers.append({"turn": index, "answer": recovered, "read_ids": list(read_ids)})
        except (ValueError, TypeError):
            pass
        if not response["ended_eos"]:
            status = "generation_incomplete"
            break
        if kind == "final":
            answer, status = value, "final"
            break
        if kind != "read":
            status = kind
            break
        cid = value["read"]
        catalog = {x["id"]: x for x in state["public"]["catalog"]}
        if (task["mode"] != "active" or cid not in catalog or cid in read_ids
                or catalog[cid]["cost"] > state["public"]["remaining_budget"]):
            status = "illegal_read"
            break
        read_ids = sorted(read_ids + [cid])
        state = bundle["states"][",".join(read_ids)]
        status = "unfinished"
    if (slot / "FINAL.json").exists():
        final = json.loads((slot / "FINAL.json").read_text())
        if final["status"] == "deadline_not_called" and status in {"not_executed", "unfinished"}:
            status = "deadline_not_called"
        if (final["read_ids"], final["answer"], final["status"]) != (read_ids, answer, status):
            raise ValueError("independent replay disagrees with stored final: " + task["id"])
    return read_ids, answer, status, calls, wrappers


def aggregate(rows, keys):
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[k] for k in keys)].append(row)
    results = []
    for group, items in sorted(groups.items()):
        result = {**dict(zip(keys, group)), "n": len(items), "statuses": dict(Counter(x["status"] for x in items))}
        for metric in ["valid", "goal_correct", "visible_decision_correct", "grounded_success", "read_sufficient", "spent"]:
            result[metric] = sum(float(x["score"][metric]) for x in items) / len(items)
        possible = [x for x in items if x["certificate_attainable"]]
        result["attainable_n"] = len(possible)
        result["grounded_success_attainable"] = (sum(x["score"]["grounded_success"] for x in possible) / len(possible)
                                                if possible else None)
        result["calls"] = sum(len(x["calls"]) for x in items)
        results.append(result)
    return results


def main(batch, output):
    plan = json.loads((batch / "PLAN.json").read_text())
    for rel, expected in plan["bound_files"].items():
        if sha_file(batch / rel) != expected:
            raise ValueError("frozen file changed: " + rel)
    data = ROOT / plan.get("private_data_file", "data/PILOT_EPISODES_PRIVATE.json")
    if sha_file(data) != plan["private_data_sha256"]:
        raise ValueError("private reference input changed")
    episodes = {e["id"]: e for e in json.loads(data.read_text())}
    public = json.loads((batch / "PUBLIC.json").read_text())
    by_worker = {task: worker for worker, spec in plan["workers"].items() for task in spec["tasks"]}
    if len(by_worker) != len(plan["tasks"]):
        raise ValueError("assignment task count differs")
    rows, wrapper_diagnostics = [], []
    for tid, task in plan["tasks"].items():
        read_ids, answer, status, calls, wrappers = reconstruct(batch, task, by_worker[tid], public)
        episode = episodes[task["episode"]]
        metrics = score(episode, read_ids, answer, task["budget"])
        rows.append({"task": tid, "episode": episode["id"], "family": episode["family"], "group": episode["group"],
            "variant": episode["variant"], "model": task["model"], "condition": task["condition"],
            "status": status, "read_ids": read_ids, "answer": answer, "score": metrics, "calls": calls,
            "certificate_attainable": certificates(episode)["minimum_cost"] <= task["budget"]})
        for wrapper in wrappers:
            wrapper_diagnostics.append({"task": tid, "condition": task["condition"], "model": task["model"],
                **wrapper, "score": score(episode, wrapper["read_ids"], wrapper["answer"], task["budget"])})
    calls = [c for row in rows for c in row["calls"]]
    report = {"batch": str(batch.relative_to(ROOT)), "plan_sha256": sha_file(batch / "PLAN.json"),
        "tasks": len(rows), "captured_model_calls": len(calls),
        "generation_intents": len(list((batch / "runs").glob("*/trajectories/*/turn-*/intent.json"))),
        "output_tokens": sum(c["output_tokens"] for c in calls), "input_tokens": sum(c["input_tokens"] for c in calls),
        "response_generation_seconds": sum(c["seconds"] for c in calls),
        "statuses": dict(Counter(row["status"] for row in rows)), "rows": rows,
        "by_model_condition": aggregate(rows, ["model", "condition"]),
        "by_model_condition_family": aggregate(rows, ["model", "condition", "family"]),
        "posthoc_wrapper_diagnostics": wrapper_diagnostics,
        "wrapper_diagnostic_limit": "Descriptive recovery only; never replaces primary strict scores or invents unexecuted read trajectories.",
        "independent_replay": "Read history, final action and status reconstructed from public state machine and raw outputs; equals stored final.",
        "reference_validation": "Finite support scorer separately checked against exhaustive synthetic possible worlds; source-derived references are not independent physical truth.",
        "statistics_limit": "Development only; variants and neighboring targets/frames correlated; no confirmatory p-values."}
    dump(output, report)
    print(json.dumps({k: report[k] for k in ["tasks", "captured_model_calls", "generation_intents", "statuses", "by_model_condition"]}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    main(args.batch.resolve(), args.output)
