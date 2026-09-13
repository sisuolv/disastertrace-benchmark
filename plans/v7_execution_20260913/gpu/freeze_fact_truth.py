"""Fresh same-input probe of filled example sensitivity, not a selected score retry."""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from disastertrace.monitoring_fixed_v1.contracts import EvidenceBundle, fingerprint
from fact_truth_probe import model_messages
from gpu_worker import digest, save
from transformers import AutoTokenizer

HERE = Path(__file__).resolve().parent


def main():
    prior_batch = HERE / "fixed_matrix_01"
    prior = json.loads((prior_batch / "PLAN.json").read_text())
    matrix = HERE.parent / "evidence_bundle/matrix_01"
    original_rows = json.loads((matrix / "MANIFEST.json").read_text())
    tokenizer = AutoTokenizer.from_pretrained(
        prior["model"]["directory"], local_files_only=True
    )
    batch = HERE / "fact_truth_probe_01"
    batch.mkdir(exist_ok=False)
    shutil.copytree(prior_batch / "source", batch / "source")
    shutil.copyfile(HERE / "fact_truth_probe.py", batch / "source/fact_truth_probe.py")
    worker_path = batch / "source/gpu_worker.py"
    source = worker_path.read_text()
    source = source.replace(
        "from disastertrace.monitoring_fixed_v1.aviation import model_messages",
        "from fact_truth_probe import model_messages",
    )
    source = source.replace(
        "messages = model_messages(bundle)",
        'messages = model_messages(bundle, item["prompt_variant"])',
    )
    worker_path.write_text(source)
    (batch / "policy").mkdir()
    variants = ["explicit_truth_E_only", "explicit_truth_joint_EF"]
    workers = {str(i): [] for i in range(4)}
    opportunities = sorted({(r["region"], r["opportunity_id"]) for r in original_rows})
    shards = {key: str(i % 4) for i, key in enumerate(opportunities)}
    for original in original_rows:
        bundle_file = prior_batch / "policy" / (original["call_id"] + ".json")
        bundle = EvidenceBundle.restore(json.loads(bundle_file.read_text()))
        for variant in variants:
            call_id = fingerprint([original["call_id"], variant])[:20]
            shutil.copyfile(bundle_file, batch / "policy" / (call_id + ".json"))
            messages = model_messages(bundle, variant)
            rendered = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
            n = len(tokenizer(rendered, add_special_tokens=False)["input_ids"])
            if n + prior["max_new_tokens"] > prior["context_limit"]:
                raise ValueError("Input exceeds existing context limit")
            row = {
                **original,
                "call_id": call_id,
                "original_call_id": original["call_id"],
                "prompt_variant": variant,
                "input_tokens": n,
                "messages_sha256": fingerprint(messages),
            }
            workers[shards[(row["region"], row["opportunity_id"])]].append(row)
    design = {
        "trigger": "Example-free joint prompt calls any nonempty evidence supported; test explicit truth vocabulary and E-only versus joint head",
        "original_result_sha256": digest(HERE / "prompt_verification_01/REPORT.json"),
        "scope": "same144inputs x2newprompt variants; all outcomes and original results retained",
        "variants": variants,
        "expected_calls": 288,
        "one_repeat": True,
        "comparison": "Explicit truth with same data: E-only vs joint head diagnostic; not isolated naming effect or independent confirmation",
        "inputs_and_predictor_settings_unchanged_except_system_prompt": True,
        "future_outcomes_in_prompts": False,
        "retries": 0,
    }
    save(batch / "DESIGN.json", design)
    files = {
        str(p.relative_to(batch)): digest(p) for p in batch.rglob("*") if p.is_file()
    }
    plan = {
        **prior,
        "schema": "disastertrace.fact_truth_heads_gpu.v1",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "workers": workers,
        "files": files,
        "expected_calls": 288,
        "max_calls_per_worker": 72,
        "design_sha256": digest(batch / "DESIGN.json"),
        "original_plan_sha256": digest(prior_batch / "PLAN.json"),
    }
    if any(len(tasks) != 72 for tasks in workers.values()):
        raise ValueError("Expected four equal72-call shards")
    save(batch / "PLAN.json", plan)
    save(
        batch / "CPU_PREFLIGHT.json",
        {
            "all_288_inputs_bound": True,
            "original_bundle_hashes_retained": True,
            "generation_calls": 0,
            "plan_sha256": digest(batch / "PLAN.json"),
        },
    )
    print(
        json.dumps(
            {
                "batch": str(batch),
                "calls": 288,
                "workers": 4,
                "plan_sha256": digest(batch / "PLAN.json"),
            }
        )
    )


if __name__ == "__main__":
    main()
