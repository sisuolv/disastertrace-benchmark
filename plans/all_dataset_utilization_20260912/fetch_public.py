"""Bounded, receipt-producing source checks; HTTP success is not scientific admission."""

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent


def now():
    return datetime.now(timezone.utc).isoformat()


def public_url(url):
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.hostname or "", parsed.path, "", ""))


def fetch(spec, output):
    ident = spec["id"]
    if not re.fullmatch(r"[A-Za-z0-9_-]+", ident):
        raise ValueError("Invalid capture identifier")
    url = spec["url"]
    if urlsplit(url).scheme != "https":
        raise ValueError("HTTPS required")
    receipt = dict(spec, started_at=now())
    token = ""
    if spec.get("earthdata"):
        if not (urlsplit(url).hostname or "").endswith(".nasa.gov"):
            raise ValueError("Earthdata credential only permitted at NASA hosts")
        token = (
            Path("/mnt/afs/260010168/.config/disastertrace/earthdata-token")
            .read_text()
            .strip()
        )
    cap = spec.get("max_bytes", 4 * 1024 * 1024)
    with tempfile.TemporaryDirectory(prefix="source-sample-") as temporary:
        scratch = Path(temporary)
        command = [
            "curl",
            "--http1.1",
            "--silent",
            "--show-error",
            "--location",
            "--globoff",
            "--proto",
            "=https",
            "--proto-redir",
            "=https",
            "--max-redirs",
            "5",
            "--connect-timeout",
            "10",
            "--max-time",
            str(spec.get("timeout", 60)),
            "--max-filesize",
            str(cap),
            "--output",
            str(scratch / "body"),
            "--dump-header",
            str(scratch / "headers"),
            "--write-out",
            "%{http_code}\n%{url_effective}",
        ]
        if spec.get("range"):
            command += ["--range", spec["range"]]
        if spec.get("proxy"):
            command += ["--proxy", "http://127.0.0.1:17890"]
        if token:
            command += ["--header", "@-"]
        command.append(url)
        try:
            run = subprocess.run(
                command,
                input=("Authorization: Bearer " + token + "\n").encode()
                if token
                else b"",
                capture_output=True,
                timeout=spec.get("timeout", 60) + 10,
                check=False,
            )
            lines = run.stdout.decode(errors="replace").splitlines()
            receipt.update(
                curl_exit=run.returncode, http_status=int(lines[0]) if lines else 0
            )
            if len(lines) > 1:
                receipt["final_url_without_query"] = public_url(lines[1])
        except subprocess.TimeoutExpired:
            receipt.update(curl_exit=28, http_status=0)
        raw = (scratch / "body").read_bytes() if (scratch / "body").exists() else b""
        if len(raw) > cap:
            raw = raw[:cap]
            receipt["locally_truncated"] = True
        if token and token.encode() in raw:
            raise ValueError("Credential echo detected; refusing artifact")
        headers = {}
        if (scratch / "headers").exists():
            for line in (scratch / "headers").read_text(errors="replace").splitlines():
                if line.startswith("HTTP/"):
                    headers = {}
                key, sep, value = line.partition(":")
                if sep and key.lower() in {
                    "content-type",
                    "content-length",
                    "content-range",
                    "etag",
                    "last-modified",
                }:
                    headers[key.lower()] = value.strip()
        receipt.update(
            bytes=len(raw),
            sha256=hashlib.sha256(raw).hexdigest(),
            response_headers=headers,
            body_file=ident + ".body",
            finished_at=now(),
            scientific_validation=False,
        )
        (output / (ident + ".body")).write_bytes(raw)
        serialized = json.dumps(receipt, indent=2, ensure_ascii=True) + "\n"
        if token and token in serialized:
            raise ValueError("Credential echo detected in receipt")
        (output / (ident + ".json")).write_text(serialized)
    return receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("spec", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    specs = json.loads(args.spec.read_text())
    if len({s["id"] for s in specs}) != len(specs):
        raise ValueError("Duplicate capture IDs")
    args.output.mkdir(parents=True, exist_ok=False)
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(lambda s: fetch(s, args.output), specs))
    report = {
        "finished_at": now(),
        "requests": len(rows),
        "bytes": sum(r["bytes"] for r in rows),
        "rows": rows,
    }
    (args.output / "MANIFEST.json").write_text(json.dumps(report, indent=2) + "\n")
    for row in rows:
        print(row["id"], row["http_status"], row["curl_exit"], row["bytes"])


if __name__ == "__main__":
    main()
