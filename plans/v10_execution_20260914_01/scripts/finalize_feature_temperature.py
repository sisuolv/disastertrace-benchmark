"""Wait for terminal captures, then score and audit tokens without new inference."""

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from disastertrace.monitoring_v1.spool_backend import digest, publish, read


def token_audit(batch, out):
    from transformers import AutoTokenizer

    gpu = batch / "gpu"
    plan = read(gpu / "PLAN.json")
    qualification = read(gpu / "QUALIFICATION.json")
    for rel, sha in qualification["frozen_files"].items():
        if digest(gpu / rel) != sha:
            raise ValueError("Frozen local generation source/input changed")
    manifest = read(gpu / "MODEL_MANIFEST.json")
    for item in manifest["files"]:
        if (
            "token" in item["path"] or item["path"].endswith((".json", ".jinja"))
        ) and digest(Path(manifest["directory"]) / item["path"]) != item["sha256"]:
            raise ValueError(
                "Tokenizer/config source differs from actual model manifest"
            )
    tokenizer = AutoTokenizer.from_pretrained(
        plan["model_directory"], local_files_only=True, trust_remote_code=False
    )
    generation = read(Path(plan["model_directory"]) / "generation_config.json")
    eos = generation["eos_token_id"]
    eos = eos if isinstance(eos, list) else [eos]
    rows = []
    for rank in range(4):
        folder = gpu / ("worker_" + str(rank))
        if not folder.exists():
            continue
        hardware = read(folder / "HARDWARE.json")
        if (
            "H100" not in hardware["name"]
            or hardware["versions"] != qualification["runtime_versions"]
        ):
            raise ValueError(
                "Actual local runtime is not the qualified H100 environment"
            )
        expected = {t["call_id"]: t for t in plan["tasks"] if t["worker"] == rank}
        for path in sorted(folder.glob("*.response.json")):
            response = read(path)
            cid = response["call_id"]
            if cid != "compatibility" and cid not in expected:
                raise ValueError("Unregistered or wrong-replica local response")
            request_path = folder / (cid + ".request.json")
            request = read(request_path)
            publication = read(folder / (cid + ".publication.json"))
            ids = tokenizer.apply_chat_template(
                request["messages"],
                tokenize=True,
                add_generation_prompt=True,
                enable_thinking=False,
                preserve_thinking=False,
                return_dict=False,
            )
            generated = response["output_ids"]
            if (
                ids != request["input_ids"]
                or len(ids) != response["input_tokens"]
                or response["request_sha256"] != digest(request_path)
                or len(generated) != response["output_tokens"]
                or len(generated) > request["max_new_tokens"]
                or tokenizer.decode(generated, skip_special_tokens=True)
                != response["raw"]
                or response["ended_with_eos"]
                != bool(
                    (generated and generated[-1] in eos)
                    or (
                        response.get("finish_reason") == "stop"
                        and response.get("stop_reason") in eos
                    )
                )
                or publication["response_sha256"] != digest(path)
            ):
                raise ValueError(
                    "Original local tokens/request/text/publication do not reconstruct"
                )
            if (
                cid != "compatibility"
                and request["messages"]
                != read(gpu / "policy" / (cid + ".json"))["messages"]
            ):
                raise ValueError("Original local prompt was not the registered policy")
            rows.append(
                {
                    "rank": rank,
                    "call_id": cid,
                    "benchmark": cid != "compatibility",
                    "input_tokens": len(ids),
                    "output_tokens": len(generated),
                    "ended_with_eos": response["ended_with_eos"],
                    "lifecycle_seconds": publication["lifecycle_seconds"],
                    "generation_seconds": response["seconds"],
                }
            )
    publish(
        out / "LOCAL_TOKEN_AUDIT.json",
        {
            "passed": True,
            "responses": len(rows),
            "benchmark": sum(r["benchmark"] for r in rows),
            "output_tokens": sum(r["output_tokens"] for r in rows),
            "source_weights_verified_by_original_worker": (
                gpu / "WORKER_PREFLIGHT.json"
            ).exists(),
            "local_tokenizer_and_runtime_independently_verified": True,
            "rows": rows,
            "model_calls": 0,
        },
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--wait-seconds", type=int, default=5400)
    args = parser.parse_args()
    args.out.mkdir(exist_ok=False)
    publish(
        args.out / "STARTED.json",
        {
            "at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "pid": os.getpid(),
            "model_calls": 0,
        },
    )
    has_api = bool(read(args.batch / "PLAN.json")["api_models"])
    deadline = time.monotonic() + args.wait_seconds
    while not (
        (args.batch / "gpu/submission_01/EXIT.json").exists()
        and (not has_api or (args.batch / "api/runtime/RESULT.json").exists())
    ):
        if time.monotonic() >= deadline:
            publish(
                args.out / "WAIT_EXPIRED.json",
                {"model_calls": 0, "captures_preserved": True},
            )
            raise SystemExit(124)
        time.sleep(20)
    scorer = args.batch / read(args.batch / "PLAN.json")["scorer_source"]
    command = [
        sys.executable,
        str(scorer),
        "--batch",
        str(args.batch),
        "--out",
        str(args.out / "scores"),
    ]
    publish(args.out / "SCORE_COMMAND.json", command)
    with (args.out / "score.log").open("x") as handle:
        process = subprocess.run(
            command, stdout=handle, stderr=subprocess.STDOUT, check=False, timeout=1800
        )
    if process.returncode:
        publish(
            args.out / "SCORE_FAILED.json",
            {"exit_code": process.returncode, "new_model_calls": 0},
        )
        raise SystemExit(process.returncode)
    token_audit(args.batch, args.out)
    publish(
        args.out / "RESULT.json",
        {
            "passed": True,
            "scoring_passed": True,
            "local_tokens_passed": True,
            "api_original_wire_usage_rechecked_by_scorer": has_api,
            "model_calls": 0,
            "confirmation_opened": False,
            "gpu_terminal": read(args.batch / "gpu/submission_01/EXIT.json"),
            "api_terminal": read(args.batch / "api/runtime/RESULT.json")
            if has_api
            else None,
            "finished_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        },
    )
    print(json.dumps(read(args.out / "RESULT.json")), flush=True)


if __name__ == "__main__":
    main()
