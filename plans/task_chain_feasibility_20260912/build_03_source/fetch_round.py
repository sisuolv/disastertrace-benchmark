"""Use saved bounded capture code, limiting each remote host to one request."""

import argparse
import importlib.util
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
CAPTURE = ROOT.parent / "all_candidate_data_validation_20260912/fetch_samples.py"
spec = importlib.util.spec_from_file_location("chain_source_capture", CAPTURE)
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    rows = json.loads(args.spec.read_text())
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("Duplicate capture IDs")
    prior = [
        json.loads(path.read_text()) for path in ROOT.glob("captures_*/MANIFEST.json")
    ]
    if sum(item["requests"] for item in prior) + len(rows) > 120:
        raise ValueError("Initial logical request budget exceeded")
    if (
        sum(item["bytes"] for item in prior)
        + sum(row.get("max_bytes", 4 * 1024 * 1024) for row in rows)
        > 512 * 1024 * 1024
    ):
        raise ValueError("Initial conservative byte budget exceeded")
    args.output.mkdir(parents=True, exist_ok=False)
    locks = {urlsplit(row["url"]).hostname: threading.Lock() for row in rows}

    def one(row):
        host = urlsplit(row["url"]).hostname
        with locks[host]:
            result = capture.fetch(row, args.output)
            if host == "mesonet.agron.iastate.edu":
                time.sleep(3)
        print(
            result["id"],
            result["http_status"],
            result["curl_exit"],
            result["bytes"],
            flush=True,
        )
        return result

    with ThreadPoolExecutor(max_workers=4) as pool:
        receipts = list(pool.map(one, rows))
    report = dict(
        finished_at=capture.now(),
        requests=len(receipts),
        bytes=sum(row["bytes"] for row in receipts),
        rows=receipts,
        per_host_parallelism=1,
        total_parallelism=4,
    )
    (args.output / "MANIFEST.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
