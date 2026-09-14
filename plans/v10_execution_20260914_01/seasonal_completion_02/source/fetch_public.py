"""Bounded public captures with durable intent; no authentication or retries."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from http.client import HTTPException, IncompleteRead
import json
from pathlib import Path
import subprocess
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(path, value):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    tmp.replace(path)


def curl_fetch(spec):
    cap = spec["max_bytes"]
    raw = bytearray()
    with tempfile.TemporaryDirectory(prefix="monitoring-public-") as scratch:
        headers_path = Path(scratch) / "headers"
        with (Path(scratch) / "stderr").open("wb") as error_stream:
            command = ["curl", "--silent", "--show-error", "--http1.1", "--location",
                       "--proto", "=https", "--proto-redir", "=https", "--max-redirs", "3",
                       "--connect-timeout", "15", "--max-time", str(spec.get("timeout", 90)),
                       "--max-filesize", str(cap), "--dump-header", str(headers_path), spec["url"]]
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=error_stream)
            while len(raw) <= cap:
                chunk = process.stdout.read(min(65536, cap + 1 - len(raw)))
                if not chunk:
                    break
                raw.extend(chunk)
            if len(raw) > cap:
                process.kill()
            process.stdout.close()
            code = process.wait(timeout=10)
        headers, status = {}, None
        if headers_path.exists():
            for line in headers_path.read_text(errors="replace").splitlines():
                if line.startswith("HTTP/"):
                    headers = {}
                    status = int(line.split()[1])
                key, sep, value = line.partition(":")
                if sep and key.lower() in {"content-type", "content-length", "etag", "last-modified", "date"}:
                    headers[key.lower()] = value.strip()
        result = {"http_status": status, "curl_exit": code, "headers": headers,
                  "complete": code == 0 and status == 200 and len(raw) <= cap, "transport": "curl_http1.1"}
        if not result["complete"]:
            result["failure"] = "body_exceeds_cap" if len(raw) > cap else "curl_or_http_error"
        return raw, result


def fetch_batch(plan_path: Path, output: Path):
    plan_bytes = plan_path.read_bytes()
    plan = json.loads(plan_bytes)
    specs = plan["requests"]
    names = [s["id"] for s in specs]
    if len(names) != len(set(names)) or any(not n.replace("-", "").replace("_", "").isalnum() for n in names):
        raise ValueError("Invalid or duplicate capture IDs")
    if len(specs) > plan["limits"]["requests"]:
        raise ValueError("Request cap")
    # Reserve one overflow-detection byte for every request, including failures.
    reserved = sum(s["max_bytes"] + 1 for s in specs)
    if reserved > plan["limits"]["bytes"]:
        raise ValueError("Worst-case bytes exceed batch cap")
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "INTENT.json", {"started_at": now(), "plan_sha256": digest(plan_bytes),
               "limits": plan["limits"], "reserved_bytes": reserved, "attempts_per_request": 1,
               "source_sha256": digest(Path(__file__).read_bytes())})
    receipts = []
    for spec in specs:
        parsed = urlsplit(spec["url"])
        if parsed.scheme != "https" or parsed.hostname not in plan["allowed_hosts"] or parsed.username:
            raise ValueError("Public host not allowed")
        cap = spec["max_bytes"]
        receipt = dict(spec, started_at=now(), http_status=None, complete=False,
                       first_seen_is_historical=False, as_of_admission=False)
        write_json(output / (spec["id"] + ".intent.json"), receipt)
        raw = bytearray()
        if spec.get("transport", plan.get("transport")) == "curl":
            raw, fields = curl_fetch(spec)
            receipt.update(fields)
            receipt.update(bytes=len(raw), sha256=digest(raw), finished_at=now(), body_file=spec["id"] + ".body")
            (output / receipt["body_file"]).write_bytes(raw)
            write_json(output / (spec["id"] + ".json"), receipt)
            receipts.append(receipt)
            write_json(output / "MANIFEST.json", {"plan_sha256": digest(plan_bytes), "finished_at": now(),
                       "planned": len(specs), "attempted": len(receipts), "bytes": sum(r["bytes"] for r in receipts),
                       "rows": receipts})
            print(spec["id"], receipt["http_status"], len(raw), receipt["complete"], flush=True)
            time.sleep(plan.get("pause_seconds", 3))
            continue
        try:
            request = Request(spec["url"], headers={"User-Agent": "DisasterTrace-research-contact-sisuolv/1.0"})
            with urlopen(request, timeout=spec.get("timeout", 90)) as response:
                final = urlsplit(response.url)
                if final.scheme != "https" or final.hostname not in plan["allowed_hosts"]:
                    raise ValueError("Redirect outside public allowlist")
                receipt["http_status"] = response.status
                receipt["headers"] = {key.lower(): response.headers[key] for key in
                    ("Content-Type", "Content-Length", "ETag", "Last-Modified", "Date") if key in response.headers}
                while len(raw) <= cap:
                    try:
                        chunk = response.read(min(65536, cap + 1 - len(raw)))
                    except IncompleteRead as exc:
                        raw.extend(exc.partial)
                        raise
                    if not chunk:
                        receipt["complete"] = response.status == 200
                        break
                    raw.extend(chunk)
                if len(raw) > cap:
                    receipt.update(complete=False, failure="body_exceeds_cap")
        except HTTPError as exc:
            receipt.update(http_status=exc.code, failure="http_error")
        except (URLError, TimeoutError, OSError, HTTPException) as exc:
            receipt.update(failure=type(exc).__name__)
        receipt.update(bytes=len(raw), sha256=digest(raw), finished_at=now(), body_file=spec["id"] + ".body")
        (output / receipt["body_file"]).write_bytes(raw)
        write_json(output / (spec["id"] + ".json"), receipt)
        receipts.append(receipt)
        write_json(output / "MANIFEST.json", {"plan_sha256": digest(plan_bytes), "finished_at": now(),
                   "planned": len(specs), "attempted": len(receipts), "bytes": sum(r["bytes"] for r in receipts),
                   "rows": receipts})
        print(spec["id"], receipt["http_status"], len(raw), receipt["complete"], flush=True)
        time.sleep(plan.get("pause_seconds", 3))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    fetch_batch(args.plan, args.output)
