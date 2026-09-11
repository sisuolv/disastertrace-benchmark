"""Local capture lookup shared by the feasibility scripts."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT.parent / "v5_0910_source_probe_20260910"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def capture(key, old=False):
    root = OLD if old else ROOT
    matches = list((root / "batches").glob("*/" + key + ".json"))
    if len(matches) != 1:
        raise ValueError(f"capture identity missing/ambiguous: {key}")
    result = json.loads(matches[0].read_text())["final"]
    if result["http_status"] not in (200, 206) or not result["complete"]:
        raise ValueError(f"incomplete or failed response: {key}")
    path = root / result["attempt_path"] / "body.bin"
    body = path.read_bytes()
    if digest(body) != result["body_sha256"]:
        raise ValueError(f"capture hash mismatch: {key}")
    return body, {
        "capture_id": key, "url": result["url"],
        "path": str(path.relative_to(ROOT.parent.parent)),
        "sha256": digest(body), "captured_at": result["finished_at"],
        "headers": result["headers"],
    }
