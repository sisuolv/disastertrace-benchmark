"""Capture bounded public references for the active-warning design review."""

import argparse
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class PageText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.links = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.skip += 1
        if tag == "a":
            self.links.extend(v for k, v in attrs if k == "href")
        if tag in {"p", "div", "section", "li", "tr", "h1", "h2", "h3", "br"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def stamp():
    return datetime.now(timezone.utc).isoformat()


def capture(spec, root):
    name = spec["id"]
    if not name or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for c in name):
        raise ValueError("invalid reference ID")
    record = {**spec, "started_at": stamp(), "status": "failed"}
    limit = spec.get("max_bytes", 8 * 1024 * 1024)
    request = Request(spec["url"], headers={"User-Agent": "DisasterTrace-research-review/1.0"})
    try:
        try:
            response = urlopen(request, timeout=25)
        except HTTPError as exc:
            response = exc
        with response:
            body = response.read(limit + 1)
            record.update(
                http_status=response.status,
                final_url=response.geturl(),
                content_type=response.headers.get("Content-Type", ""),
            )
        complete = len(body) <= limit
        body = body[:limit]
        raw = root / (name + (".raw" if complete else ".partial"))
        raw.write_bytes(body)
        record.update(
            complete=complete,
            bytes=len(body),
            sha256=hashlib.sha256(body).hexdigest(),
            raw=raw.name,
            status="received" if record["http_status"] == 200 and complete else "incomplete_or_http_error",
        )
        if record["content_type"].startswith("image/") or "pdf" in record["content_type"]:
            record["finished_at"] = stamp()
            (root / (name + ".json")).write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return record
        decoded = body.decode("utf-8", errors="replace")
        if "html" in record["content_type"]:
            parser = PageText()
            parser.feed(decoded)
            decoded = "\n".join(" ".join(line.split()) for line in "".join(parser.parts).splitlines() if line.strip())
            record["links"] = sorted(set(parser.links))
        (root / (name + ".txt")).write_text(decoded, encoding="utf-8")
    except Exception as exc:
        record["error"] = type(exc).__name__ + ": " + str(exc)
    record["finished_at"] = stamp()
    (root / (name + ".json")).write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    specs = json.loads(args.spec.read_text())
    if len({s["id"] for s in specs}) != len(specs):
        raise ValueError("duplicate IDs")
    args.out.mkdir(parents=True, exist_ok=False)
    records = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(capture, spec, args.out) for spec in specs]
        for future in as_completed(futures):
            record = future.result()
            records.append(record)
            print(json.dumps({k: record[k] for k in ("id", "status", "http_status", "bytes", "error") if k in record}), flush=True)
    (args.out / "MANIFEST.json").write_text(json.dumps(sorted(records, key=lambda r: r["id"]), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
