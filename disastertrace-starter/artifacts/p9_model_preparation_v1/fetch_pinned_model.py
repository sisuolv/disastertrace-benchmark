"""Acquire selected public model files against the already captured official listing."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
from pathlib import Path
import shutil
import urllib.parse
import urllib.request

from disastertrace.forecast_live.storage import now, write
from disastertrace.forecast_task.common import digest, read

ROOT = Path(__file__).resolve().parent
MODEL = "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B"
METADATA = ROOT / MODEL.replace("/", "--")
DESTINATION = Path("/mnt/afs/260010168/models/DeepSeek-R1-Distill-Qwen-7B-modelscope-pinned-v1")


def acquire(item, receipts):
    name = item["Path"]
    if Path(name).name != name or not item["Revision"] or len(item["Sha256"]) != 64:
        raise ValueError("unbound or unsafe source path")
    url = "https://modelscope.cn/api/v1/models/" + MODEL + "/repo?" + urllib.parse.urlencode(
        {"Revision": item["Revision"], "FilePath": name}
    )
    write(receipts / (name + ".intent.json"), {"at": now(), "url": url, "expected": item})
    target = DESTINATION / name
    partial = DESTINATION / (name + ".partial")
    if target.exists() or partial.exists():
        raise FileExistsError("acquisition path already consumed: " + name)
    size, sha = 0, hashlib.sha256()
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "DisasterTrace-pinned-model/1"})
        with urllib.request.urlopen(request, timeout=120) as response, partial.open("xb") as stream:
            if response.status != 200:
                raise ValueError("unexpected download response")
            while chunk := response.read(8 * 1024 * 1024):
                size += len(chunk)
                if size > item["Size"]:
                    raise ValueError("file exceeds official size")
                stream.write(chunk)
                sha.update(chunk)
        if size != item["Size"] or sha.hexdigest() != item["Sha256"]:
            raise ValueError("download differs from official SHA256 or size")
        partial.rename(target)
        result = {"status": "verified", "path": name, "bytes": size, "sha256": sha.hexdigest(),
                  "revision": item["Revision"], "url": url, "completed_at": now()}
    except Exception as exc:
        result = {"status": "failed", "path": name, "received_bytes": size,
                  "error": type(exc).__name__ + ": " + str(exc), "at": now()}
    write(receipts / (name + ".result.json"), result)
    print(result, flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("tokenizer", "weights"))
    stage = parser.parse_args().stage
    receipts = ROOT / ("pinned_" + stage + "_01")
    receipts.mkdir(exist_ok=False)
    listing = read(METADATA / "listing.json")
    selected = ({"tokenizer.json", "model.safetensors.index.json"} if stage == "tokenizer"
                else {"model-00001-of-000002.safetensors", "model-00002-of-000002.safetensors"})
    items = [x for x in listing["Data"]["Files"] if x["Path"] in selected and x["Type"] == "blob"]
    if {x["Path"] for x in items} != selected:
        raise ValueError("incomplete official file listing")
    write(receipts / "CLAIM.json", {"at": now(), "stage": stage, "model": MODEL,
          "listing_sha256": digest(METADATA / "listing.json"), "files": items,
          "destination": str(DESTINATION), "model_calls": 0, "automatic_retries": 0})
    if stage == "tokenizer":
        DESTINATION.mkdir(exist_ok=False)
        for name in ("config.json", "generation_config.json", "tokenizer_config.json", "LICENSE", "README.md"):
            source = METADATA / name
            item = next(x for x in listing["Data"]["Files"] if x["Path"] == name)
            if digest(source) != item["Sha256"]:
                raise ValueError("previous metadata changed")
            shutil.copyfile(source, DESTINATION / name)
    elif not (DESTINATION / "tokenizer.json").is_file():
        raise ValueError("tokenizer feasibility preparation must precede weights")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda item: acquire(item, receipts), items))
    write(receipts / "RESULT.json", {"status": "passed" if all(r["status"] == "verified" for r in results) else "failed",
          "files": results, "model_calls": 0, "completed_at": now()})
    return 0 if all(r["status"] == "verified" for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
