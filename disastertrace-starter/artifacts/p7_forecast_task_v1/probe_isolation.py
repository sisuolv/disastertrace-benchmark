"""Diagnose a blocked optional import operation without running program diagnostics."""

import json
import os
import sys
import traceback
from pathlib import Path

copied = Path(sys.argv[1]).resolve()
blocked = tuple(Path(p).resolve() for p in sys.argv[2:])
events = []


def guard(event, values):
    if event in ("open", "os.listdir", "os.scandir") and values:
        value = values[0]
        if isinstance(value, (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(value)).resolve()
            if not path.is_relative_to(copied) and any(path.is_relative_to(b) for b in blocked):
                events.append({"event": event, "path": str(path)})
                raise PermissionError("original path blocked")
    if event in ("subprocess.Popen", "os.system", "os.posix_spawn", "os.exec", "os.fork"):
        events.append(
            {
                "event": event,
                "executable": str(values[0]),
                "argv": str(values[1]) if len(values) > 1 else None,
            }
        )
        raise PermissionError("subprocess blocked")
    if event in ("socket.connect", "socket.getaddrinfo", "socket.bind", "socket.sendto"):
        events.append(
            {
                "event": event,
                "address": str(values[1:]),
                "stack": [str(frame) for frame in traceback.extract_stack(limit=7)],
            }
        )
        raise PermissionError("network blocked")
    if event == "import" and values[0].split(".")[0] in ("torch", "vllm", "tensorflow", "flax"):
        events.append({"event": event, "name": values[0]})
        raise PermissionError("model backend import blocked")


sys.addaudithook(guard)
sys.path[:] = [str(copied / "execution/source/src")] + [
    p for p in sys.path if p and not any(Path(p).resolve().is_relative_to(b) for b in blocked)
]
os.chdir(copied)
from transformers import AutoTokenizer

from disastertrace.forecast_task.package import _runtime

tokenizer = AutoTokenizer.from_pretrained(
    copied / "execution/tokenizer", local_files_only=True, trust_remote_code=False
)
tokenizer.apply_chat_template(
    [{"role": "user", "content": "offline tokenizer fixture"}],
    tokenize=True,
    add_generation_prompt=True,
    enable_thinking=True,
)
print(
    json.dumps(
        {
            "runtime": _runtime(),
            "guard_events": events,
            "backend_modules": [
                name for name in ("torch", "vllm", "tensorflow", "flax") if name in sys.modules
            ],
        }
    )
)
