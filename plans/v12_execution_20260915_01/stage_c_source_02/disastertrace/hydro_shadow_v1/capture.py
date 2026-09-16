"""Bounded public HTTP capture, retaining incomplete bodies and exclusive receipts."""

import hashlib
import http.client
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def stamp():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write_new(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def strict_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key: " + key)
            result[key] = value
        return result

    def invalid(value):
        raise ValueError("nonfinite JSON constant: " + value)

    return json.loads(data, object_pairs_hook=pairs, parse_constant=invalid)


def capture_json(url, destination, max_bytes=4 * 1024 * 1024, timeout=25):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    record = {
        "url": url,
        "started_at": stamp(),
        "status": "failed",
        "complete": False,
        "max_bytes": max_bytes,
        "http_status": None,
        "automatic_retries": 0,
    }
    raw = destination / "response.raw"
    started = time.monotonic()
    size, result = 0, None
    try:
        request = Request(
            url,
            headers={
                "User-Agent": "DisasterTrace-shadow-research/1.0",
                "Accept": "application/json",
                "Accept-Encoding": "identity",
            },
        )
        try:
            response = urlopen(request, timeout=timeout)
        except HTTPError as exc:
            response = exc
        with response, raw.open("xb") as stream:
            record.update(
                http_status=response.status,
                final_url=response.geturl(),
                content_type=response.headers.get("Content-Type"),
                response_date=response.headers.get("Date"),
            )
            while size <= max_bytes:
                chunk = response.read(min(65536, max_bytes + 1 - size))
                if not chunk:
                    record["complete"] = True
                    break
                stream.write(chunk)
                size += len(chunk)
                if time.monotonic() - started > 60:
                    raise TimeoutError("total read duration exceeded")
            if size > max_bytes:
                raise ValueError("body byte cap exceeded")
        if record["http_status"] != 200:
            raise ValueError("HTTP status " + str(record["http_status"]))
        if not record["complete"]:
            raise ValueError("incomplete body")
        result = strict_json(raw.read_bytes())
        record["status"] = "received"
    except (OSError, ValueError, http.client.HTTPException) as exc:
        record["error"] = type(exc).__name__ + ": " + str(exc)
    record.update(
        finished_at=stamp(),
        seconds=time.monotonic() - started,
        bytes=raw.stat().st_size if raw.exists() else 0,
        sha256=file_hash(raw) if raw.exists() else None,
    )
    write_new(destination / "RECEIPT.json", record)
    return result, record
