"""Capture bounded public literature and code references for the overall plan."""

import argparse
import hashlib
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit


def fetch(item, root):
    url = item["url"]
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.username or parsed.password:
        raise ValueError("Expected public HTTPS reference")
    output = root / item["id"]
    output.mkdir(parents=True, exist_ok=False)
    started = datetime.now(timezone.utc).isoformat()
    run = subprocess.run(
        ["curl", "--silent", "--show-error", "--location", "--proto", "=https",
         "--proto-redir", "=https", "--connect-timeout", "10", "--max-time", "25",
         "--max-filesize", "2097152", "--user-agent", "DisasterTrace-reference-review/1.0",
         "--output", str(output / "response.body"), "--write-out", "%{http_code}", url],
        capture_output=True, check=False,
    )
    path = output / "response.body"
    body = path.read_bytes() if path.exists() else b""
    receipt = {
        **item, "started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(),
        "http_status": int(run.stdout.decode().strip() or "0"), "curl_exit": run.returncode,
        "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(),
        "is_scientific_dataset_download": False, "reference_content_reviewed": False,
    }
    (output / "RECEIPT.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return {key: receipt[key] for key in ["id", "http_status", "curl_exit", "bytes"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    items = json.loads(args.spec.read_text())
    if len({item["id"] for item in items}) != len(items):
        raise ValueError("Duplicate reference IDs")
    args.output.mkdir(parents=True, exist_ok=False)
    with ThreadPoolExecutor(max_workers=4) as pool:
        for result in pool.map(lambda item: fetch(item, args.output), items):
            print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
