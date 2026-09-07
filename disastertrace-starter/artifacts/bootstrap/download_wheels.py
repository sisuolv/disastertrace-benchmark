"""Bounded parallel range downloads, verified against official PyPI hashes."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import urllib.request


ROOT = Path(__file__).resolve().parent
MANIFEST = json.loads((ROOT / "parallel_download_manifest.json").read_text())
WHEELS = ROOT / "wheels"
PARTS = WHEELS / "parts"
PARTS.mkdir(parents=True, exist_ok=True)
START = time.monotonic()
tasks = []
prefixes = {}
chunk_bytes = 512 * 1024

for item in MANIFEST:
    prefix_path = PARTS / (item["filename"] + ".prefix")
    cached = Path("/tmp/pip-unpack-8di3oy0n") / item["filename"]
    prefix_size = min(cached.stat().st_size, item["size"]) if cached.exists() else 0
    if prefix_size:
        with cached.open("rb") as source:
            prefix_path.write_bytes(source.read(prefix_size))
        prefix_size = prefix_path.stat().st_size
    prefixes[item["filename"]] = (prefix_path, prefix_size)
    for start in range(prefix_size, item["size"], chunk_bytes):
        tasks.append((item, start, min(start + chunk_bytes, item["size"]) - 1))


def fetch(task):
    item, start, end = task
    target = PARTS / f"{item['filename']}.{start}-{end}"
    expected_length = end - start + 1
    request = urllib.request.Request(item["url"], headers={"Range": f"bytes={start}-{end}"})
    for attempt in range(2):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                expected_range = f"bytes {start}-{end}/{item['size']}"
                if response.status != 206 or response.headers.get("Content-Range") != expected_range:
                    raise ValueError("Range response does not match requested byte interval")
                data = response.read(expected_length + 1)
                if len(data) != expected_length:
                    raise ValueError("Partial range response")
            target.write_bytes(data)
            return {"filename": item["filename"], "start": start, "end": end, "path": str(target)}
        except Exception:
            if attempt == 1:
                raise


results = []
with ThreadPoolExecutor(max_workers=8) as executor:
    futures = [executor.submit(fetch, task) for task in tasks]
    for future in as_completed(futures):
        results.append(future.result())
        print(f"verified range responses: {len(results)}/{len(tasks)}", flush=True)

verified = []
for item in MANIFEST:
    target = WHEELS / item["filename"]
    prefix, size = prefixes[item["filename"]]
    with target.open("wb") as output:
        if size:
            output.write(prefix.read_bytes())
        for part in sorted((p for p in results if p["filename"] == item["filename"]),
                           key=lambda p: p["start"]):
            output.write(Path(part["path"]).read_bytes())
    observed = hashlib.sha256(target.read_bytes()).hexdigest()
    if target.stat().st_size != item["size"] or observed != item["sha256"]:
        target.rename(target.with_suffix(".whl.invalid"))
        raise ValueError(f"Final wheel hash/length mismatch: {item['filename']}")
    verified.append({"filename": target.name, "bytes": target.stat().st_size,
                     "sha256": observed, "verified_against": "official PyPI JSON metadata"})

report = {"finished_at": datetime.now(timezone.utc).isoformat(),
          "elapsed_seconds": round(time.monotonic() - START, 2),
          "parallel_workers": 8, "range_requests": len(results), "verified_wheels": verified}
(ROOT / "parallel_download_result.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
