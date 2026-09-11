"""Pinned local model runtime for separately frozen state and visual diagnostics."""

from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import socket
import subprocess
import time

from model_adapter_intern import load_frontend, prepare
from model_adapter import save, sha_file, text_file


def now():
    return datetime.now(timezone.utc).isoformat()


class Backend:
    def __init__(self, batch, plan, worker, output):
        import torch
        from transformers import AutoModelForCausalLM, Qwen3VLForConditionalGeneration

        self.batch, self.settings, self.plan = batch, plan["settings"], plan
        self.spec = plan["models"][plan["workers"][worker]["model"]]
        self.requests = 0
        self.max_requests = plan["workers"][worker]["max_calls"]
        for rel, expected in plan["bound_files"].items():
            if sha_file(batch / rel) != expected:
                raise ValueError("frozen diagnostic file changed: " + rel)
        for path, expected in plan["runtime_files"].items():
            if sha_file(path) != expected:
                raise ValueError("runtime changed: " + path)
        versions = {name: importlib.metadata.version(name) for name in plan["runtime_versions"]}
        if versions != plan["runtime_versions"]:
            raise ValueError("runtime version mismatch")
        torch.set_num_threads(4)
        torch.manual_seed(self.settings["seed"])
        if torch.cuda.device_count() != 1:
            raise ValueError("expected one visible H100")
        device = torch.cuda.get_device_properties(0)
        if "H100" not in device.name or device.total_memory < 75 * 1024**3:
            raise ValueError("expected H10080GB")
        save(output / "HARDWARE.json", {"at": now(), "hostname": socket.gethostname(), "name": device.name,
             "count": 1, "bytes": device.total_memory, "runtime_versions": versions,
             "nvidia_smi": subprocess.check_output(["nvidia-smi", "--query-gpu=name,uuid,driver_version,memory.total", "--format=csv,noheader"], text=True)})
        for row in self.spec["files"]:
            path = Path(self.spec["directory"]) / row["path"]
            if path.stat().st_size != row["bytes"] or sha_file(path) != row["sha256"]:
                raise ValueError("model integrity failed: " + row["path"])
        save(output / "MODEL_VERIFIED.json", {"at": now(), "files": len(self.spec["files"]), "revision": self.spec["revision"]})
        self.frontend = load_frontend(self.spec, self.settings)
        klass = Qwen3VLForConditionalGeneration if self.spec["kind"] == "vl" else AutoModelForCausalLM
        self.model = klass.from_pretrained(self.spec["directory"], local_files_only=True, trust_remote_code=False,
            dtype=torch.bfloat16, device_map={"": 0}, attn_implementation="sdpa").eval()
        self.tokenizer = self.frontend.tokenizer if self.spec["kind"] == "vl" else self.frontend
        self.torch = torch
        save(output / "LOADED.json", {"at": now(), "allocated_bytes": torch.cuda.memory_allocated(),
             "parameters": sum(p.numel() for p in self.model.parameters())})

    def preflight(self, state, slot):
        inputs, record = prepare(self.frontend, self.spec["kind"], state, self.batch, self.settings, slot)
        with self.torch.inference_mode():
            output = self.model(**{k: v.to("cuda") for k, v in inputs.items()}, use_cache=False, logits_to_keep=1)
            if not self.torch.isfinite(output.logits).all():
                raise ValueError("nonfinite preflight")
        return record

    def call(self, state, slot):
        if self.requests >= self.max_requests:
            raise ValueError("worker request cap exceeded")
        if time.time() + self.settings["max_generation_seconds"] >= self.plan["deadline_unix"]:
            raise TimeoutError("not enough remaining scope for a generation")
        inputs, processor = prepare(self.frontend, self.spec["kind"], state, self.batch, self.settings, slot)
        save(slot / "request.json", state)
        save(slot / "intent.json", {"at": now(), "request_sha256": sha_file(slot / "request.json"),
             "plan_sha256": sha_file(self.batch / "PLAN.json")})
        self.requests += 1
        started = time.monotonic()
        with self.torch.inference_mode():
            output = self.model.generate(**{k: v.to("cuda") for k, v in inputs.items()},
                do_sample=False, use_cache=True, max_new_tokens=self.settings["max_new_tokens"],
                max_time=self.settings["max_generation_seconds"], pad_token_id=self.tokenizer.pad_token_id,
                return_dict_in_generate=True)
        self.torch.cuda.synchronize()
        ids = output.sequences[0, inputs["input_ids"].shape[-1]:].tolist()
        raw = self.tokenizer.decode(ids, skip_special_tokens=True)
        text_file(slot / "raw.txt", raw)
        save(slot / "tokens.json", ids)
        eos = self.model.generation_config.eos_token_id
        eos = eos if isinstance(eos, list) else [eos]
        ended = bool(ids and ids[-1] in eos)
        save(slot / "response.json", {"at": now(), "seconds": time.monotonic() - started,
             "ended_eos": ended, "generated_tokens": len(ids), "raw_sha256": sha_file(slot / "raw.txt")})
        return raw, ended
