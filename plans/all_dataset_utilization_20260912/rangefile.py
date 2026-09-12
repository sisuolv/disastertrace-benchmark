"""Seek over captured HTTP ranges without inventing any unobserved bytes."""

import io
from pathlib import Path

from fetch_batch import fetch_one


class RemoteFile(io.RawIOBase):
    def __init__(self, spec, output):
        self.spec = spec
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=False)
        self.position = 0
        self.length = spec["size"]
        self.cache = []
        self.receipts = []
        self.version = None

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        if whence not in (0, 1, 2):
            raise ValueError("Invalid seek origin")
        target = offset + (
            self.position if whence == 1 else self.length if whence == 2 else 0
        )
        if not 0 <= target <= self.length:
            raise ValueError("Seek outside declared asset")
        self.position = target
        return target

    def read(self, size=-1):
        size = min(size if size >= 0 else self.length, self.length - self.position)
        if size == 0:
            return b""
        if size > 32 * 1024**2:
            raise ValueError("Read exceeds per-range sample budget")
        start, stop = self.position, self.position + size
        for offset, data in self.cache:
            if offset <= start and stop <= offset + len(data):
                self.position = stop
                return data[start - offset : stop - offset]
        if (
            len(self.receipts) >= 40
            or sum(r["bytes"] for r in self.receipts) >= 128 * 1024**2
        ):
            raise ValueError("Range sampler budget exceeded")
        end = min(self.length, max(stop, start + 65536)) - 1
        row = {
            "id": "range-" + str(len(self.receipts)),
            "source_id": self.spec["source_id"],
            "url": self.spec["url"],
            "range": f"{start}-{end}",
            "max_bytes": end - start + 1,
            "timeout": 120,
            "proxy": self.spec.get("proxy", False),
        }
        receipt = fetch_one(row, self.output)
        self.receipts.append(receipt)
        expected = f"bytes {start}-{end}/{self.length}"
        if (
            receipt["http_status"] != 206
            or receipt["curl_exit"]
            or receipt["bytes"] != end - start + 1
            or receipt["response_headers"].get("content-range") != expected
        ):
            raise ValueError("Incomplete or inconsistent range")
        version = tuple(
            receipt["response_headers"].get(k) for k in ("etag", "last-modified")
        )
        if self.version is not None and version != self.version:
            raise ValueError("Archive changed between range reads")
        self.version = version
        data = (self.output / receipt["body_file"]).read_bytes()
        self.cache.append((start, data))
        self.position = stop
        return data[:size]

    def readinto(self, buffer):
        data = self.read(len(buffer))
        buffer[: len(data)] = data
        return len(data)
