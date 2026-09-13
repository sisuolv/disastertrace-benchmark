"""Independently replay native-E labels, tokens and charged diagnostic receipts."""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from gpu_worker import digest, save


def main(args):
    batch = args.batch.resolve()
    args.output.mkdir(exist_ok=False)
    shutil.copyfile(__file__, args.output / "verify_e_probe.py")
    plan = json.loads((batch / "PLAN.json").read_text())
    for name, expected in plan["files"].items():
        if digest(batch / name) != expected:
            raise ValueError("Frozen probe input changed")
    if plan["evaluation_bindings"].get(str(args.labels.resolve())) != digest(
        args.labels
    ):
        raise ValueError("Evaluation labels differ from frozen binding")
    labels = json.loads(args.labels.read_text())["labels"]
    sys.path.insert(0, str(batch / "source"))
    from disastertrace.monitoring_v1.evidence import exists_report_support
    from disastertrace.monitoring_v1.journal import read_journal
    from disastertrace.monitoring_v1.resources import BudgetLedger
    from e_probe_runtime import parse_status
    from transformers import AutoTokenizer

    hardware = json.loads((batch / "worker-0/HARDWARE.json").read_text())
    if (
        hardware["count"] != 1
        or "H100" not in hardware["name"]
        or hardware["hostname"] == plan["cci_hostname"]
    ):
        raise ValueError("Incorrect actual worker hardware")
    job_id = (batch / "submissions/0/job-id.txt").read_text().strip()
    result = subprocess.run(
        [
            "/mnt/afs/260010168/bin/sco",
            "acp",
            "jobs",
            "describe",
            "--workspace-name=share-space",
            "--format=json",
            job_id,
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=45,
    )
    job = json.loads(result.stdout)
    save(args.output / "JOB.json", job)
    if job["state"] != "SUCCEEDED":
        raise ValueError("Probe job has not succeeded")
    complete = json.loads((batch / "worker-0/COMPLETE.json").read_text())
    if complete["plan_sha256"] != digest(batch / "PLAN.json"):
        raise ValueError("Completion identity mismatch")
    spec = plan["models"]["qwen3_8b"]
    tokenizer = AutoTokenizer.from_pretrained(spec["directory"], local_files_only=True)
    eos = json.loads((Path(spec["directory"]) / "generation_config.json").read_text())[
        "eos_token_id"
    ]
    eos = eos if isinstance(eos, list) else [eos]
    reports, total_calls, total_tokens = {}, 0, 0
    for task in plan["workers"]["0"]:
        directory = batch / "worker-0" / task["run_id"]
        trace = json.loads((directory / "TRACE.json").read_text())
        data = json.loads((batch / task["data_file"]).read_text())
        cases = {c["case_id"]: c for c in data["cases"]}
        if len(trace["calls"]) != len(cases) or {
            c["case_id"] for c in trace["calls"]
        } != set(cases):
            raise ValueError("Probe lost or duplicated cases")
        # Restore a ledger from its exact journal without opening it for writing.
        journal = read_journal(directory / "RESOURCES.jsonl")
        if journal.incomplete_tail:
            raise ValueError("Partial resource journal")
        holder = type("ReadOnlyJournal", (), {"records": journal.records})()
        ledger = BudgetLedger.restore(holder)
        if ledger.limits != {
            "tokens": task["config"]["token_cap"],
            "compute_ms": task["config"]["compute_ms_cap"],
        }:
            raise ValueError("Probe ledger limits differ from the frozen task")
        spent = {k: getattr(ledger.spent, k) for k in trace["resource_spent"]}
        if spent != trace["resource_spent"] or any(trace["resource_reserved"].values()):
            raise ValueError("Probe resource receipts do not reconcile")
        condition = task["config"]["condition"]
        token_sum, correct, invalid, confusion = 0, 0, 0, Counter()
        for call in trace["calls"]:
            prefix = call["call_id"]
            case = cases[call["case_id"]]
            original = case["requests"]["E_only"]
            disclosed = {
                a["content"]["query_id"]: a["content"]
                for a in original["read_evidence"]
            }
            expected_e = exists_report_support(
                original["registered_query_ids"], disclosed, original["threshold_m"]
            )
            if expected_e != labels[call["case_id"]]:
                raise ValueError(
                    "Evaluator E label does not reconstruct from disclosed native products"
                )
            request = json.loads((directory / (prefix + "-request.json")).read_text())
            response = json.loads((directory / (prefix + "-response.json")).read_text())
            raw = (directory / (prefix + "-raw.txt")).read_text()
            expected_messages = [
                {"role": "system", "content": data["systems"][condition]},
                {
                    "role": "user",
                    "content": json.dumps(
                        case["requests"][condition], separators=(",", ":")
                    ),
                },
            ]
            if request["messages"] != expected_messages:
                raise ValueError(
                    "Actual probe request differs from declared representation"
                )
            rendered = tokenizer.apply_chat_template(
                expected_messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
            ids = tokenizer(rendered, add_special_tokens=False)["input_ids"]
            if (
                ids != request["input_ids"]
                or len(ids) != response["input_tokens"]
                or hashlib.sha256(rendered.encode()).hexdigest()
                != request["rendered_sha256"]
            ):
                raise ValueError("Input token replay differs")
            if (
                tokenizer.decode(response["output_ids"], skip_special_tokens=True)
                != raw
                or raw != call["raw"]
                or hashlib.sha256(raw.encode()).hexdigest() != response["raw_sha256"]
            ):
                raise ValueError("Output token replay differs")
            if len(response["output_ids"]) != response["output_tokens"]:
                raise ValueError("Output token count differs")
            ended = bool(response["output_ids"] and response["output_ids"][-1] in eos)
            if ended != response["ended_with_eos"] or any(
                call["details"].get(k) != v
                for k, v in response.items()
                if k != "output_ids"
            ):
                raise ValueError("Finish or cost details differ from actual capture")
            try:
                parsed = parse_status(raw, condition)
                if not ended:
                    raise ValueError("No terminal EOS")
                error = False
            except (ValueError, TypeError, json.JSONDecodeError):
                parsed, error = None, True
            if parsed != call["reported_e"] or error != bool(call["error"]):
                raise ValueError("Response schema/status audit differs")
            correct += parsed == expected_e
            invalid += error
            confusion[f"{expected_e} -> {parsed}"] += 1
            token_sum += response["input_tokens"] + response["output_tokens"]
        if token_sum != spent["tokens"]:
            raise ValueError("Charged tokens differ from raw captures")
        reports[condition] = {
            "cases": len(cases),
            "correct": correct,
            "invalid": invalid,
            "confusion": dict(confusion),
            "costs": spent,
        }
        total_calls += len(cases)
        total_tokens += token_sum
    if (
        total_calls != complete["model_calls"]
        or total_calls > plan["maximum_model_calls"]
    ):
        raise ValueError("Probe call budget mismatch")
    save(
        args.output / "VERIFIED.json",
        {
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "batch": str(batch),
            "plan_sha256": digest(batch / "PLAN.json"),
            "actual_calls": total_calls,
            "actual_tokens": total_tokens,
            "verified_workers": 1,
            "execution_kind": "current_evidence_diagnostic",
            "reports": reports,
            "validator_sha256": digest(args.output / "verify_e_probe.py"),
            "interpretation": plan["interpretation"],
        },
    )
    print(
        json.dumps(
            {
                "calls": total_calls,
                "tokens": total_tokens,
                "conditions": {
                    k: [v["correct"], v["cases"]] for k, v in reports.items()
                },
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
