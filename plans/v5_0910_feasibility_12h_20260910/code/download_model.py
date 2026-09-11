"""Bounded, pinned, streaming ModelScope acquisition; never executes hub code."""

import concurrent.futures
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import requests

from common import ROOT, capture, digest, dump

DEST = Path("/mnt/afs/260010168/models/Qwen3-VL-32B-Instruct-feasibility-20260910")
RUN = ROOT / "gpu/model32_acquisition"


def now():
    return datetime.now(timezone.utc).isoformat()


def acquire(row, deadline):
    name = row["Path"]
    intent = {"at": now(), "path": name, "expected_bytes": row["Size"],
              "revision": row["Revision"], "expected_sha256": row["Sha256"]}
    dump(RUN / (name + ".intent.json"), intent)
    result = {**intent, "status": "failed", "actual_bytes": 0}
    part = DEST / (name + ".partial")
    started = time.monotonic()
    sha = hashlib.sha256()
    try:
        url = "https://modelscope.cn/api/v1/models/Qwen/Qwen3-VL-32B-Instruct/repo?" + urlencode({
            "Revision": row["Revision"], "FilePath": name})
        with requests.Session() as session:
            session.trust_env = False
            with session.get(url, stream=True, timeout=(20, 60),
                             headers={"Accept-Encoding": "identity"}) as response:
                response.raise_for_status()
                result["http_status"] = response.status_code
                with part.open("xb") as stream:
                    for chunk in response.iter_content(1024 * 1024):
                        if time.time() >= deadline or time.monotonic() - started >= 3600:
                            raise TimeoutError("model acquisition deadline")
                        if result["actual_bytes"] + len(chunk) > row["Size"]:
                            raise ValueError("response exceeds pinned file size")
                        stream.write(chunk)
                        sha.update(chunk)
                        result["actual_bytes"] += len(chunk)
        result["actual_sha256"] = sha.hexdigest()
        if result["actual_bytes"] != row["Size"] or sha.hexdigest() != row["Sha256"]:
            raise ValueError("model file size/hash mismatch")
        os.replace(part, DEST / name)
        result["status"] = "verified"
    except Exception as error:
        result["error"] = {"type": type(error).__name__, "message": str(error).split("?")[0][:300]}
    result.update(finished_at=now(), elapsed_seconds=time.monotonic() - started)
    dump(RUN / (name + ".result.json"), result)
    print(json.dumps({"file": name, "status": result["status"], "bytes": result["actual_bytes"]}), flush=True)
    return result


def main():
    scope = json.loads((ROOT / "SCOPE.json").read_text())
    deadline = datetime.fromisoformat(scope["deadline_utc"]).timestamp() - 3600
    body, provenance = capture("qwen32-ms-metadata")
    listing = json.loads(body)
    if not listing["Success"]:
        raise ValueError("model metadata failed")
    allowed = {"chat_template.json", "config.json", "generation_config.json", "merges.txt",
               "model.safetensors.index.json", "preprocessor_config.json", "README.md",
               "tokenizer.json", "tokenizer_config.json", "video_preprocessor_config.json", "vocab.json"}
    files = [x for x in listing["Data"]["Files"] if x["Path"] in allowed or
             x["Path"].startswith("model-") and x["Path"].endswith(".safetensors")]
    size = sum(x["Size"] for x in files)
    if size > scope["max_additional_weight_bytes"] or len(files) > scope["max_weight_download_http_attempts"]:
        raise ValueError("weight acquisition budget exceeded")
    if any("/" in x["Path"] or not x["Sha256"] for x in files):
        raise ValueError("unsafe or unpinned model file")
    RUN.mkdir(exist_ok=False)
    DEST.mkdir(exist_ok=False)
    dump(RUN / "PLAN.json", {"created_at": now(), "model": "Qwen/Qwen3-VL-32B-Instruct",
         "destination": str(DEST), "metadata_source": provenance,
         "files": files, "total_bytes": size, "deadline_unix": deadline,
         "parallel_downloads": 2, "automatic_retries": 0, "trust_remote_code": False})
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(acquire, row, deadline) for row in files]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
    verified = all(x["status"] == "verified" for x in results)
    dump(RUN / "COMPLETED.json", {"finished_at": now(), "all_verified": verified,
         "planned_files": len(files), "verified_files": sum(x["status"] == "verified" for x in results),
         "downloaded_bytes": sum(x["actual_bytes"] for x in results)})
    if not verified:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
