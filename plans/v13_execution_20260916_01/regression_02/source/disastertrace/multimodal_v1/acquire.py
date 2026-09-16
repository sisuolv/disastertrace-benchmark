"""Bounded official-source downloads with immutable receipts and safe ZIP reads."""

import fcntl
import io
import os
import stat
import urllib.error
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

from .storage import digest, now, read, write

HOSTS = {"ftp.nhc.noaa.gov", "www.nhc.noaa.gov", "www.weather.gov"}


def check_url(url):
    value = urlsplit(url)
    if (
        value.scheme != "https"
        or value.hostname not in HOSTS
        or value.port not in (None, 443)
        or value.username
        or value.password
    ):
        raise ValueError("source URL outside official HTTPS allowlist")


class OfficialRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        check_url(newurl)
        return super().redirect_request(request, fp, code, msg, headers, newurl)


def zip_members(data, max_expanded=64 * 1024 * 1024):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        if len(entries) > 256 or sum(x.file_size for x in entries) > max_expanded:
            raise ValueError("ZIP expansion budget exceeded")
        names = set()
        for entry in entries:
            path = PurePosixPath(entry.filename)
            if (
                path.is_absolute()
                or ".." in path.parts
                or "\\" in entry.filename
                or ":" in entry.filename
                or entry.filename in names
                or stat.S_ISLNK(entry.external_attr >> 16)
                or entry.file_size > max(1, entry.compress_size) * 500
            ):
                raise ValueError("unsafe ZIP member")
            names.add(entry.filename)
        return {entry.filename: archive.read(entry) for entry in entries if not entry.is_dir()}


class Fetcher:
    def __init__(self, root, total_limit=512 * 1024 * 1024, file_limit=256 * 1024 * 1024):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.total_limit = total_limit
        self.file_limit = file_limit

    def fetch(self, url, kind):
        check_url(url)
        if kind not in {"zip", "html", "text"}:
            raise ValueError("unsupported source kind")
        with (self.root / "download.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            return self._fetch(url, kind)

    def _fetch(self, url, kind):
        existing = sorted(self.root.glob("*/intent.json"))
        spent, matching = 0, []
        for intent_path in existing:
            intent = read(intent_path)
            receipt_path = intent_path.parent / "receipt.json"
            if receipt_path.exists():
                receipt = read(receipt_path)
                spent += receipt.get("budget_charged_bytes", receipt["bytes_received"])
                if intent["url"] == url and receipt["status"] == "received":
                    raw = intent_path.parent / "body"
                    if digest(raw.read_bytes()) != receipt["sha256"] or receipt["kind"] != kind:
                        raise ValueError("cached source identity differs")
                    return raw, receipt
            else:
                # An interrupted read retains its entire reservation, never a free retry.
                spent += intent["reserved_bytes"]
            if intent["url"] == url:
                matching.append(intent)
        if len(matching) >= 3:
            raise ValueError("download attempt cap reached")
        allowance = min(self.file_limit, self.total_limit - spent)
        if allowance <= 0:
            raise ValueError("download byte budget exhausted")
        folder = self.root / (digest(url.encode())[:16] + "-" + str(len(matching) + 1))
        folder.mkdir()
        write(
            folder / "intent.json",
            {"url": url, "kind": kind, "at": now(), "reserved_bytes": allowance},
        )
        count, metadata, body_complete = 0, {}, False
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "DisasterTrace-MM research/1.0",
                    "Accept-Encoding": "identity",
                },
            )
            opener = urllib.request.build_opener(OfficialRedirect())
            try:
                response = opener.open(request, timeout=40)
            except urllib.error.HTTPError as error:
                response = error
            with response, (folder / "body").open("xb") as output:
                check_url(response.url)
                metadata = {
                    "http_status": response.status,
                    "final_url": response.url,
                    "headers": dict(response.headers.items()),
                }
                while count < allowance:
                    chunk = response.read(min(65536, allowance - count))
                    if not chunk:
                        body_complete = True
                        break
                    count += len(chunk)
                    output.write(chunk)
                    output.flush()
                    os.fsync(output.fileno())
                if count == allowance:
                    raise ValueError("response reached byte cap; incomplete body retained")
            data = (folder / "body").read_bytes()
            if response.status != 200:
                raise ValueError("HTTP status " + str(response.status))
            if kind == "zip":
                zip_members(data)
            elif kind == "html" and b"<" not in data[:1024]:
                raise ValueError("directory response is not HTML")
            receipt = {
                "url": url,
                "kind": kind,
                "status": "received",
                "retrieved_at": now(),
                "historical_available_at": None,
                "bytes_received": count,
                "budget_charged_bytes": count,
                "sha256": digest(data),
                **metadata,
            }
            write(folder / "receipt.json", receipt)
            return folder / "body", receipt
        except Exception as error:
            write(
                folder / "receipt.json",
                {
                    "url": url,
                    "kind": kind,
                    "status": "failed",
                    "at": now(),
                    "bytes_received": count,
                    "error_type": type(error).__name__,
                    "budget_charged_bytes": count if body_complete else allowance,
                    "unobserved_transfer_possible": not body_complete,
                    "error": str(error),
                    **metadata,
                },
            )
            raise
