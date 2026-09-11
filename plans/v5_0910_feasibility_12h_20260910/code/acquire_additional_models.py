"""Complete a pinned partial shard, then acquire an audited native-HF InternVL."""

import concurrent.futures
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
from urllib.parse import urlencode

import requests

from common import ROOT, capture, dump
from model_adapter import sha_file


def now():
    return datetime.now(timezone.utc).isoformat()


def download(row, model, dest, run, deadline, prefix=None):
    name = row["Path"]
    offset = prefix.stat().st_size if prefix else 0
    if (dest / name).exists():
        raise ValueError("refusing to replace existing model file")
    intent = {"at": now(), "path": name, "offset": offset, "revision": row["Revision"],
              "expected_bytes": row["Size"], "expected_sha256": row["Sha256"]}
    dump(run / (name + ".intent.json"), intent)
    part = dest / (name + (".resume.partial" if prefix else ".partial"))
    if part.exists():
        raise ValueError("attempt path already exists")
    if prefix:
        shutil.copyfile(prefix, part)
    result = {**intent, "status": "failed", "received_bytes": 0}
    start = time.monotonic()
    try:
        headers = {"Accept-Encoding": "identity"}
        if offset:
            headers["Range"] = f"bytes={offset}-"
        url = "https://modelscope.cn/api/v1/models/" + model + "/repo?" + urlencode({
            "Revision": row["Revision"], "FilePath": name})
        with requests.Session() as session:
            session.trust_env = False
            with session.get(url, stream=True, timeout=(20, 60), headers=headers) as response:
                result["http_status"] = response.status_code
                response.raise_for_status()
                if offset and (response.status_code != 206 or
                               response.headers.get("Content-Range") != f"bytes {offset}-{row['Size']-1}/{row['Size']}"):
                    raise ValueError("server did not honor exact pinned Range")
                with part.open("ab" if prefix else "xb") as stream:
                    for chunk in response.iter_content(1024**2):
                        if time.time() >= deadline or time.monotonic() - start >= 3600:
                            raise TimeoutError("bounded acquisition deadline")
                        if offset + result["received_bytes"] + len(chunk) > row["Size"]:
                            raise ValueError("response exceeds pinned size")
                        stream.write(chunk)
                        result["received_bytes"] += len(chunk)
        if part.stat().st_size != row["Size"] or sha_file(part) != row["Sha256"]:
            raise ValueError("complete size/SHA256 mismatch")
        os.replace(part, dest / name)
        result["status"] = "verified"
    except Exception as error:
        result["error"] = {"type": type(error).__name__, "message": str(error).split("?")[0][:300]}
    result.update(finished_at=now(), elapsed_seconds=time.monotonic() - start)
    dump(run / (name + ".result.json"), result)
    print(json.dumps({"model": model, "file": name, "status": result["status"],
                      "new_bytes": result["received_bytes"]}), flush=True)
    return result


def main():
    scope = json.loads((ROOT / "SCOPE.json").read_text())
    deadline = datetime.fromisoformat(scope["deadline_utc"]).timestamp() - 3600
    old = ROOT / "gpu/model32_acquisition"
    waiting = ROOT / "gpu/additional_acquisition"
    waiting.mkdir(exist_ok=False)
    dump(waiting / "PLAN.json", {"at": now(), "wait_for": "gpu/model32_acquisition/COMPLETED.json",
         "reason": "Keep at most two simultaneous weight download streams to ModelScope.",
         "deadline_unix": deadline, "scope_weight_bytes": scope["max_additional_weight_bytes"]})
    while not (old / "COMPLETED.json").exists():
        if time.time() >= deadline:
            raise TimeoutError("initial acquisition did not finish within scope")
        time.sleep(5)
    previous = json.loads((old / "PLAN.json").read_text())
    dest32 = Path(previous["destination"])
    failed = [x for x in previous["files"] if not (dest32 / x["Path"]).exists()]
    resume_run = ROOT / "gpu/model32_resume_01"
    resume_run.mkdir(exist_ok=False)
    resumed = []
    for row in failed:
        prefix = dest32 / (row["Path"] + ".partial")
        prior = json.loads((old / (row["Path"] + ".result.json")).read_text())
        if not prefix.exists() or prefix.stat().st_size != prior["actual_bytes"]:
            raise ValueError("failed prefix identity changed")
        if prior.get("actual_sha256") and sha_file(prefix) != prior["actual_sha256"]:
            raise ValueError("failed prefix hash changed")
        resumed.append(download(row, "Qwen/Qwen3-VL-32B-Instruct", dest32, resume_run, deadline, prefix))
    dump(resume_run / "COMPLETED.json", {"at": now(), "all_verified": all(x["status"] == "verified" for x in resumed),
         "new_bytes": sum(x["received_bytes"] for x in resumed), "results": resumed})
    body, source = capture("internvl3_5-8b-hf-ms-files")
    listing = json.loads(body)["Data"]["Files"]
    files = [x for x in listing if "/" not in x["Path"] and
             (x["Path"].endswith((".safetensors", ".json", ".jinja", ".txt")) or x["Path"] == "README.md")]
    if any(not x["Sha256"] or not x["Revision"] for x in files):
        raise ValueError("unbound InternVL file")
    prior_bytes = json.loads((old / "COMPLETED.json").read_text())["downloaded_bytes"]
    resumed_bytes = sum(x["received_bytes"] for x in resumed)
    if prior_bytes + resumed_bytes + sum(x["Size"] for x in files) > scope["max_additional_weight_bytes"]:
        raise ValueError("combined weight byte cap exceeded")
    run = ROOT / "gpu/internvl_acquisition"
    dest = Path("/mnt/afs/260010168/models/InternVL3_5-8B-HF-feasibility-20260910")
    run.mkdir(exist_ok=False)
    dest.mkdir(exist_ok=False)
    dump(run / "PLAN.json", {"created_at": now(), "model": "OpenGVLab/InternVL3_5-8B-HF",
         "destination": str(dest), "files": files, "metadata_source": source,
         "total_bytes": sum(x["Size"] for x in files), "parallel_downloads": 2,
         "automatic_retries": 0, "trust_remote_code": False,
         "license_evidence": "captured intern35-README-md: Apache2, Qwen3 component Apache2",
         "shared_component_limit": "Different VLM family, but both InternVL3.5 and Qwen3 text share Qwen3 lineage."})
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(download, x, "OpenGVLab/InternVL3_5-8B-HF", dest, run, deadline) for x in files]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    dump(run / "COMPLETED.json", {"at": now(), "all_verified": all(x["status"] == "verified" for x in results),
         "received_bytes": sum(x["received_bytes"] for x in results), "results": results})


if __name__ == "__main__":
    main()
