"""Download a content-pinned official Qwen ModelScope snapshot; no model calls."""

import concurrent.futures
import hashlib
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DESTINATION = Path("/mnt/afs/260010168/models/Qwen3-8B-modelscope-pinned-v1")


def download(item):
    name = item["Path"]
    if "/" in name or name.startswith("."):
        return None
    path = DESTINATION / name
    query = urllib.parse.urlencode({"Revision": item["Revision"], "FilePath": name})
    url = "https://modelscope.cn/api/v1/models/Qwen/Qwen3-8B/repo?" + query
    if path.exists():
        raise ValueError("Preserve existing download: " + name)
    temporary = path.with_suffix(path.suffix + ".partial")
    digest, size = hashlib.sha256(), 0
    started = datetime.now(timezone.utc).isoformat()
    with urllib.request.urlopen(url, timeout=180) as response, temporary.open("xb") as stream:
        while block := response.read(8 * 1024 * 1024):
            stream.write(block)
            digest.update(block)
            size += len(block)
        stream.flush()
        os.fsync(stream.fileno())
    if digest.hexdigest() != item["Sha256"] or size != item["Size"]:
        raise ValueError("Official digest/size mismatch: " + name)
    temporary.rename(path)
    result = {
        "path": name,
        "sha256": digest.hexdigest(),
        "bytes": size,
        "revision": item["Revision"],
        "url": url,
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }
    print(json.dumps(result), flush=True)
    return result


if __name__ == "__main__":
    DESTINATION.mkdir(parents=True, exist_ok=True)
    files = json.loads((HERE / "references/qwen_files.json").read_text())["Data"]["Files"]
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        results = [r for r in pool.map(download, files) if r is not None]
    manifest = {
        "model_id": "Qwen/Qwen3-8B",
        "origin": "official_qwen_modelscope",
        "snapshot_kind": "per_file_commit_and_official_sha256",
        "local_path": str(DESTINATION),
        "files": results,
    }
    with (HERE / "model_snapshot.json").open("x") as stream:
        json.dump(manifest, stream, indent=2)
        stream.write("\n")
