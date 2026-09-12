"""Download complete small ZIP members with range/version and member CRC checks."""

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path

from rangefile import RemoteFile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text())
    args.output.mkdir(parents=True, exist_ok=False)
    result = {"source_id": spec["source_id"], "members": [], "status": "pending"}
    stream = RemoteFile(spec, args.output / "ranges")
    try:
        with zipfile.ZipFile(stream) as archive:
            entries = archive.infolist()
            index = [
                {
                    "name": e.filename,
                    "bytes": e.file_size,
                    "compressed": e.compress_size,
                    "crc32": e.CRC,
                }
                for e in entries
            ]
            (args.output / "INDEX.json").write_text(json.dumps(index, indent=2) + "\n")
            chosen = [
                e
                for e in entries
                if not e.is_dir()
                and re.search(spec["pattern"], e.filename)
                and e.file_size <= 24 * 1024**2
            ][: spec.get("count", 3)]
            if not chosen:
                raise ValueError("No small members satisfy selection")
            for i, entry in enumerate(chosen):
                data = archive.read(entry)
                local = f"member_{i:02d}" + Path(entry.filename).suffix
                (args.output / local).write_bytes(data)
                result["members"].append(
                    {
                        "member": entry.filename,
                        "file": local,
                        "bytes": len(data),
                        "sha256": hashlib.sha256(data).hexdigest(),
                        "crc_checked": True,
                    }
                )
                print(entry.filename, len(data), flush=True)
            result["status"] = "complete_members"
    except Exception as error:  # noqa: BLE001 -- Retain partial acquisition and its failure receipt.
        result.update(
            status="failed_or_partial",
            error_type=type(error).__name__,
            error=str(error),
        )
    result["network_requests"] = len(stream.receipts)
    result["network_bytes"] = sum(r["bytes"] for r in stream.receipts)
    (args.output / "RESULT.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result), flush=True)
    return 0 if result["status"] == "complete_members" else 1


if __name__ == "__main__":
    raise SystemExit(main())
