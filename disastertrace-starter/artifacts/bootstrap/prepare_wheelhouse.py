"""Resolve recorded wheels on official PyPI and fetch missing byte ranges."""

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import re
import shutil
import time
import urllib.request
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parent
WHEELS = ROOT / "wheels"
PARTS = WHEELS / "remaining_parts"
PARTS.mkdir(exist_ok=True)
filenames = set(json.loads((ROOT / "runtime_timeout.json").read_text())["resolved_wheels"])
cache_by_hash = {}
started = time.monotonic()
for path in [*Path("/root/.cache/pip").rglob("*.body"), *WHEELS.glob("*.whl")]:
    with path.open("rb") as stream:
        if stream.read(2) != b"PK":
            continue
    with ZipFile(path) as archive:
        metadata_path = next((name for name in archive.namelist()
                              if name.endswith(".dist-info/METADATA")), None)
        if metadata_path is None:
            continue
        package_version = metadata_path.split(".dist-info/")[0]
        if package_version.startswith(("hatchling-", "editables-", "trove_classifiers-")):
            filenames.add(package_version + "-py3-none-any.whl")
    cache_by_hash[hashlib.sha256(path.read_bytes()).hexdigest()] = path


def metadata_for(filename):
    package, version = filename.split("-")[:2]
    with urllib.request.urlopen(f"https://pypi.org/pypi/{package}/{version}/json", timeout=20) as response:
        metadata = json.load(response)
    wheel = next(item for item in metadata["urls"] if item["filename"] == filename)
    return {"filename": filename, "url": wheel["url"], "size": wheel["size"],
            "sha256": wheel["digests"]["sha256"]}


with ThreadPoolExecutor(max_workers=8) as executor:
    manifest = list(executor.map(metadata_for, sorted(filenames)))
(ROOT / "wheelhouse_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
tasks = []
cached = []
for item in manifest:
    source = cache_by_hash.get(item["sha256"])
    if source is not None:
        destination = WHEELS / item["filename"]
        if source.resolve() != destination.resolve():
            shutil.copyfile(source, destination)
        cached.append(item["filename"])
        continue
    for start in range(0, item["size"], 256 * 1024):
        tasks.append((item, start, min(start + 256 * 1024, item["size"]) - 1))
print(f"Official metadata verified: {len(manifest)} wheels; cached: {len(cached)}; ranges: {len(tasks)}",
      flush=True)


def fetch(task):
    item, start, end = task
    destination = PARTS / f"{item['filename']}.{start}-{end}"
    for attempt in range(2):
        try:
            request = urllib.request.Request(item["url"], headers={"Range": f"bytes={start}-{end}"})
            with urllib.request.urlopen(request, timeout=30) as response:
                if response.status != 206 or response.headers.get("Content-Range") != (
                    f"bytes {start}-{end}/{item['size']}"
                ):
                    raise ValueError("Unexpected byte range response")
                data = response.read(end - start + 2)
            if len(data) != end - start + 1:
                raise ValueError("Incomplete byte range")
            destination.write_bytes(data)
            return item["filename"], start, destination
        except Exception:
            if attempt == 1:
                raise


parts = []
with ThreadPoolExecutor(max_workers=8) as executor:
    futures = [executor.submit(fetch, task) for task in tasks]
    for future in as_completed(futures):
        parts.append(future.result())
        print(f"range completed {len(parts)}/{len(tasks)}", flush=True)

for item in manifest:
    destination = WHEELS / item["filename"]
    if item["filename"] not in cached:
        with destination.open("wb") as output:
            for _, _, path in sorted(part for part in parts if part[0] == item["filename"]):
                output.write(path.read_bytes())
    if (destination.stat().st_size != item["size"]
            or hashlib.sha256(destination.read_bytes()).hexdigest() != item["sha256"]):
        destination.rename(destination.with_suffix(".whl.invalid"))
        raise ValueError(f"Wheel hash mismatch: {item['filename']}")

result = {"verified_wheels": len(manifest), "cached_wheels": len(cached),
          "range_requests": len(tasks), "elapsed_seconds": round(time.monotonic() - started, 2)}
(ROOT / "wheelhouse_verification.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
