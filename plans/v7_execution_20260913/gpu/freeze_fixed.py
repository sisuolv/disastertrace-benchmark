"""Qualify every new input and prepare four fresh 36-call workers."""

from __future__ import annotations

import json
import shutil
import socket
from datetime import datetime, timezone
from pathlib import Path

from disastertrace.monitoring_fixed_v1.aviation import model_messages
from disastertrace.monitoring_fixed_v1.contracts import EvidenceBundle, fingerprint
from gpu_worker import digest, save
from transformers import AutoTokenizer

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def main():
    matrix = HERE.parent / "evidence_bundle/matrix_01"
    acceptance = json.loads((matrix / "CPU_ACCEPTANCE.json").read_text())
    if not acceptance["accepted_for_bounded_fixed_snapshot_inference"]:
        raise ValueError("CPU matrix not qualified")
    manifest = json.loads((matrix / "MANIFEST.json").read_text())
    prior = json.loads(
        (
            ROOT
            / "plans/v7_review_execution_20260912/gpu_front_primary_base_01/PLAN.json"
        ).read_text()
    )
    spec = prior["models"]["qwen3_8b"]
    tokenizer = AutoTokenizer.from_pretrained(spec["directory"], local_files_only=True)
    batch = HERE / "fixed_matrix_01"
    batch.mkdir(exist_ok=False)
    (batch / "source/disastertrace").mkdir(parents=True)
    (batch / "source/disastertrace/__init__.py").write_text("")
    src = ROOT / "disastertrace-starter/src/disastertrace"
    for package in ["monitoring_fixed_v1", "monitoring_v1"]:
        shutil.copytree(
            src / package,
            batch / "source/disastertrace" / package,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
    shutil.copyfile(HERE / "gpu_worker.py", batch / "source/gpu_worker.py")
    shutil.copytree(matrix / "policy", batch / "policy")
    shutil.copyfile(matrix / "DESIGN.json", batch / "DESIGN.json")
    workers = {str(i): [] for i in range(4)}
    counts = []
    # Each opportunity's three conditions remain on one worker, balanced by public IDs.
    opportunities = sorted({(r["region"], r["opportunity_id"]) for r in manifest})
    shards = {pair: str(i % 4) for i, pair in enumerate(opportunities)}
    for row in manifest:
        bundle = EvidenceBundle.restore(
            json.loads((batch / "policy" / (row["call_id"] + ".json")).read_text())
        )
        messages = model_messages(bundle)
        if (
            bundle.bundle_hash != row["bundle_hash"]
            or fingerprint(messages) != row["messages_sha256"]
        ):
            raise ValueError("Prepared input binding mismatch")
        rendered = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True, enable_thinking=False
        )
        n = len(tokenizer(rendered, add_special_tokens=False)["input_ids"])
        if n + 192 > 12288:
            raise ValueError("Input exceeds bounded context")
        counts.append(n)
        workers[shards[(row["region"], row["opportunity_id"])]].append(
            {**row, "input_tokens": n}
        )
    files = {
        str(p.relative_to(batch)): digest(p) for p in batch.rglob("*") if p.is_file()
    }
    plan = {
        "schema": "disastertrace.fixed_snapshot_gpu.v1",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "workers": workers,
        "files": files,
        "model": spec,
        "runtime_versions": prior["runtime_versions"],
        "seed": 20260913,
        "max_new_tokens": 192,
        "max_generation_seconds": 45,
        "context_limit": 12288,
        "max_calls_per_worker": 36,
        "max_worker_seconds": 1800,
        "max_concurrent_gpus": 4,
        "cci_hostname": socket.gethostname(),
        "expected_calls": 144,
        "retries": 0,
        "design_sha256": digest(batch / "DESIGN.json"),
        "matrix_manifest_sha256": digest(matrix / "MANIFEST.json"),
        "gpu_evaluation": "New actual inference on frozen development snapshots; direct candidate p and E response only",
        "outcomes_packaged": False,
        "tools": [],
        "online_inference": False,
        "old_launches_reused": False,
    }
    if sum(len(w) for w in workers.values()) != 144 or any(
        len(w) != 36 for w in workers.values()
    ):
        raise ValueError("Expected four equal 36-call shards")
    save(batch / "PLAN.json", plan)
    save(
        batch / "CPU_PREFLIGHT.json",
        {
            "inputs_verified": len(counts),
            "min_input_tokens": min(counts),
            "max_input_tokens": max(counts),
            "sum_input_tokens": sum(counts),
            "output_reservation": 144 * 192,
            "generation_calls": 0,
            "plan_sha256": digest(batch / "PLAN.json"),
        },
    )
    print(
        json.dumps(
            {
                "batch": str(batch),
                "calls": 144,
                "max_input_tokens": max(counts),
                "plan_sha256": digest(batch / "PLAN.json"),
            }
        )
    )


if __name__ == "__main__":
    main()
