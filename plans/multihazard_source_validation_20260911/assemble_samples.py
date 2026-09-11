"""Complete interrupted captures only with contiguous, identical-version ranges."""

import argparse
import hashlib
import json
import re

from validate_samples import ROOT, captures, require, validate


def assemble(rows, ident):
    spec, response, prefix = rows[ident]
    total = int(response["headers"]["content-length"])
    require(response["http_status"] == 200 and not response["complete"], "expected an interrupted full GET")
    chunks = [(0, prefix, ident)]
    for name, (part, result, data) in rows.items():
        if part.get("completes") != ident:
            continue
        require(result.get("complete") and result["http_status"] == 206, "range incomplete: " + name)
        match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", result["headers"].get("content-range", ""))
        require(match is not None, "missing Content-Range")
        start, end, length = map(int, match.groups())
        require(part["range"] == f"bytes={start}-{end}" and end - start + 1 == len(data) and length == total, "range identity/length")
        require(result["headers"].get("etag") == response["headers"].get("etag") and response["headers"].get("etag"), "object version changed")
        chunks.append((start, data, name))
    chunks.sort()
    body, inputs = bytearray(), []
    for start, data, name in chunks:
        require(start == len(body), "gap or overlap in assembly")
        body.extend(data)
        inputs.append({"id": name, "offset": start, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    require(len(body) == total, "assembled length mismatch")
    return spec, bytes(body), inputs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    args = parser.parse_args()
    folder = ROOT / "assemblies" / args.run
    folder.mkdir(parents=True, exist_ok=False)
    rows = captures()
    selected = sorted({s["completes"] for s, _, _ in rows.values() if "completes" in s})
    reports = []
    for ident in selected:
        record = {"id": ident, "source": rows[ident][0]["source"], "new_http_response": False}
        try:
            spec, body, inputs = assemble(rows, ident)
            path = folder / (ident + ".bin")
            path.write_bytes(body)
            # This wrapper admits a proven local assembly to the byte-format checker.
            level, details = validate(spec, {"complete": True, "http_status": 200}, body)
            record.update(level=level, details=details, inputs=inputs, path=str(path.relative_to(ROOT)), sha256=hashlib.sha256(body).hexdigest(), bytes=len(body))
        except Exception as exc:
            record.update(level="not_validated", error_type=type(exc).__name__, error=str(exc))
        reports.append(record)
    (folder / "RESULT.json").write_text(json.dumps({"reports": reports}, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps([{k: r.get(k) for k in ("id", "level", "error")} for r in reports]))


if __name__ == "__main__":
    main()
