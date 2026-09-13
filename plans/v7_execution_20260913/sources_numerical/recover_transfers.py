"""Resume explicitly detected short transfers, bound to their original HTTP ETags."""
import concurrent.futures
import hashlib
import json

from fetch import ROOT, fetch


def recover(row):
    name = row["name"]
    path = ROOT / "raw" / name
    partial = path.with_suffix(path.suffix + ".partial")
    if not partial.exists():
        path.rename(partial)
    records = [json.loads(line) for line in (ROOT / "REQUESTS.jsonl").read_text().splitlines()]
    original = next(r for r in records if r["name"] == name)
    prefix = partial.read_bytes()
    chunks = []
    for start in range(len(prefix), row["expected"], 750_000):
        end = min(row["expected"] - 1, start + 749_999)
        partname = name + f".range_{start}_{end}"
        headers = {"Range": f"bytes={start}-{end}", "If-Match": row["etag"]}
        result = fetch(original["url"], partname, cap=750_000, headers=headers)
        if "error" in result or result.get("status") != 206:
            raise ValueError(f"Range request failed: {partname}")
        content_range = {k.lower(): v for k, v in result["headers"].items()}.get("content-range")
        if content_range != f"bytes {start}-{end}/{row['expected']}":
            raise ValueError("Unexpected Content-Range")
        chunks.append((ROOT / result["local"]).read_bytes())
    combined = prefix + b"".join(chunks)
    if len(combined) != row["expected"]:
        raise ValueError("Recovered object length mismatch")
    md5 = hashlib.md5(combined).hexdigest()
    if md5 != row["etag"].strip('"'):
        raise ValueError("Recovered object MD5 does not match single-part ETag")
    path.write_bytes(combined)
    return {"name": name, "bytes": len(combined), "sha256": hashlib.sha256(combined).hexdigest(),
            "md5": md5, "etag_matches": True, "retained_partial": str(partial.relative_to(ROOT))}


if __name__ == "__main__":
    rows = json.loads((ROOT / "INCOMPLETE_TRANSFER_AUDIT.json").read_text())
    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        results = list(pool.map(recover, rows))
    (ROOT / "RECOVERED_TRANSFERS.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))
