"""Bounded, revision-pinned acquisition from Qwen's ModelScope repository."""

import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
MODEL = "Qwen/Qwen3-VL-8B-Instruct"
BASE = "https://modelscope.cn/api/v1/models/" + MODEL
DEST = Path("/mnt/afs/260010168/models/Qwen3-VL-8B-Instruct-mm3-pinned-v1")


def write(path, data):
    with path.open("x") as stream:
        json.dump(data, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def fetch_small(url, path):
    if path.exists():
        return path.read_bytes()
    with urllib.request.urlopen(url, timeout=45) as response:
        data = response.read(2 * 1024 * 1024 + 1)
    if len(data) > 2 * 1024 * 1024:
        raise ValueError("metadata byte cap")
    with path.open("xb") as stream:
        stream.write(data)
    return data


def main():
    evidence = ROOT / "model_acquisition"
    evidence.mkdir(exist_ok=True)
    listing = json.loads(fetch_small(BASE + "/repo/files?Revision=master&Recursive=true", evidence / "discovery.json"))
    rows = listing["Data"]["Files"]
    # ModelScope lists each file's last change, not the repository HEAD.
    # Resolve the latest listed commit and verify its complete tree explicitly.
    revision = max(rows, key=lambda r: r.get("CommittedDate", 0))["Revision"]
    pinned = json.loads(fetch_small(BASE + "/repo/files?Revision=" + revision + "&Recursive=true", evidence / "pinned_listing.json"))
    selected = [r for r in pinned["Data"]["Files"] if r["Type"] == "blob" and not r["Path"].startswith(".")]
    expected = {r["Path"]: (r["Size"], r["Sha256"]) for r in rows if r["Type"] == "blob" and not r["Path"].startswith(".")}
    if {r["Path"]: (r["Size"], r["Sha256"]) for r in selected} != expected:
        raise ValueError("pinned snapshot does not reproduce discovery tree")
    if sum(r["Size"] for r in selected) > 24 * 1024**3:
        raise ValueError("model byte budget")
    if any(Path(r["Path"]).name != r["Path"] or not r["Sha256"] for r in selected):
        raise ValueError("unexpected file or missing digest")
    DEST.mkdir(exist_ok=True)
    plan = {"model": MODEL, "provider": "official Qwen ModelScope namespace", "revision": revision,
            "files": selected, "expected_bytes": sum(r["Size"] for r in selected),
            "max_reserved_network_bytes": 40 * 1024**3, "max_attempts_per_file": 2,
            "huggingface_probe": "Network is unreachable; use separately pinned ModelScope revision"}
    plan_path = evidence / "plan.json"
    if plan_path.exists():
        if json.loads(plan_path.read_text()) != plan:
            raise ValueError("acquisition plan changed")
    else:
        write(plan_path, plan)
    # Each interrupted attempt remains charged at its full reserved file size.
    attempts = []
    for row in selected:
        path = DEST / row["Path"]
        if path.exists():
            h = hashlib.file_digest(path.open("rb"), "sha256").hexdigest() if hasattr(hashlib, "file_digest") else file_hash(path)
            if h != row["Sha256"] or path.stat().st_size != row["Size"]:
                raise ValueError("existing verified file changed")
            continue
        used = list(evidence.glob(row["Path"] + ".attempt-*.intent.json"))
        if len(used) >= 2:
            raise ValueError("file attempt budget consumed")
        attempt = len(used) + 1
        name = row["Path"] + ".attempt-" + str(attempt)
        url = BASE + "/repo?" + urllib.parse.urlencode({"Revision": revision, "FilePath": row["Path"]})
        attempts.append((row, name, url))
    reserved = sum(json.loads(p.read_text())["reserved_bytes"] for p in evidence.glob("*.intent.json"))
    if reserved + sum(r["Size"] for r, _, _ in attempts) > plan["max_reserved_network_bytes"]:
        raise ValueError("cumulative network reservation exhausted")
    for row, name, url in attempts:
        write(evidence / (name + ".intent.json"), {"url": url, "reserved_bytes": row["Size"], "at": time.time()})

    def download(item):
        row, name, url = item
        partial = DEST / (name + ".partial")
        n, h, start = 0, hashlib.sha256(), time.time()
        try:
            with urllib.request.urlopen(url, timeout=60) as response, partial.open("xb") as stream:
                while True:
                    block = response.read(min(8 * 1024**2, row["Size"] - n + 1))
                    if not block:
                        break
                    n += len(block)
                    if n > row["Size"]:
                        raise ValueError("file exceeds reserved bytes")
                    stream.write(block)
                    h.update(block)
                stream.flush()
                os.fsync(stream.fileno())
            if n != row["Size"] or h.hexdigest() != row["Sha256"]:
                raise ValueError("size/digest mismatch")
            os.link(partial, DEST / row["Path"])
            partial.unlink()
            result = {"status": "verified", "bytes": n, "sha256": h.hexdigest(), "seconds": time.time() - start}
        except Exception as error:
            result = {"status": "failed", "observed_bytes": n, "error_type": type(error).__name__, "error": str(error)[:160]}
        write(evidence / (name + ".receipt.json"), result)
        print(row["Path"], result, flush=True)
        return result

    # Network download concurrency is independent of GPU reservations.
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(download, sorted(attempts, key=lambda x: x[0]["Size"])))
    if any(x["status"] != "verified" for x in results):
        raise SystemExit(1)
    write(evidence / "COMPLETE.json", {"revision": revision, "directory": str(DEST), "files": len(selected), "bytes": plan["expected_bytes"], "at": time.time()})


def file_hash(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b""):
            h.update(block)
    return h.hexdigest()


if __name__ == "__main__":
    main()
