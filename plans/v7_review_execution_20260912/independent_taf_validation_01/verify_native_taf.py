"""Cross-decode native TAF headers, clause clocks and visibility with AVWX."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import socket
import sys
from collections import Counter
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

BASE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def external_visibility(value, unit):
    if value is None:
        return None
    word = value.repr
    prefix = word[:1] if word[:1] in {"P", "M"} else ""
    token = word[1:] if prefix else word
    if token == "CAVOK":
        return (10000.0, math.inf, True, False)
    if " " in token:
        bound = sum(Fraction(part) for part in token.split())
    else:
        bound = Fraction(token)
    if unit == "sm":
        bound *= Fraction("1609.344")
    elif unit != "m":
        raise ValueError("Unexpected external visibility units")
    if prefix == "P":
        return (float(bound), math.inf, False, False)
    if prefix == "M":
        return (0.0, float(bound), True, False)
    if unit == "m" and token == "9999":
        return (10000.0, math.inf, True, False)
    return (float(bound), float(bound), True, True)


def bounds_match(ours, other):
    if ours is None or other is None:
        return ours is other
    ours = (ours["lower"], ours["upper"], ours["lower_closed"], ours["upper_closed"])
    normalized = [math.inf if v == "+inf" else -math.inf if v == "-inf" else v for v in ours]
    for index in (0, 1):
        a, b = normalized[index], other[index]
        if not math.isclose(a, b, abs_tol=1e-6, rel_tol=0):
            return False
        if math.isfinite(a) and normalized[index + 2] != other[index + 2]:
            return False
    return True


def main(args):
    sys.path.insert(0, str(BASE / "independent_taf_libs"))
    from avwx.current.taf import parse as avwx_parse
    from disastertrace.monitoring_v1.providers.aviation import parse_taf

    args.output.mkdir(exist_ok=False)
    sources = {}
    for dataset in args.datasets:
        for ident, binding in json.loads((dataset / "SOURCES.json").read_text()).items():
            if not ident.startswith("taf-"):
                continue
            if ident in sources and sources[ident]["sha256"] != binding["sha256"]:
                raise ValueError("Same native product ID has conflicting capture bytes")
            sources[ident] = binding
    rows, counts = [], Counter()

    def deny_network(*_args, **_kwargs):
        raise RuntimeError("Independent decoding must not fetch new data")

    socket.socket.connect = deny_network
    for ident, binding in sorted(sources.items()):
        body, receipt_path = BASE / binding["path"], BASE / binding["receipt_path"]
        if digest(body) != binding["sha256"] or digest(receipt_path) != binding["receipt_sha256"]:
            raise ValueError("Bound native TAF capture changed")
        receipt = json.loads(receipt_path.read_text())
        metadata = receipt["catalog_metadata"]
        issued = metadata["issued_at"].replace(" ", "T") + ":00Z"
        station, raw = metadata["station"], body.read_text()
        row = {"source_id": ident, "body_sha256": binding["sha256"], "differences": []}
        try:
            ours = parse_taf(raw, station=station, archive_issue=issued)
        except ValueError as exc:
            row.update(status="our_strict_parser_quarantined", reason=str(exc))
            rows.append(row)
            counts[row["status"]] += 1
            continue
        try:
            header = re.search(r"\b(?:TAF(?: AMD| COR)?\s+)?" + re.escape(station) + r"\s+\d{6}Z\b", raw)
            if header is None:
                raise ValueError("Missing native header for independent parser")
            payload = raw[header.start():].split("=", 1)[0]
            other, units, sanitation = avwx_parse(station, payload, issued=datetime.fromisoformat(issued.replace("Z", "+00:00")).date())

            def micros(stamp):
                return None if stamp is None else round(stamp.dt.timestamp() * 1_000_000)

            for key, left, right in (("station", ours.station, other.station),
                ("issued_at", ours.issued_at, micros(other.time)),
                ("valid_start", ours.valid_start, micros(other.start_time)),
                ("valid_end", ours.valid_end, micros(other.end_time)),
                ("clause_count", len(ours.clauses), len(other.forecast))):
                if left != right:
                    row["differences"].append({"field": key, "ours": left, "external": right})
            for index, (left, right) in enumerate(zip(ours.clauses, other.forecast)):
                start = right.transition_start if left.operator == "BECMG" else right.start_time
                if left.start != micros(start):
                    row["differences"].append({"field": f"clause{index}.start", "ours": left.start, "external": micros(start)})
                if left.operator not in {"BASE", "FM"} and left.end != micros(right.end_time):
                    row["differences"].append({"field": f"clause{index}.end", "ours": left.end, "external": micros(right.end_time)})
                expected_type = "FROM" if left.operator in {"BASE", "FM"} else "TEMPO" if "TEMPO" in left.operator else "PROB" if left.operator.startswith("PROB") else left.operator
                if right.type != expected_type:
                    row["differences"].append({"field": f"clause{index}.operator", "ours": left.operator, "external": right.type})
                probability = None if right.probability is None else right.probability.value / 100
                if left.native_probability != probability:
                    row["differences"].append({"field": f"clause{index}.native_probability", "ours": left.native_probability, "external": probability})
                other_interval = external_visibility(right.visibility, units.visibility)
                if not bounds_match(left.fields.get("visibility"), other_interval):
                    row["differences"].append({"field": f"clause{index}.visibility", "ours": left.fields.get("visibility"), "external_repr": None if right.visibility is None else right.visibility.repr})
                counts["compared_clauses"] += 1
            row["status"] = "matched_checked_fields" if not row["differences"] else "differences"
            row["external_sanitization"] = {"removed": sanitation.removed, "replaced": sanitation.replaced,
                "duplicates_found": sanitation.duplicates_found, "extra_spaces_needed": sanitation.extra_spaces_needed}
        except Exception as exc:
            row.update(status="external_decode_or_comparison_error", reason=type(exc).__name__ + ": " + str(exc))
        rows.append(row)
        counts[row["status"]] += 1
    result = {"checked_at": datetime.now(timezone.utc).isoformat(), "unique_products": len(sources),
        "counts": dict(counts), "records": rows,
        "external_library": {"name": "avwx-engine", "version": "1.9.9", "license": "MIT",
            "repository": "https://github.com/avwx-rest/avwx-engine",
            "wheels": {p.name: digest(p) for p in (BASE / "independent_taf_downloads").glob("*.whl")},
            "parser_sha256": digest(Path(avwx_parse.__code__.co_filename))},
        "our_parser_sha256": digest(Path(parse_taf.__code__.co_filename)),
        "validator_sha256": digest(Path(__file__)),
        "network_during_decode": "blocked socket.connect",
        "scope": "Independent native header, main validity, clause start/conditional end, operator/probability and explicit visibility bounds. Not an independent proof of all inherited-field projection, product publication time, physical truth or probability calibration. Strict-unparsed source envelopes remain quarantined; external parser repairs are recorded, not accepted as Gold."}
    with (args.output / "REPORT.json").open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    shutil.copyfile(__file__, args.output / "verify_native_taf.py")
    shutil.copyfile(BASE / "independent_taf_libs/avwx_engine-1.9.9.dist-info/licenses/LICENSE", args.output / "AVWX_LICENSE.txt")
    print(json.dumps({"unique_products": len(sources), **counts}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--datasets", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
