"""Seal verified official checkpoint resources without copying model weights into artifacts."""

import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import shutil

from disastertrace.forecast_live import package as native
from disastertrace.forecast_live.storage import now, write
from disastertrace.forecast_task.common import digest, fingerprint, read, seal

ROOT = Path(__file__).resolve().parent
PREPARATION = ROOT.with_name("p9_model_preparation_v1")
MODEL = Path("/mnt/afs/260010168/models/DeepSeek-R1-Distill-Qwen-7B-modelscope-pinned-v1")


def main():
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "":
        raise ValueError("resource preparation is CPU-only")
    from transformers import AutoTokenizer

    output = ROOT / "resources_01"
    output.mkdir(exist_ok=False)
    write(ROOT / "RESOURCE_BUILD_CLAIM.json", {"at": now(), "script_sha256": digest(__file__), "model_calls": 0})
    metadata = PREPARATION / "deepseek-ai--DeepSeek-R1-Distill-Qwen-7B"
    listing = read(metadata / "listing.json")
    listed = {item["Path"]: item for item in listing["Data"]["Files"] if item["Type"] == "blob"}
    for stage in ("tokenizer", "weights"):
        if read(PREPARATION / ("pinned_" + stage + "_01/RESULT.json"))["status"] != "passed":
            raise ValueError("checkpoint acquisition did not complete")
    files = []
    for path in sorted(MODEL.iterdir()):
        item = listed[path.name]
        sha = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                sha.update(block)
        if path.stat().st_size != item["Size"] or sha.hexdigest() != item["Sha256"]:
            raise ValueError("checkpoint bytes no longer match the official listing")
        files.append({"path": path.name, "bytes": item["Size"], "sha256": item["Sha256"],
                      "revision": item["Revision"], "verified_at": now()})
    snapshot = {"local_path": str(MODEL), "model_id": "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
                "origin": "official_deepseek_modelscope", "snapshot_kind": "per_file_commit_and_official_sha256", "files": files}
    index = read(MODEL / "model.safetensors.index.json")
    tensor_names, total_parameters, dtypes = {}, 0, set()
    for path in sorted(MODEL.glob("*.safetensors")):
        with path.open("rb") as stream:
            length = int.from_bytes(stream.read(8), "little")
            if not 0 < length < 10_000_000:
                raise ValueError("unexpected safetensors header length")
            header = json.loads(stream.read(length))
        for name, tensor in header.items():
            if name == "__metadata__":
                continue
            if name in tensor_names or index["weight_map"].get(name) != path.name:
                raise ValueError("safetensors headers disagree with official index")
            tensor_names[name] = path.name
            total_parameters += math.prod(tensor["shape"])
            dtypes.add(tensor["dtype"])
    if tensor_names != index["weight_map"] or dtypes != {"BF16"}:
        raise ValueError("incomplete tensor index or unexpected precision")
    tokenizer = AutoTokenizer.from_pretrained(MODEL, local_files_only=True, trust_remote_code=False)
    config, generation = read(MODEL / "config.json"), read(MODEL / "generation_config.json")
    if (config["model_type"] != "qwen2" or config["architectures"] != ["Qwen2ForCausalLM"]
            or config["max_position_embeddings"] < 32768
            or tokenizer.eos_token_id != config["eos_token_id"] or tokenizer.eos_token_id != generation["eos_token_id"]
            or len(tokenizer.encode("</think>", add_special_tokens=False)) != 1):
        raise ValueError("actual checkpoint/tokenizer settings differ from selected model")
    (output / "tokenizer").mkdir()
    for name in ("config.json", "tokenizer_config.json", "tokenizer.json", "generation_config.json"):
        shutil.copyfile(MODEL / name, output / "tokenizer" / name)
    (output / "official_metadata").mkdir()
    for name in ("listing.json", "listing_receipt.json", "README.md", "LICENSE", "RESULT.json"):
        shutil.copyfile(metadata / name, output / "official_metadata" / name)
    shutil.copyfile(PREPARATION / "TOKENIZER_FEASIBILITY_01.json", output / "tokenizer_feasibility.json")
    write(output / "model_snapshot.json", snapshot)
    environment = native.environment()
    baseline_environment = read(ROOT.parent / "p7_forecast_live_v1/execution_live_01/environment.json")
    if environment != baseline_environment:
        raise ValueError("installed GPU environment differs from native baseline")
    write(output / "environment.json", environment)
    names = (*native.BACKEND_FILES, "vllm/reasoning/deepseek_r1_reasoning_parser.py")
    backend_files = {}
    for name in names:
        path = importlib.metadata.distribution(name.split("/")[0]).locate_file(name)
        backend_files[name] = digest(path)
        target = output / "backend_source" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    write(output / "backend_files.json", backend_files)
    record = {"status": "passed", "model_identity": fingerprint(snapshot), "backend_files": backend_files,
              "environment_sha256": fingerprint(environment), "parameter_count": total_parameters,
              "tensor_count": len(tensor_names), "tensor_dtypes": sorted(dtypes),
              "eos_token_id": tokenizer.eos_token_id, "bos_token_id": tokenizer.bos_token_id,
              "open_think_ids": tokenizer.encode("<think>", add_special_tokens=False),
              "close_think_ids": tokenizer.encode("</think>", add_special_tokens=False),
              "model_calls": 0, "hardware_preflight": "pending", "at": now()}
    write(output / "resources.json", record)
    sealed = seal(output)
    print({"status": "passed", "resource_package_id": sealed["package_id"], "parameter_count": total_parameters,
           "tensor_count": len(tensor_names), "model_calls": 0}, flush=True)


if __name__ == "__main__":
    main()
