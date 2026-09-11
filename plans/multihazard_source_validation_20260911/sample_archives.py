"""Download complete small ZIP members through recorded, checked HTTP ranges."""

import argparse
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

import probe_sources as fetcher

ROOT = Path(__file__).resolve().parent


class RangeReader(io.RawIOBase):
    def __init__(self, url, folder, budget):
        self.url, self.folder, self.budget = url, folder, budget
        self.pos, self.counter, self.blocks = 0, 0, []
        self.etag, self.length = None, None
        self.fetch("bytes=-131072")

    def fetch(self, span):
        self.counter += 1
        spec = {"id": self.folder.name + "-range-" + str(self.counter), "url": self.url,
                "kind": "zip_member_range", "range": span, "max_bytes": 64 * 1024**2}
        result = fetcher.probe_one(spec, self.budget)
        fetcher.write(self.folder / f"request_{self.counter:03}.json", {"spec": spec, "result": result})
        response = result.get("final", {})
        if response.get("http_status") != 206 or not response.get("complete"):
            raise ValueError("server did not return a complete 206 range")
        match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", response["headers"].get("content-range", ""))
        if not match:
            raise ValueError("invalid Content-Range")
        start, end, total = map(int, match.groups())
        raw = (ROOT / response["attempt_path"] / "body.bin").read_bytes()
        if len(raw) != end - start + 1:
            raise ValueError("range byte count mismatch")
        if self.length is not None and (total != self.length or response["headers"].get("etag") != self.etag):
            raise ValueError("object identity changed between range requests")
        if span.startswith("bytes=-"):
            expected = max(0, total - int(span[7:])), total - 1
        else:
            expected = tuple(map(int, span[6:].split("-")))
        if (start, end) != expected:
            raise ValueError("server returned a different range")
        self.length, self.etag = total, response["headers"].get("etag")
        self.blocks.append((start, raw))
        return start, raw

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        pos = offset if whence == 0 else self.pos + offset if whence == 1 else self.length + offset
        if pos < 0:
            raise ValueError("negative seek")
        self.pos = pos
        return pos

    def read(self, size=-1):
        if size < 0:
            size = self.length - self.pos
        size = min(size, self.length - self.pos)
        if size <= 0:
            return b""
        if size > 63 * 1024**2:
            raise ValueError("single range exceeds sample limit")
        for start, raw in self.blocks:
            if start <= self.pos and self.pos + size <= start + len(raw):
                result = raw[self.pos - start:self.pos - start + size]
                self.pos += size
                return result
        start = self.pos
        stop = min(self.length - 1, start + max(size, 65536) - 1)
        _, raw = self.fetch(f"bytes={start}-{stop}")
        self.pos += size
        return raw[:size]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--pattern", default="(?!)")
    parser.add_argument("--count", type=int, default=6)
    args = parser.parse_args()
    folder = ROOT / "archive_runs" / args.run
    folder.mkdir(parents=True, exist_ok=False)
    fetcher.write(folder / "INTENT.json", {**vars(args), "created_at": fetcher.now(),
                                         "rule": "First lexical matching members, capped at 48 MiB uncompressed per member; ZIP CRC checked."})
    budget = fetcher.Budget(fetcher.read(ROOT / "SCOPE.json"))
    result = {"url": args.url, "members": [], "status": "started"}
    try:
        reader = RangeReader(args.url, folder, budget)
        with zipfile.ZipFile(reader) as archive:
            entries = [{"name": i.filename, "compressed": i.compress_size, "uncompressed": i.file_size,
                        "crc32": i.CRC, "header_offset": i.header_offset} for i in archive.infolist()]
            fetcher.write(folder / "INDEX.json", {"object_bytes": reader.length, "etag": reader.etag, "entries": entries})
            selected = [i for i in sorted(archive.infolist(), key=lambda i: i.filename)
                        if re.search(args.pattern, i.filename) and not i.is_dir()
                        and i.file_size <= 48 * 1024**2 and i.compress_size <= 48 * 1024**2][:args.count]
            for index, member in enumerate(selected):
                data = archive.read(member)
                target = folder / f"member_{index:03}.bin"
                target.write_bytes(data)
                result["members"].append({"name": member.filename, "path": str(target.relative_to(ROOT)),
                                          "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "crc32": member.CRC})
        result["status"] = "members_downloaded" if result["members"] else "index_only"
    except Exception as exc:
        result.update(status="incomplete", error_type=type(exc).__name__, error=str(exc))
    result["completed_at"] = fetcher.now()
    fetcher.write(folder / "RESULT.json", result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
