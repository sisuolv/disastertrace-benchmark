"""Run only query selection on TP4; the registered numerical forecaster is fixed."""

import argparse
import datetime as dt
import hashlib
import os
import socket
import time
from pathlib import Path

from disastertrace.monitoring_fixed_v1.admission import AdmissionEngine
from disastertrace.monitoring_fixed_v1.outcomes import ComparisonContract
from disastertrace.monitoring_v1.formal_session import (
    FormalSession,
    required_source_files,
)
from disastertrace.monitoring_v1.spool_backend import digest, publish, read
from prepare_selector_trial import backend


def file_digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(16 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main(batch):
    import torch
    import transformers
    import vllm
    from transformers import AutoTokenizer
    from vllm import LLM, SamplingParams

    plan = read(batch / "PLAN.json")
    publish(
        batch / "RUN_CLAIM.json",
        {"pid": os.getpid(), "host": socket.gethostname(), "at": time.time_ns()},
    )
    for rel, sha in plan["files"].items():
        if digest(batch / rel) != sha:
            raise ValueError("Frozen selector experiment changed")
    settings, model = read(batch / "BACKEND.json"), read(batch / "MODEL_MANIFEST.json")
    versions = {
        "torch": torch.__version__.split("+")[0],
        "transformers": transformers.__version__,
        "vllm": vllm.__version__,
    }
    if versions != settings["runtime"]["versions"] or torch.cuda.device_count() != 4:
        raise ValueError("Qualified TP4 runtime required")
    hardware = [torch.cuda.get_device_properties(i).name for i in range(4)]
    if any("H100" not in h for h in hardware):
        raise ValueError("Four H100s required")
    for row in model["files"]:
        path = Path(model["directory"]) / row["path"]
        if path.stat().st_size != row["bytes"] or file_digest(path) != row["sha256"]:
            raise ValueError("Frozen model bytes changed")
    publish(
        batch / "MODEL_RECHECK.json",
        {
            "passed": True,
            "files": len(model["files"]),
            "hardware": hardware,
            "versions": versions,
        },
    )
    tokenizer = AutoTokenizer.from_pretrained(
        model["directory"], local_files_only=True, trust_remote_code=False
    )
    llm = LLM(
        model=model["directory"],
        tokenizer=model["directory"],
        tensor_parallel_size=4,
        dtype="auto",
        quantization="fp8",
        trust_remote_code=False,
        seed=20260914,
        **settings["runtime"]["engine"],
    )
    eos = read(Path(model["directory"]) / "generation_config.json")["eos_token_id"]
    eos = eos if isinstance(eos, list) else [eos]
    ids = tokenizer.apply_chat_template(
        [{"role": "user", "content": "Return exactly READY."}],
        tokenize=True,
        add_generation_prompt=True,
        enable_thinking=False,
    )
    publish(batch / "COMPATIBILITY_REQUEST.json", {"input_ids": ids, "max_tokens": 16})
    smoke = llm.generate(
        [{"prompt_token_ids": ids}],
        SamplingParams(temperature=0, max_tokens=16),
        use_tqdm=False,
    )[0].outputs[0]
    publish(
        batch / "COMPATIBILITY_RESPONSE.json",
        {
            "raw": smoke.text,
            "output_ids": list(smoke.token_ids),
            "finish_reason": smoke.finish_reason,
        },
    )
    if smoke.text.strip().rstrip(".") != "READY" or smoke.finish_reason != "stop":
        raise ValueError("Compatibility failed before benchmark dispatch")
    publish(batch / "WARM_READY.json", {"at": time.time_ns(), "compatibility_calls": 1})
    deadline = dt.datetime.fromisoformat(plan["last_worker_time"])
    completed, calls = [], 0
    # Four sessions share one generation batch; none sees another session's state.
    for offset in range(0, len(plan["cases"]), plan["batch_size"]):
        sessions = []
        for name in plan["cases"][offset : offset + plan["batch_size"]]:
            case = batch / name
            comp = read(case / "COMPARISON.json")["payload"]
            files = {str(p): digest(p) for p in required_source_files()}
            files.update({str(batch / p): sha for p, sha in plan["files"].items()})
            transport = backend(batch, case)
            session = FormalSession(
                read(case / "DATA.json"),
                read(case / "BANK.json"),
                read(case / "CONFIG.json"),
                comparison=ComparisonContract(
                    comp["invariants"], comp["allowed_interventions"]
                ),
                bound_files=files,
                directory=case / "B11_LLM",
                backend=transport,
            )
            sessions.append((case, session, transport))
        for iteration in range(100):
            if dt.datetime.now(dt.timezone.utc) >= deadline:
                raise TimeoutError("Registered selector experiment deadline reached")
            pending = []
            for case, session, transport in sessions:
                if session.done:
                    continue
                session.step()
                snapshot = session.snapshot()
                if "pending_selector" in snapshot["payload"]:
                    item = snapshot["payload"]["pending_selector"]
                    path = case / "B11_LLM" / (item["call_id"] + ".checkpoint.json")
                    session.persist(path)
                    request = transport.claim_ready(
                        item["call_id"], worker_id="tp4-selector-worker"
                    )
                    request_path = (
                        case / "spool" / (item["ticket"]["remote_id"] + ".request.json")
                    )
                    pending.append((case, request_path, request))
            if not pending:
                if all(session.done for _, session, _ in sessions):
                    break
                continue
            if calls + len(pending) > plan["max_model_benchmark_calls"]:
                raise ValueError("Registered model call ceiling exceeded")
            prompts = []
            for case, request_path, request in pending:
                config = read(case / "CONFIG.json")
                tokens = tokenizer.apply_chat_template(
                    request["messages"],
                    tokenize=True,
                    add_generation_prompt=True,
                    enable_thinking=False,
                )
                if (
                    len(tokens) > config["input_token_cap"]
                    or len(tokens) + 512
                    > settings["runtime"]["engine"]["max_model_len"]
                ):
                    raise ValueError(
                        "Original selector request exceeds registered context cap"
                    )
                prompt_path = request_path.with_name(
                    request_path.name.replace(".request.json", ".tokens.json")
                )
                publish(
                    prompt_path,
                    {
                        "input_ids": tokens,
                        "request_sha256": digest(request_path),
                        "max_tokens": 512,
                        "batch_size": len(pending),
                    },
                )
                prompts.append({"prompt_token_ids": tokens})
            started = time.perf_counter()
            try:
                generated = llm.generate(
                    prompts,
                    SamplingParams(temperature=0, max_tokens=512, seed=20260914),
                    use_tqdm=False,
                )
                duration = time.perf_counter() - started
                if len(generated) != len(pending):
                    raise ValueError("Generation batch response count mismatch")
            except Exception as exc:
                for _, path, request in pending:
                    publish(
                        path.with_name(
                            path.name.replace(".request.json", ".failure.json")
                        ),
                        {
                            "call_id": request["call_id"],
                            "request_sha256": digest(path),
                            "execution_sha256": request["execution_sha256"],
                            "error_type": type(exc).__name__,
                        },
                    )
                raise
            for (_, path, request), prompt, response in zip(
                pending, prompts, generated, strict=True
            ):
                answer = response.outputs[0]
                output_ids = list(answer.token_ids)
                ended = answer.finish_reason == "stop" and (
                    (output_ids and output_ids[-1] in eos) or answer.stop_reason in eos
                )
                value = {
                    "call_id": request["call_id"],
                    "request_sha256": digest(path),
                    "execution_sha256": request["execution_sha256"],
                    "raw": answer.text,
                    "raw_sha256": hashlib.sha256(answer.text.encode()).hexdigest(),
                    "input_tokens": len(prompt["prompt_token_ids"]),
                    "output_tokens": len(output_ids),
                    "compute_seconds": duration,
                    "ended_with_eos": bool(ended),
                }
                worker = path.with_name(
                    path.name.replace(".request.json", ".worker.json")
                )
                publish(
                    worker,
                    {
                        **value,
                        "output_ids": output_ids,
                        "finish_reason": answer.finish_reason,
                        "stop_reason": answer.stop_reason,
                        "generated_wall_ns": time.time_ns(),
                        "compute_scope": "whole TP4 batch elapsed charged conservatively per call; not additive device-seconds",
                    },
                )
                publish(
                    path.with_name(
                        path.name.replace(".request.json", ".response.json")
                    ),
                    {
                        **value,
                        "schema": "disastertrace.spool_response.v1",
                        "worker_receipt_sha256": digest(worker),
                    },
                )
            calls += len(pending)
            print(
                {"group": offset, "iteration": iteration, "benchmark_calls": calls},
                flush=True,
            )
        for case, session, _ in sessions:
            report = session.finish(max_steps=1)
            publish(case / "B11_LLM/REPORT.json", report)
            publish(case / "B11_LLM/FINAL.json", session.snapshot())
            AdmissionEngine.restore(report["event_replay"]).write_journal(
                case / "B11_LLM/admission.jsonl"
            )
            result = {
                "case": case.name,
                "opportunities": len(report["snapshots"]),
                "selector_calls": len(report["selector_calls"]),
                "model_calls": report["actual_model_calls"],
                "source_spent": report["resource_spent"]["requests"],
            }
            publish(case / "B11_LLM/COMPLETE.json", result)
            completed.append(result)
    publish(
        batch / "COMPLETE.json",
        {
            "cases": completed,
            "benchmark_calls": calls,
            "compatibility_calls": 1,
            "confirmation_opened": False,
            "at": dt.datetime.now(dt.timezone.utc).isoformat(),
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, required=True)
    args = parser.parse_args()
    main(args.batch.absolute())
