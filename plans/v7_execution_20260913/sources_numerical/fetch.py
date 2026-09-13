"""Bounded, receipt-producing source fetcher for numerical admission probes."""
import datetime as dt
import hashlib
import http.client
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def fetch(url, name, cap=20_000_000, headers=None):
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    receipt = {"url": url, "name": name, "started_utc": started, "cap": cap}
    request = urllib.request.Request(url, headers=headers or {"User-Agent": "DisasterTrace-research-source-probe/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            receipt.update(status=response.status, final_url=response.url,
                           headers=dict(response.headers))
            length = response.headers.get("Content-Length")
            if length and int(length) > cap:
                raise ValueError(f"declared size {length} exceeds cap {cap}")
            data = response.read(cap + 1)
            if len(data) > cap:
                raise ValueError("stream exceeds cap")
            output = ROOT / "raw" / name
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(data)
            receipt.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), local=str(output.relative_to(ROOT)))
            if length and len(data) != int(length):
                raise ValueError(f"short response: received {len(data)} of {length} bytes")
    except (OSError, ValueError, http.client.HTTPException) as exc:
        receipt.update(error=f"{type(exc).__name__}: {exc}")
        if isinstance(exc, urllib.error.HTTPError):
            receipt["status"] = exc.code
    receipt["finished_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    with (ROOT / "REQUESTS.jsonl").open("a") as f:
        f.write(json.dumps(receipt, sort_keys=True) + "\n")
    print(json.dumps({k: receipt[k] for k in ("name", "status", "bytes", "error") if k in receipt}))
    return receipt


if __name__ == "__main__":
    result = fetch(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 20_000_000)
    if "error" in result:
        sys.exit(1)
