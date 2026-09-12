"""Fetch bounded authorized xBD data without recording signed URLs in artifacts."""

import argparse
import hashlib
import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit, urlunsplit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--links", type=Path, required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--range")
    parser.add_argument("--max-bytes", type=int, default=1048576)
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--proxy", action="store_true")
    args = parser.parse_args()
    url = json.loads(args.links.read_text())[args.key]
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "download.xview2.org"
        or any(c in url for c in '\r\n"')
    ):
        raise ValueError("Unexpected xBD URL")
    args.output.mkdir(parents=True, exist_ok=False)
    started = datetime.now(timezone.utc).isoformat()
    command = [
        "curl",
        "--silent",
        "--show-error",
        "--location",
        "--http1.1",
        "--proto",
        "=https",
        "--proto-redir",
        "=https",
        "--connect-timeout",
        "10",
        "--max-time",
        str(args.timeout),
        "--max-filesize",
        str(args.max_bytes),
        "--output",
        str(args.output / "response.body"),
        "--write-out",
        "%{http_code}",
        "--config",
        "-",
    ]
    if args.range:
        command += ["--range", args.range]
    if args.proxy:
        command += ["--proxy", "http://127.0.0.1:17890"]
    headers = {}
    with tempfile.TemporaryDirectory(prefix="xbd-headers-") as temporary:
        header_path = Path(temporary) / "headers"
        command += ["--dump-header", str(header_path)]
        run = subprocess.run(
            command,
            input=('url = "' + url + '"\n').encode(),
            capture_output=True,
            check=False,
        )
        if header_path.exists():
            for line in header_path.read_text(errors="replace").splitlines():
                if line.startswith("HTTP/"):
                    headers = {}
                key, sep, value = line.partition(":")
                if sep and key.lower() in {
                    "content-range",
                    "content-length",
                    "etag",
                    "last-modified",
                    "content-type",
                }:
                    headers[key.lower()] = value.strip()
    path = args.output / "response.body"
    body = path.read_bytes() if path.exists() else b""
    query = parse_qs(parsed.query)
    if any(
        value.encode() in body
        for value in query.get("Signature", []) + query.get("Key-Pair-Id", [])
    ):
        raise ValueError(
            "Response echoes private authorization; retain locally without reporting"
        )
    receipt = {
        "source_id": "D44",
        "url_without_query": urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, "", "")
        ),
        "signed_link_expiry_utc": datetime.fromtimestamp(
            int(query["Expires"][0]), timezone.utc
        ).isoformat()
        if "Expires" in query
        else None,
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "http_status": int(run.stdout.decode().strip() or "0"),
        "curl_exit": run.returncode,
        "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
        "range": args.range,
        "max_bytes": args.max_bytes,
        "signed_query_saved": False,
        "response_headers": headers,
        "error_mentions_expiry": b"expired" in body.lower(),
        "scientific_sample_verified": False,
    }
    (args.output / "RECEIPT.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt))
    return 0 if receipt["http_status"] in [200, 206] and run.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
