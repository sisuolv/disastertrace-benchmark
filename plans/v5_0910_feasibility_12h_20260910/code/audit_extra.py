"""Rebuild source state independently and score raw diagnostic responses."""

from collections import Counter, defaultdict
import argparse
from datetime import datetime
import json
import re
from pathlib import Path

from common import ROOT, dump
from evidence_core import score
from model_adapter import parse_action, sha_file
from state_inputs import parse_state, state_request


def source_candidates(trace, step):
    target = trace["target"]
    target_time = datetime.fromisoformat(target["valid_time"])
    candidates = []
    for card in trace["deliveries"][:step + 1]:
        text = card["text"]
        storm = re.search(r"\bAL\d{6}\b", text)
        if not storm or storm[0] != target["storm_id"]:
            continue
        issue = datetime.fromisoformat(card["issue_time"])
        if not 0 < (target_time - issue).total_seconds() <= 7 * 86400:
            continue
        label = target_time.strftime("%d/%H%M") + "Z"
        matches = re.findall(r"(?:FORECAST|OUTLOOK) VALID " + re.escape(label) +
                             r"[^\n]*\nMAX WIND\s+(\d+) KT", text)
        if not matches:
            continue
        if len(matches) != 1:
            raise ValueError("ambiguous target in raw product")
        candidates.append({"wind_kt": int(matches[0]), "source_id": card["id"], "issue_time": card["issue_time"]})
    return candidates


