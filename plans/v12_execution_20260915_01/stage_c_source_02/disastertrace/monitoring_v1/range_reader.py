"""Byte caps apply before a request; distinct ranges require object identity."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class RangeResponse:
    status: int
    body: bytes
    content_range: str
    etag: str | None = None
    last_modified: str | None = None


class BoundedRangeReader:
    def __init__(self, *, max_bytes, max_requests):
        if (
            type(max_bytes) is not int
            or type(max_requests) is not int
            or min(max_bytes, max_requests) < 0
        ):
            raise ValueError("Invalid range budget")
        self.max_bytes, self.max_requests = max_bytes, max_requests
        self.spent_bytes = self.spent_requests = 0
        self.version = None
        self.receipts = []

    def fetch(self, start, end, bounded_transport):
        if type(start) is not int or type(end) is not int or start < 0 or end < start:
            raise ValueError("Invalid byte range")
        requested = end - start + 1
        if (
            self.spent_requests + 1 > self.max_requests
            or self.spent_bytes + requested > self.max_bytes
        ):
            raise ValueError("Range budget would be exceeded before request")
        self.spent_requests += 1
        try:
            response = bounded_transport(start, end, requested)
        except Exception:
            # The caller cannot spend unknown failed-transfer bytes a second time.
            self.spent_bytes += requested
            self.receipts.append(
                {"start": start, "end": end, "status": "transport_error_reserved_bytes_charged"}
            )
            raise
        self.spent_bytes += len(response.body)
        receipt = {
            "start": start,
            "end": end,
            "bytes": len(response.body),
            "http_status": response.status,
        }
        self.receipts.append(receipt)
        if len(response.body) != requested or response.status != 206:
            receipt["status"] = "rejected_range"
            raise ValueError("Transport violated bounded range contract")
        match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", response.content_range)
        if (
            match is None
            or tuple(map(int, match.groups()[:2])) != (start, end)
            or int(match.group(3)) <= end
        ):
            receipt["status"] = "rejected_content_range"
            raise ValueError("Incorrect content range")
        if not response.etag and not response.last_modified:
            receipt["status"] = "rejected_missing_version"
            raise ValueError("No object version evidence for cross-range consistency")
        version = (response.etag, response.last_modified, int(match.group(3)))
        if self.version is not None and self.version != version:
            receipt["status"] = "rejected_changed_version"
            raise ValueError("Object version changed across ranges")
        self.version = version
        receipt["status"] = "accepted"
        return response.body
