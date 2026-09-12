"""Capture bounded public samples with per-host serialization and saved failures."""

import argparse
import fcntl
import hashlib
import importlib.util
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "public_capture", ROOT / "fetch_public.py"
)
CAPTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CAPTURE)


def fetch_one(row, output):
    locks = ROOT / ".download_locks"
    locks.mkdir(exist_ok=True)
    host_key = hashlib.sha256(urlsplit(row["url"]).hostname.encode()).hexdigest()
    with (locks / (host_key + ".lock")).open("a") as host:
        fcntl.flock(host, fcntl.LOCK_EX)
        slot = None
        while slot is None:
            for number in range(4):
                candidate = (locks / f"slot-{number}.lock").open("a")
                try:
                    fcntl.flock(candidate, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    slot = candidate
                    break
                except BlockingIOError:
                    candidate.close()
            if slot is None:
                time.sleep(0.25)
        try:
            return CAPTURE.fetch(row, output)
        finally:
            slot.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    rows = json.loads(args.spec.read_text())
    if len({r["id"] for r in rows}) != len(rows):
        raise ValueError("Repeated capture IDs")
    # Count dispatched specifications too, including batches still in flight.
    reserved = []
    for output in ROOT.glob("captures_*"):
        plan = ROOT / ("SPEC_" + output.name.rsplit("_", 1)[1] + ".json")
        if plan.exists():
            reserved.extend(json.loads(plan.read_text()))
    if len(reserved) + len(rows) > 160:
        raise ValueError("Request budget exceeded")
    if sum(r.get("max_bytes", 4194304) for r in reserved + rows) > 2 * 1024**3:
        raise ValueError("Conservative response budget exceeded")
    args.output.mkdir(parents=True, exist_ok=False)
    locks = {urlsplit(r["url"]).hostname: threading.Lock() for r in rows}

    def one(row):
        with locks[urlsplit(row["url"]).hostname]:
            receipt = fetch_one(row, args.output)
            time.sleep(0.5)
        print(
            receipt["id"],
            receipt["http_status"],
            receipt["curl_exit"],
            receipt["bytes"],
            flush=True,
        )
        return receipt

    with ThreadPoolExecutor(max_workers=4) as pool:
        receipts = list(pool.map(one, rows))
    report = {
        "finished_at": CAPTURE.now(),
        "requests": len(receipts),
        "bytes": sum(r["bytes"] for r in receipts),
        "rows": receipts,
        "per_host_parallelism": 1,
        "total_parallelism": 4,
    }
    (args.output / "MANIFEST.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