def main(output=None):
    batch = ROOT / "gpu/wave5_diagnostics"
    plan = json.loads((batch / "PLAN.json").read_text())
    for rel, expected in plan["bound_files"].items():
        if sha_file(batch / rel) != expected:
            raise ValueError("frozen diagnostic file changed")
    for rel, expected in plan["private_reference_hashes"].items():
        if sha_file(ROOT / rel) != expected:
            raise ValueError("private reference changed")
    public = json.loads((batch / "PUBLIC.json").read_text())
    references = {r["id"]: r for r in json.loads((ROOT / "data/STATE_REFERENCES_PRIVATE.json").read_text())}
    episodes = {e["id"]: e for e in json.loads((ROOT / "data/PILOT_EPISODES_PRIVATE.json").read_text())}
    independent, baselines = {}, []
    for ident, trace in public["traces"].items():
        for step in range(7):
            candidates = source_candidates(trace, step)
            expected = max(candidates, key=lambda x: x["issue_time"])
            if expected != references[ident]["steps"][step]["expected"]:
                raise ValueError("independent raw NHC parser disagrees with private state")
            independent[ident, step] = expected
            baselines.append({"trace": ident, "step": step,
                "latest_compatible_source": True, "last_compatible_delivery": candidates[-1] == expected})
    assignments = {tid: w for w, d in plan["workers"].items() for tid in d["tasks"]}
    state_rows, static_rows, calls = [], [], []
    for tid, task in plan["tasks"].items():
        directory = batch / "runs" / assignments[tid] / "tasks" / tid
        final_path = directory / "FINAL.json"
        stored = json.loads(final_path.read_text()) if final_path.exists() else None
        previous = None
        steps = 7 if task["kind"] == "state" else 1
        for step in range(steps):
            slot = directory / ("step-%02d" % step)
            state = (state_request(public["traces"][task["trace"]], step, task["carrier"], previous)
                     if task["kind"] == "state" else public["static"][task["public_key"]])
            answer, status = None, "not_executed"
            if (slot / "request.json").exists() and json.loads((slot / "request.json").read_text()) != state:
                raise ValueError("actual carrier input differs from replay")
            if (slot / "response.json").exists():
                raw = (slot / "raw.txt").read_text()
                response = json.loads((slot / "response.json").read_text())
                processor = json.loads((slot / "processor.json").read_text())
                if response["raw_sha256"] != sha_file(slot / "raw.txt") or processor["prompt_sha256"] != sha_file(slot / "prompt.txt"):
                    raise ValueError("raw/prompt hash mismatch")
                if task["kind"] == "state":
                    answer = parse_state(raw)
                else:
                    parsed, kind = parse_action(raw)
                    answer = parsed if kind == "final" else None
                status = "final" if response["ended_eos"] and answer is not None else "invalid_schema" if response["ended_eos"] else "generation_incomplete"
                if status != "final":
                    answer = None
                calls.append({"task": tid, "step": step, "model": task["model"], "seconds": response["seconds"],
                    "output_tokens": response["generated_tokens"], "input_tokens": processor["input_tokens"],
                    "visual_tokens": processor["visual_tokens"], "images": len(processor["assets"])})
            elif (slot / "ERROR.json").exists():
                status = "runtime_error"
            if stored is not None:
                saved = stored["results"][step]
                if saved["status"] == "deadline_not_called" and status == "not_executed":
                    status = "deadline_not_called"
                if saved != {"step": step, "status": status, "answer": answer}:
                    raise ValueError("stored diagnostic result differs from raw replay")
            previous = answer
            if task["kind"] == "state":
                expected = independent[task["trace"], step]
                metadata = references[task["trace"]]["steps"][step]
                state_rows.append({"task": tid, "trace": task["trace"], "model": task["model"], "carrier": task["carrier"],
                    "step": step, "kind": metadata["kind"], "group": references[task["trace"]]["storm_id"],
                    "status": status, "answer": answer, "expected": expected, "exact_state": answer == expected,
                    "wind_correct": isinstance(answer, dict) and answer["wind_kt"] == expected["wind_kt"],
                    "source_correct": isinstance(answer, dict) and answer["source_id"] == expected["source_id"],
                    "value_changed": metadata["value_changed"], "source_changed": metadata["source_changed"]})
            else:
                episode = episodes[task["episode"]]
                result = score(episode, task["read_ids"], answer, task["budget"])
                static_rows.append({"task": tid, "model": task["model"], "episode": task["episode"],
                    "family": episode["family"], "group": episode["group"], "variant": episode["variant"],
                    "condition": task["condition"], "status": status, "answer": answer, "score": result})
    state_aggregate = []
    for model in sorted(plan["models"]):
        for carrier in ["full_history", "last_state"]:
            rows = [r for r in state_rows if r["model"] == model and r["carrier"] == carrier]
            state_aggregate.append({"model": model, "carrier": carrier, "n": len(rows),
                **{key: sum(r[key] for r in rows) / len(rows) for key in ["exact_state", "wind_correct", "source_correct"]},
                "by_kind": {kind: {"n": sum(r["kind"] == kind for r in rows),
                    "exact_state": sum(r["exact_state"] for r in rows if r["kind"] == kind) / sum(r["kind"] == kind for r in rows)}
                    for kind in sorted({r["kind"] for r in rows})}})
    static_aggregate = []
    for model in sorted(plan["models"]):
        for condition in ["fixed2_image", "native_vil_full"]:
            rows = [r for r in static_rows if r["model"] == model and r["condition"] == condition]
            static_aggregate.append({"model": model, "condition": condition, "n": len(rows),
                **{key: sum(float(r["score"][key]) for r in rows) / len(rows) for key in
                   ["goal_correct", "grounded_success", "read_sufficient", "spent"]}})
    report = {"state_checkpoints": len(state_rows), "static_tasks": len(static_rows), "captured_calls": len(calls),
        "generation_intents": len(list((batch / "runs").glob("*/tasks/*/step-*/intent.json"))),
        "statuses": dict(Counter(r["status"] for r in state_rows + static_rows)),
        "state_aggregate": state_aggregate, "static_aggregate": static_aggregate,
        "state_rows": state_rows, "static_rows": static_rows, "calls": calls,
        "program_state_baselines": baselines, "independent_raw_source_reference_checks": len(independent),
        "limitations": ["Only4storm groups for state; targets and conditions are paired/correlated.",
            "Last-state and full-history inputs differ in retained source detail and token cost.",
            "Native VIL visualization is a pixel-area interpretation diagnostic, not a validated general remote-sensing benchmark."]}
    dump(output or ROOT / "analysis/WAVE5_AUDIT.json", report)
    print(json.dumps({k: report[k] for k in ["state_checkpoints", "static_tasks", "captured_calls", "statuses", "state_aggregate", "static_aggregate"]}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    main(parser.parse_args().output)
