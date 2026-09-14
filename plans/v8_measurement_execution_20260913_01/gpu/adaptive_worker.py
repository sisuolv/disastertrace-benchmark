"""One TP4 model serves committed requests from independent serial controllers."""

import argparse
import datetime
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

from disastertrace.monitoring_v1.session_checkpoint import SessionCoordinator
from disastertrace.monitoring_v1.spool_backend import (
    CommittedSpoolBackend,
    digest,
    publish,
    read,
)


def file_sha(path):
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(16 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def backend(batch, case):
    if not case["uses_model"]:
        return None
    return CommittedSpoolBackend(
        batch / "runs" / case["id"] / "spool",
        read(batch / "BACKEND.json"),
        run_id=case["id"],
    )


def case_files(batch, case):
    group = batch / "cases" / case["data_case"]
    return read(group / "DATA.json"), read(batch / "BANK.json")


def controller(batch, case_id):
    plan = read(batch / "PLAN.json")
    case = next(c for c in plan["cases"] if c["id"] == case_id)
    out = batch / "runs" / case_id
    publish(
        out / "CONTROLLER_STARTED.json",
        {"pid": os.getpid(), "plan_sha256": digest(batch / "PLAN.json")},
    )
    data, bank = case_files(batch, case)
    session = SessionCoordinator(
        data, bank, read(batch / case["config"]), backend=backend(batch, case)
    )
    index = 0
    deadline = datetime.datetime.fromisoformat(plan["last_worker_time"])
    while not session.done:
        if datetime.datetime.now(datetime.timezone.utc) >= deadline:
            publish(
                out / "TIME_LIMIT.json",
                {"index": index, "before_next_controller_step": True},
            )
            return 2
        session.finish()
        if session.done:
            break
        checkpoint = session.snapshot()
        pending = checkpoint["payload"].get("pending_predictor") or checkpoint[
            "payload"
        ].get("pending_selector")
        assert pending is not None
        path = out / f"checkpoint_{index:04d}.json"
        session.persist(path)
        pointer = out / "CURRENT_PENDING.json"
        temporary = out / ("pending_" + str(index) + ".json")
        publish(
            temporary,
            {
                "call_id": pending["call_id"],
                "ticket": pending["ticket"],
                "checkpoint": str(path),
                "index": index,
            },
        )
        replacement = out / ("pointer_" + str(index) + ".tmp")
        replacement.write_bytes(temporary.read_bytes())
        os.replace(replacement, pointer)
        response_path = (
            out / "spool" / (pending["ticket"]["remote_id"] + ".response.json")
        )
        while not response_path.exists():
            if datetime.datetime.now(datetime.timezone.utc) >= deadline:
                publish(out / "TIME_LIMIT.json", {"pending": pending, "index": index})
                return 2
            time.sleep(0.1)
        index += 1
    publish(out / "REPORT.json", session.report)
    publish(out / "FINAL_CHECKPOINT.json", session.snapshot())
    publish(
        out / "COMPLETE.json",
        {
            "opportunities": len(session.report["snapshots"]),
            "model_dispatches": session.report["actual_model_calls"],
            "program_forecasts": session.report["actual_program_forecast_calls"],
            "checkpointed_model_calls": index,
            "all_opportunities_retained": len(session.report["snapshots"])
            == len(data["opportunities"]),
        },
    )
    return 0


def main(batch, *, rehearsal=False):
    plan = read(batch / "PLAN.json")
    for name, expected in plan["files"].items():
        assert file_sha(batch / name) == expected, name
    publish(
        batch / "LIVE_STARTED.json",
        {
            "plan_sha256": digest(batch / "PLAN.json"),
            "pid": os.getpid(),
            "hostname": socket.gethostname(),
            "engineering_rehearsal": rehearsal,
        },
    )
    if rehearsal:
        assert plan["engineering_rehearsal"] and plan["model_call_ceiling"] == 0
        from disastertrace.monitoring_fixed_v1.aviation import (
            TRUTH_TO_SUPPORT,
            FrozenFrequencyPredictor,
            visible_e_status,
        )
        from disastertrace.monitoring_fixed_v1.contracts import EvidenceBundle
    else:
        assert not plan["engineering_rehearsal"]
        import torch
        import transformers
        import vllm
        from transformers import AutoTokenizer
        from vllm import LLM, SamplingParams

        spec = plan["model"]
        versions = {
            "torch": torch.__version__.split("+")[0],
            "transformers": transformers.__version__,
            "vllm": vllm.__version__,
        }
        assert versions == plan["runtime_versions"] and torch.cuda.device_count() == 4
        gpus = [
            {
                "name": torch.cuda.get_device_properties(i).name,
                "bytes": torch.cuda.get_device_properties(i).total_memory,
            }
            for i in range(4)
        ]
        assert all("H100" in row["name"] for row in gpus)
        for row in spec["files"]:
            path = Path(spec["directory"]) / row["path"]
            assert (
                path.stat().st_size == row["bytes"] and file_sha(path) == row["sha256"]
            ), row["path"]
        publish(
            batch / "HARDWARE.json",
            {
                "gpus": gpus,
                "runtime_versions": versions,
                "model_files_verified": spec["files"],
            },
        )
        tokenizer = AutoTokenizer.from_pretrained(
            spec["directory"], local_files_only=True
        )
        torch.set_num_threads(4)
        before = time.perf_counter()
        llm = LLM(
            model=spec["directory"],
            tokenizer=spec["directory"],
            tensor_parallel_size=4,
            dtype="auto",
            quantization=spec["quantization"],
            trust_remote_code=False,
            seed=plan["generation"]["seed"],
            **plan["engine"],
        )
        publish(
            batch / "MODEL_READY.json",
            {
                "load_seconds": time.perf_counter() - before,
                "controllers_start_after_model_ready": True,
            },
        )
        parameters = SamplingParams(
            temperature=0,
            max_tokens=plan["generation"]["max_tokens"],
            seed=plan["generation"]["seed"],
        )
    pending_cases = list(plan["case_order"])
    registry = {case["id"]: case for case in plan["cases"]}
    active, logs, exits = {}, {}, {}
    issued, batch_index = 0, 0
    deadline = datetime.datetime.fromisoformat(plan["last_worker_time"])
    try:
        while pending_cases or active:
            if datetime.datetime.now(datetime.timezone.utc) >= deadline:
                publish(
                    batch / "TIME_LIMIT.json",
                    {
                        "issued_model_calls": issued,
                        "pending_cases": pending_cases,
                        "active_cases": list(active),
                    },
                )
                break
            while pending_cases and len(active) < plan["parallel_controllers"]:
                ident = pending_cases.pop(0)
                out = batch / "runs" / ident
                log = (out / "controller.log").open("x")
                command = [
                    sys.executable,
                    str(Path(__file__)),
                    "controller",
                    "--batch",
                    str(batch),
                    "--case",
                    ident,
                ]
                publish(out / "CONTROLLER_COMMAND.json", {"command": command})
                active[ident] = subprocess.Popen(
                    command,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    env=dict(
                        os.environ,
                        OMP_NUM_THREADS="1",
                        MKL_NUM_THREADS="1",
                        OPENBLAS_NUM_THREADS="1",
                    ),
                )
                logs[ident] = log
            requests = []
            for ident in list(active):
                process = active[ident]
                if process.poll() is not None:
                    exits[ident] = process.returncode
                    publish(
                        batch / "runs" / ident / "CONTROLLER_EXIT.json",
                        {"exit_code": process.returncode},
                    )
                    logs.pop(ident).close()
                    del active[ident]
                    continue
                pointer = batch / "runs" / ident / "CURRENT_PENDING.json"
                if not pointer.exists():
                    continue
                current = read(pointer)
                spool = batch / "runs" / ident / "spool"
                key = current["ticket"]["remote_id"]
                if (spool / (key + ".claim.json")).exists():
                    continue
                transport = backend(batch, registry[ident])
                request = transport.claim_ready(
                    current["call_id"], worker_id=f"tp4-worker-batch-{batch_index}"
                )
                requests.append((ident, current, request))
            if not requests:
                time.sleep(0.1)
                continue
            started = time.perf_counter()
            wall_started = time.time_ns()
            if rehearsal:
                outputs = []
                for ident, current, request in requests:
                    view = request["request"]
                    if current["call_id"].startswith("select-"):
                        answer = {
                            "query_order": sorted(view["queries"]),
                            "forecast_handles": sorted(view["targets"])[
                                : view["per_tick_forecast_cap"]
                            ],
                        }
                    else:
                        bundle = EvidenceBundle.freeze(view)
                        answer = {
                            "fact_truth": {v: k for k, v in TRUTH_TO_SUPPORT.items()}[
                                visible_e_status(bundle)
                            ],
                            "probability": FrozenFrequencyPredictor(
                                read(batch / "BANK.json")
                            )
                            .predict(bundle)
                            .value,
                        }
                    outputs.append(
                        {
                            "raw": json.dumps(answer, separators=(",", ":")),
                            "input_ids": [],
                            "output_ids": [],
                            "input_tokens": 0,
                            "output_tokens": 0,
                            "ended_with_eos": True,
                        }
                    )
            else:
                assert issued + len(requests) <= plan["model_call_ceiling"]
                tokenization_start = time.perf_counter()
                inputs = [
                    tokenizer.apply_chat_template(
                        r[2]["messages"],
                        tokenize=True,
                        add_generation_prompt=True,
                        enable_thinking=False,
                    )
                    for r in requests
                ]
                tokenization_seconds = time.perf_counter() - tokenization_start
                assert all(len(ids) <= plan["input_token_cap"] for ids in inputs), (
                    "Frozen context cap exceeded; no selective retry"
                )
                publish(
                    batch / f"BATCH_{batch_index:04d}_INTENT.json",
                    {
                        "calls": [
                            {"case": ident, "call_id": cur["call_id"]}
                            for ident, cur, _ in requests
                        ],
                        "wall_started_ns": wall_started,
                        "input_lengths": list(map(len, inputs)),
                    },
                )
                issued += len(requests)
                generation_start = time.perf_counter()
                generated = llm.generate(
                    [{"prompt_token_ids": ids} for ids in inputs],
                    parameters,
                    use_tqdm=False,
                )
                generation_seconds = time.perf_counter() - generation_start
                outputs = []
                for ids, answer in zip(inputs, generated, strict=True):
                    final = answer.outputs[0]
                    eos = tokenizer.eos_token_id
                    outputs.append(
                        {
                            "raw": final.text,
                            "input_ids": ids,
                            "output_ids": list(final.token_ids),
                            "input_tokens": len(ids),
                            "output_tokens": len(final.token_ids),
                            "ended_with_eos": final.finish_reason == "stop"
                            and (
                                final.stop_reason == eos
                                or bool(final.token_ids)
                                and final.token_ids[-1] == eos
                            ),
                            "finish_reason": final.finish_reason,
                            "stop_reason": final.stop_reason,
                        }
                    )
            duration = (
                max(0.000001, time.perf_counter() - started)
                if rehearsal
                else max(0.000001, tokenization_seconds + generation_seconds)
            )
            for (ident, current, request), output in zip(
                requests, outputs, strict=True
            ):
                spool = batch / "runs" / ident / "spool"
                key = current["ticket"]["remote_id"]
                row = {
                    "call_id": current["call_id"],
                    "request_sha256": current["ticket"]["request_sha256"],
                    "execution_sha256": request["execution_sha256"],
                    "raw": output["raw"],
                    "raw_sha256": hashlib.sha256(output["raw"].encode()).hexdigest(),
                    "input_tokens": output["input_tokens"],
                    "output_tokens": output["output_tokens"],
                    "compute_seconds": duration,
                    "ended_with_eos": output["ended_with_eos"],
                }
                worker = spool / (key + ".worker.json")
                publish(
                    worker,
                    {
                        **row,
                        "input_ids": output["input_ids"],
                        "output_ids": output["output_ids"],
                        "batch_index": batch_index,
                        "batch_size": len(requests),
                        "wall_started_ns": wall_started,
                        "origin": "engineering_program_rehearsal"
                        if rehearsal
                        else "actual_local_vllm_TP4",
                        "finish_reason": output.get("finish_reason"),
                        "stop_reason": output.get("stop_reason"),
                    },
                )
                publish(
                    spool / (key + ".response.json"),
                    {
                        **row,
                        "schema": "disastertrace.spool_response.v1",
                        "worker_receipt_sha256": digest(worker),
                    },
                )
            publish(
                batch / f"BATCH_{batch_index:04d}_COMPLETE.json",
                {
                    "requests": len(requests),
                    "compute_seconds": duration,
                    "models_called": 0 if rehearsal else len(requests),
                    **(
                        {}
                        if rehearsal
                        else {
                            "tokenization_seconds": tokenization_seconds,
                            "generation_seconds": generation_seconds,
                        }
                    ),
                },
            )
            batch_index += 1
            print(
                json.dumps(
                    {
                        "actual_model_calls": issued,
                        "batches": batch_index,
                        "controllers_done": len(exits),
                    }
                ),
                flush=True,
            )
    except BaseException as exc:
        publish(
            batch / "WORKER_FAILED.json",
            {
                "exception": type(exc).__name__,
                "message": str(exc),
                "issued_model_calls": issued,
                "active_cases": list(active),
                "not_started_cases": list(pending_cases),
            },
        )
        raise
    finally:
        for ident, process in active.items():
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
            exits[ident] = process.returncode
            publish(
                batch / "runs" / ident / "CONTROLLER_EXIT.json",
                {"exit_code": process.returncode, "stopped_by_original_worker": True},
            )
            logs[ident].close()
        for ident in pending_cases:
            publish(
                batch / "runs" / ident / "NOT_STARTED.json",
                {
                    "reason": "Original worker stopped before this registered session; denominator retained."
                },
            )
    publish(
        batch / "COMPLETE.json",
        {
            "all_controller_exits_zero": len(exits) == len(registry)
            and all(v == 0 for v in exits.values()),
            "controller_exits": exits,
            "actual_model_calls": issued,
            "generation_batches": batch_index,
            "engineering_rehearsal": rehearsal,
        },
    )
    if len(exits) != len(registry) or any(exits.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["worker", "controller", "rehearsal"])
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--case")
    args = parser.parse_args()
    if args.mode == "controller":
        raise SystemExit(controller(args.batch, args.case))
    main(args.batch, rehearsal=args.mode == "rehearsal")
