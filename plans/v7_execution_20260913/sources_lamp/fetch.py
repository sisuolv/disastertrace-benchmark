"""Bounded source capture; persist both successful and failed HTTP receipts."""

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

import requests


def capture(name, url, limit=20_000_000, byte_range=None):
    root = Path(__file__).resolve().parent
    destination = root / "raw" / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError("use a fresh capture name; existing evidence is immutable")
    receipt = {
        "url": url,
        "requested_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "max_bytes": limit,
        "path": str(destination.relative_to(root)),
        "requested_range": byte_range,
    }
    body = bytearray()
    try:
        headers = {"Range": byte_range} if byte_range else {}
        with requests.get(url, timeout=(20, 90), stream=True, headers=headers) as response:
            receipt.update(
                status_code=response.status_code,
                final_url=response.url,
                headers={
                    key: response.headers[key]
                    for key in ("Content-Type", "Content-Length", "Content-Range", "Last-Modified", "Date", "ETag")
                    if key in response.headers
                },
            )
            for chunk in response.iter_content(65536):
                if len(body) + len(chunk) > limit:
                    raise ValueError("bounded download byte limit exceeded")
                body.extend(chunk)
            receipt["body_complete"] = True
    except (requests.RequestException, ValueError, OSError) as error:
        receipt.update(error=str(error), body_complete=False)
    destination.write_bytes(body)
    receipt.update(
        bytes=len(body),
        sha256=hashlib.sha256(body).hexdigest(),
        completed_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
    )
    destination.with_name(destination.name + ".receipt.json").write_text(
        json.dumps(receipt, indent=2) + "\n"
    )
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("url")
    parser.add_argument("--limit", type=int, default=20_000_000)
    parser.add_argument("--range")
    arguments = parser.parse_args()
    print(json.dumps(capture(arguments.name, arguments.url, arguments.limit, arguments.range), indent=2))
