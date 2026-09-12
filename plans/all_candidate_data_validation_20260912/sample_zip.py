"""Read complete ZIP members via checked HTTP ranges, preserving each receipt."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

from fetch_samples import fetch


class RemoteFile(io.RawIOBase):
    def __init__(self, spec, output):
        self.spec = spec
        self.output = output
        self.length = spec["size"]
        self.position = 0
        self.counter = 0
        self.etag = None

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        self.position = offset + (self.position if whence == 1 else self.length if whence == 2 else 0)
        if self.position < 0:
            raise ValueError("Negative seek")
        return self.position

    def read(self, size=-1):
        size = min(self.length - self.position, size if size >= 0 else self.length)
        if size <= 0:
            return b""
        if size > 24 * 1024 * 1024 or self.counter >= 35:
            raise ValueError("Bounded sample budget exceeded")
        start, end = self.position, self.position + size - 1
        ident = self.spec["id"] + "-range-" + str(self.counter)
        self.counter += 1
        result = fetch(dict(id=ident, source_id=self.spec["source_id"], url=self.spec["url"],
                            range=f"{start}-{end}", max_bytes=max(size, 65536), timeout=90), self.output)
        expected = f"bytes {start}-{end}/{self.length}"
        if (result["http_status"] != 206 or result["curl_exit"] or result["bytes"] != size
                or result["response_headers"].get("content-range") != expected):
            raise ValueError("Incomplete or inconsistent HTTP range: " + ident)
        etag = result["response_headers"].get("etag")
        if self.etag is not None and etag != self.etag:
            raise ValueError("Remote archive version changed")
        self.etag = etag
        self.position += size
        return (self.output / result["body_file"]).read_bytes()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("spec", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text())
    args.output.mkdir(parents=True, exist_ok=False)
    report = dict(source_id=spec["source_id"], archive=spec["url"], members=[], status="pending")
    try:
        stream = RemoteFile(spec, args.output)
        with zipfile.ZipFile(stream) as archive:
            infos = archive.infolist()
            (args.output / "MEMBER_INDEX.json").write_text(json.dumps([
                dict(name=i.filename, size=i.file_size, compressed_size=i.compress_size, crc=i.CRC)
                for i in infos], indent=2) + "\n")
            chosen = [i for i in infos if not i.is_dir() and re.search(spec["pattern"], i.filename)
                      and i.file_size <= 24 * 1024 * 1024][:spec.get("count", 3)]
            if not chosen:
                raise ValueError("No complete small members matching pattern")
            for number, info in enumerate(chosen):
                data = archive.read(info)  # zipfile checks the uncompressed member CRC.
                name = f"member_{number:02}" + Path(info.filename).suffix
                (args.output / name).write_bytes(data)
                report["members"].append(dict(archive_member=info.filename, local_file=name,
                                              bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                                              crc_verified=True))
        report["status"] = "complete_members_downloaded_not_yet_scientifically_decoded"
    except Exception as error:
        report.update(status="failed_or_partial", error=str(error), error_type=type(error).__name__)
    (args.output / "ZIP_SAMPLE.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
