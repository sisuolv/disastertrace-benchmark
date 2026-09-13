"""Freeze the preregistered exposed 108-call E/F/joint engineering smoke."""

import json
import shutil
import socket
from datetime import datetime, timezone
from pathlib import Path

from disastertrace.monitoring_fixed_v1.contracts import EvidenceBundle, fingerprint
from disastertrace.monitoring_fixed_v1.heads import (
    PROMPT_VERSION,
    model_messages,
    parse_response,
)
from gpu_worker import digest, save
from transformers import AutoTokenizer

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def main():
    prior = json.loads(
        (ROOT / "plans/v7_execution_20260913/gpu/fixed_matrix_01/PLAN.json").read_text()
    )
    execution = HERE.parent
    mission = json.loads((execution / "MISSION_SPEC.json").read_text())
    rows = json.loads((execution / "EXPOSURE_LEDGER.json").read_text())["rows"]
    matrix = ROOT / "plans/v7_execution_20260913/evidence_bundle/matrix_01"
    tokenizer = AutoTokenizer.from_pretrained(
        prior["model"]["directory"], local_files_only=True
    )
    batch = HERE / "heads_smoke_01"
    batch.mkdir(exist_ok=False)
    source = batch / "source"
    source.mkdir()
    for module in ("monitoring_v1", "monitoring_fixed_v1"):
        shutil.copytree(
            ROOT / "disastertrace-starter/src/disastertrace" / module,
            source / "disastertrace" / module,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
    shutil.copyfile(HERE / "gpu_worker.py", source / "gpu_worker.py")
    shutil.copyfile(execution / "MISSION_SPEC.json", batch / "MISSION_SPEC.json")
    (batch / "policy").mkdir()
    tasks = []
    for row in sorted(
        rows, key=lambda r: (r["region"], r["opportunity_id"], r["condition"])
    ):
        original = matrix / "policy" / (row["call_id"] + ".json")
        bundle = EvidenceBundle.restore(json.loads(original.read_text()))
        p = bundle.policy_view()
        started = p["cutoff"] - 60_000_000
        if (
            max(
                [p["baseline"]["available_at"]]
                + [a["completed_at"] for a in p["assets"]]
            )
            > started
        ):
            raise ValueError("Future input at fixed invocation start")
        for head in mission["heads"]:
            cid = fingerprint(["followup.smoke.v1", row["call_id"], head])[:24]
            messages = model_messages(bundle, head)
            rendered = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
            n = len(tokenizer(rendered, add_special_tokens=False)["input_ids"])
            if n + prior["max_new_tokens"] > prior["context_limit"]:
                raise ValueError("Input exceeds bound")
            diagnostic = {"fact_truth": "unknown", "probability": 0.25}
            fields = {
                "e_only": ["fact_truth"],
                "f_only": ["probability"],
                "joint": list(diagnostic),
            }
            parse_response(
                json.dumps({k: diagnostic[k] for k in fields[head]}), bundle, head
            )
            shutil.copyfile(original, batch / "policy" / (cid + ".json"))
            tasks.append(
                {
                    **row,
                    "original_call_id": row["call_id"],
                    "call_id": cid,
                    "head": head,
                    "input_tokens": n,
                    "messages_sha256": fingerprint(messages),
                    "logical_started_at": started,
                    "logical_cutoff": p["cutoff"],
                }
            )
    if len(tasks) != 108 or len({t["call_id"] for t in tasks}) != 108:
        raise ValueError("Unexpected smoke cardinality")
    files = {
        str(p.relative_to(batch)): digest(p) for p in batch.rglob("*") if p.is_file()
    }
    plan = {
        **{
            k: prior[k]
            for k in (
                "model",
                "runtime_versions",
                "seed",
                "max_new_tokens",
                "max_generation_seconds",
                "context_limit",
            )
        },
        "schema": "disastertrace.independent_heads_smoke.v1",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "workers": {"0": tasks},
        "files": files,
        "max_calls_per_worker": 108,
        "max_worker_seconds": 7200,
        "max_concurrent_gpus": 4,
        "expected_calls": 108,
        "cci_hostname": socket.gethostname(),
        "prompt_version": PROMPT_VERSION,
        "retries": 0,
        "mission_sha256": digest(execution / "MISSION_SPEC.json"),
        "online_inference": False,
        "outcomes_packaged": False,
        "tools": [],
        "old_launches_reused": False,
    }
    save(batch / "PLAN.json", plan)
    save(
        batch / "CPU_PREFLIGHT.json",
        {
            "inputs": 36,
            "fresh_calls": 108,
            "heads": mission["heads"],
            "input_tokens_min": min(t["input_tokens"] for t in tasks),
            "input_tokens_max": max(t["input_tokens"] for t in tasks),
            "all_inputs_available_before_logical_start": True,
            "diagnostic_parse_only": True,
            "generation_calls": 0,
            "plan_sha256": digest(batch / "PLAN.json"),
        },
    )
    print(
        json.dumps(
            {
                "batch": str(batch),
                "frozen_calls": len(tasks),
                "gpus": 1,
                "plan_sha256": digest(batch / "PLAN.json"),
            }
        )
    )


if __name__ == "__main__":
    main()
