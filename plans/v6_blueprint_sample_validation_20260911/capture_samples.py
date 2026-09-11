"""Capture bounded public samples; preserve failures and exact response bytes."""

import argparse
import hashlib
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent


def stamp():
    return datetime.now(timezone.utc).isoformat()


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.skip += 1
        if tag == "a":
            self.links.extend(v for k, v in attrs if k == "href")
        if tag in {"p", "div", "li", "tr", "h1", "h2", "h3", "br"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def capture(spec, output, intent):
    record = {**spec, "started_at": stamp(), "complete": False, "status": "failed"}
    body = bytearray()
    start = time.monotonic()
    headers = {"User-Agent": "DisasterTrace-data-feasibility/1.0", "Accept-Encoding": "identity"}
    headers.update(spec.get("headers", {}))
    payload = None
    if "json_body" in spec:
        payload = json.dumps(spec["json_body"]).encode()
        headers["Content-Type"] = "application/json"
    try:
        try:
            response = urlopen(
                Request(spec["url"], data=payload, headers=headers, method=spec.get("method", "GET")),
                timeout=intent["socket_timeout_seconds"],
            )
        except HTTPError as exc:
            response = exc
        with response:
            record.update(http_status=response.status, final_url=response.geturl())
            record["response_headers"] = {
                k: response.headers[k] for k in (
                    "Content-Type", "Content-Length", "Content-Range", "Content-Encoding",
                    "ETag", "Last-Modified", "Accept-Ranges"
                ) if response.headers.get(k) is not None
            }
            while len(body) <= spec["max_bytes"]:
                if time.monotonic() - start > intent["wall_time_per_response_seconds"]:
                    raise TimeoutError("response wall-time budget reached")
                chunk = response.read(min(65536, spec["max_bytes"] + 1 - len(body)))
                if not chunk:
                    record["complete"] = True
                    break
                body.extend(chunk)
        if len(body) > spec["max_bytes"]:
            del body[spec["max_bytes"]:]
            record["complete"] = False
            record["reason"] = "response_body_cap"
        if "Range" in headers:
            wanted = re.fullmatch(r"bytes=(\d+)-(\d+)", headers["Range"])
            got = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+|\*)", record["response_headers"].get("Content-Range", ""))
            record["range_verified"] = bool(
                wanted and got and record["http_status"] == 206
                and wanted.groups() == got.groups()[:2]
                and len(body) == int(wanted[2]) - int(wanted[1]) + 1
            )
        record["status"] = "received" if (
            record["complete"] and record["http_status"] in {200, 206}
            and record.get("range_verified", True)
        ) else "incomplete_or_http_error"
    except Exception as exc:
        record["error"] = type(exc).__name__ + ": " + str(exc)
    if body or "http_status" in record:
        raw = output / (spec["id"] + ".body")
        raw.write_bytes(body)
        record.update(raw=raw.name, bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
        content_type = record.get("response_headers", {}).get("Content-Type", "")
        if any(s in content_type for s in ("text/", "json", "xml")):
            text = body.decode("utf-8", errors="replace")
            if "html" in content_type:
                page = Page()
                page.feed(text)
                record["links"] = sorted(set(page.links))
                text = "\n".join(" ".join(line.split()) for line in "".join(page.parts).splitlines() if line.strip())
            (output / (spec["id"] + ".txt")).write_text(text)
    record["finished_at"] = stamp()
    (output / (spec["id"] + ".json")).write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    intent = json.loads((ROOT / "PROBE_INTENT.json").read_text())
    specs = json.loads(args.spec.read_text())
    if len({s["id"] for s in specs}) != len(specs):
        raise ValueError("duplicate capture IDs")
    for spec in specs:
        if not re.fullmatch(r"[a-z0-9_-]+", spec["id"]):
            raise ValueError("unsafe capture ID")
        if not 0 < spec["max_bytes"] <= intent["max_single_response_bytes"]:
            raise ValueError("invalid individual response cap")
        if set(spec.get("headers", {})) - {"Range", "Accept", "User-Agent"}:
            raise ValueError("only public, nonsensitive request headers allowed")
        if spec.get("method", "GET") not in {"GET", "POST"}:
            raise ValueError("unsupported sample request method")
    prior = []
    for path in ROOT.glob("captures_*/SPEC.json"):
        prior.extend(json.loads(path.read_text()))
    if len(prior) + len(specs) > intent["max_requests"]:
        raise ValueError("aggregate request budget exceeded")
    if sum(s["max_bytes"] for s in prior + specs) > intent["max_response_caps_sum_bytes"]:
        raise ValueError("aggregate response-cap budget exceeded")
    args.out.mkdir(exist_ok=False)
    (args.out / "SPEC.json").write_text(json.dumps(specs, ensure_ascii=False, indent=2) + "\n")
    records = []
    with ThreadPoolExecutor(max_workers=intent["concurrency"]) as executor:
        futures = [executor.submit(capture, s, args.out, intent) for s in specs]
        for future in as_completed(futures):
            record = future.result()
            records.append(record)
            print(json.dumps({k: record[k] for k in ("id", "status", "http_status", "bytes", "error") if k in record}), flush=True)
    (args.out / "MANIFEST.json").write_text(json.dumps(sorted(records, key=lambda r: r["id"]), ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
