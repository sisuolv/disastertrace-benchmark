"""Expose only captured byte intervals of a remote HDF5 object."""

import io
import re

from common import capture


class CapturedFile(io.RawIOBase):
    def __init__(self, segments, size):
        self.segments, self.size, self.position = sorted(segments), size, 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        target = offset if whence == 0 else self.position + offset if whence == 1 else self.size + offset
        if target < 0:
            raise ValueError("negative file position")
        self.position = target
        return target

    def read(self, size=-1):
        if size < 0:
            size = self.size - self.position
        if size == 0:
            return b""
        for offset, body in self.segments:
            if offset <= self.position and self.position + size <= offset + len(body):
                result = body[self.position - offset:self.position - offset + size]
                self.position += size
                return result
        raise ValueError(f"uncaptured HDF5 range: {self.position}, {size}")

    def readinto(self, target):
        body = self.read(len(target))
        target[:len(body)] = body
        return len(body)


def captured_file(ids):
    segments, sizes, versions, sources = [], set(), set(), []
    for key in ids:
        body, source = capture(key)
        start, end, total = map(int, re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)",
                                                source["headers"]["content-range"]).groups())
        if end - start + 1 != len(body):
            raise ValueError("range size mismatch")
        segments.append((start, body))
        sizes.add(total)
        versions.add((source["url"], source["headers"]["etag"]))
        sources.append(source)
    if len(sizes) != 1 or len(versions) != 1:
        raise ValueError("remote object changed between range captures")
    return CapturedFile(segments, sizes.pop()), sources
