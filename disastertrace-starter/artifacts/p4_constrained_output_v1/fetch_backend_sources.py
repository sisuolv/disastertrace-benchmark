"""Save official tagged source bytes and compare them with installed backend files."""

import importlib.metadata
import urllib.request
from pathlib import Path

from disastertrace.local_eval.storage import digest, now, seal, write

HERE = Path(__file__).resolve().parent
SOURCES = {
    "vllm/v1/structured_output/__init__.py": "https://raw.githubusercontent.com/vllm-project/vllm/v0.10.2/vllm/v1/structured_output/__init__.py",
    "vllm/v1/structured_output/backend_xgrammar.py": "https://raw.githubusercontent.com/vllm-project/vllm/v0.10.2/vllm/v1/structured_output/backend_xgrammar.py",
    "vllm/reasoning/qwen3_reasoning_parser.py": "https://raw.githubusercontent.com/vllm-project/vllm/v0.10.2/vllm/reasoning/qwen3_reasoning_parser.py",
    "xgrammar/compiler.py": "https://raw.githubusercontent.com/mlc-ai/xgrammar/v0.1.23/python/xgrammar/compiler.py",
}


def main():
    root = HERE / "official_backend_sources"
    root.mkdir(exist_ok=False)
    observations = []
    for name, url in SOURCES.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        installed = importlib.metadata.distribution(name.split("/")[0]).locate_file(name)
        with urllib.request.urlopen(url, timeout=30) as response:
            data = response.read()
            status = response.status
        path.write_bytes(data)
        row = {
            "path": name,
            "url": url,
            "retrieved_at": now(),
            "http_status": status,
            "sha256": digest(path),
            "installed_sha256": digest(installed),
            "matches_installed": path.read_bytes() == Path(installed).read_bytes(),
        }
        observations.append(row)
        print(row, flush=True)
    write(root / "observations.json", observations)
    seal(root)
    if not all(row["matches_installed"] for row in observations):
        raise ValueError("installed backend differs from official tagged source")


if __name__ == "__main__":
    main()
