"""Independently verify the local source payloads and final audit claims."""

import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
import zipfile
import zlib
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
USER_ROOT = ROOT.parents[4]
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    audits = json.loads((ROOT / "outputs_02/AUDIT.json").read_text())["reports"]
    emdat, cma = audits
    original_checks = []
    for name in [Path(emdat["file"]["path"]).name, "CMABSTdata.rar"]:
        original, copy = USER_ROOT / name, ROOT / "inputs" / name
        if digest(original) != digest(copy):
            raise ValueError("Original user file and working copy differ")
        original_checks.append(
            {"name": name, "bytes": copy.stat().st_size, "sha256": digest(copy)}
        )

    # Read worksheet XML directly, independently of the openpyxl ingestion path.
    with zipfile.ZipFile(ROOT / emdat["file"]["path"]) as archive:
        if archive.testzip() is not None:
            raise ValueError("XLSX member CRC failure")
        with archive.open("xl/worksheets/sheet1.xml") as stream:
            rows, widths, columns, precision = 0, Counter(), None, Counter()
            weather, missing_coords, valid_coords = 0, 0, 0
            for _, element in ET.iterparse(stream, events=["end"]):
                if element.tag != "{" + NS["s"] + "}row":
                    continue
                cells = []
                for cell in element.findall("s:c", NS):
                    if cell.get("t") == "inlineStr":
                        value = "".join(
                            node.text or "" for node in cell.findall(".//s:t", NS)
                        )
                    else:
                        value = cell.findtext("s:v", default="", namespaces=NS)
                    cells.append(value.strip() or None)
                widths[len(cells)] += 1
                if columns is None:
                    columns = cells
                else:
                    rows += 1
                    record = dict(zip(columns, cells))
                    if record["Disaster Group"] == "Natural" and record[
                        "Disaster Type"
                    ] in {
                        "Flood",
                        "Storm",
                        "Extreme temperature",
                        "Drought",
                        "Wildfire",
                    }:
                        weather += 1
                        level = (
                            "day"
                            if record["Start Day"]
                            else "month"
                            if record["Start Month"]
                            else "year"
                        )
                        precision[level] += 1
                        if record["Latitude"] is None or record["Longitude"] is None:
                            missing_coords += 1
                        elif (
                            -90 <= float(record["Latitude"]) <= 90
                            and -180 <= float(record["Longitude"]) <= 180
                        ):
                            valid_coords += 1
                element.clear()
    if (
        rows != emdat["actual_rows"]
        or dict(precision) != emdat["start_date_precision"]
        or weather != emdat["core_weather_country_records"]
    ):
        raise ValueError("Independent XML counts disagree with EM-DAT audit")
    if (
        missing_coords != emdat["missing_coordinates"]
        or valid_coords != emdat["valid_coordinate_pairs"]
        or set(widths) != {47}
    ):
        raise ValueError("Independent spatial/column counts disagree with EM-DAT audit")

    archive_index = json.loads((ROOT / "validation/CMA_ARCHIVE_INDEX.json").read_text())
    storms, points, optional = 0, 0, 0
    for member in archive_index:
        raw = (ROOT / "extracted/cma" / member["Path"]).read_bytes()
        if len(raw) != int(member["Size"]) or f"{zlib.crc32(raw):08X}" != member["CRC"]:
            raise ValueError("CMA extracted member differs from RAR index")
        remaining = 0
        for line in raw.decode().splitlines():
            values = line.split()
            if not values:
                continue
            if values[0] == "66666":
                if remaining:
                    raise ValueError("CMA storm declared point count mismatch")
                remaining = int(values[2])
                storms += 1
            else:
                if remaining <= 0 or len(values) not in {6, 7}:
                    raise ValueError("Unexpected CMA point layout")
                remaining -= 1
                points += 1
                optional += len(values) == 7
        if remaining:
            raise ValueError("CMA final storm truncated")
    if (storms, points, optional) != (
        cma["storm_segments"],
        cma["point_records"],
        cma["optional_column_records"],
    ):
        raise ValueError("Independent CMA counts disagree")

    xbd = json.loads((ROOT / "xbd_audit_02/AUDIT.json").read_text())
    for binding in xbd["files"]:
        path = ROOT / binding["path"]
        if path.stat().st_size != binding["bytes"] or digest(path) != binding["sha256"]:
            raise ValueError("xBD bound asset changed")
    metadata = ROOT / "captures/xbd_geotransforms_02/response.body"
    if (
        hashlib.sha1(metadata.read_bytes()).hexdigest()
        != "0b3bda08084ac102d8b540261ebbba0094203a2f"
    ):
        raise ValueError("Official xBD metadata SHA1 mismatch")
    damage = Counter()
    for path in sorted((ROOT / "extracted/xbd_pairs").glob("*_post_disaster.json")):
        label = json.loads(path.read_text())
        damage.update(
            row["properties"].get("subtype", "unknown")
            for row in label["features"]["xy"]
        )
    reported_damage = sum(
        (Counter(p["post_damage_labels"]) for p in xbd["pairs"]), Counter()
    )
    if damage != reported_damage:
        raise ValueError("Independent xBD damage counts disagree")
    if xbd["spatial_grounding_admitted"] or xbd["native_pixel_label_overlay_validated"]:
        raise ValueError("Known spatial mismatch must block grounding admission")
    captures = []
    for path in sorted((ROOT / "captures").glob("xbd_*/RECEIPT.json")):
        receipt = json.loads(path.read_text())
        body = path.parent / "response.body"
        if body.stat().st_size != receipt["bytes"] or digest(body) != receipt["sha256"]:
            raise ValueError("xBD transfer receipt differs from body")
        captures.append(receipt)
    for short, long in [
        ("xbd_full_prefix_02", "xbd_full_prefix_03"),
        ("xbd_hold_prefix_02", "xbd_hold_prefix_03"),
    ]:
        first = (ROOT / "captures" / short / "response.body").read_bytes()
        with (ROOT / "captures" / long / "response.body").open("rb") as stream:
            if first != stream.read(len(first)):
                raise ValueError("Overlapping xBD archive prefixes differ")
    report = {
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "originals_equal_copies": original_checks,
        "emdat_xml": {
            "records": rows,
            "column_counts_including_header": dict(widths),
            "weather_records": weather,
            "start_precision": dict(precision),
            "missing_coordinates": missing_coords,
            "valid_coordinate_pairs": valid_coords,
        },
        "cma_raw": {
            "crc_checked_members": len(archive_index),
            "storm_segments": storms,
            "point_records": points,
            "optional_column_records": optional,
        },
        "xbd": {
            "bound_files": len(xbd["files"]),
            "damage_counts": dict(damage),
            "published_metadata_sha1_passed": True,
            "overlapping_prefix_bytes_equal": True,
            "spatial_grounding_correctly_blocked": True,
        },
        "network": {
            "logical_xbd_requests": len(captures),
            "response_body_bytes": sum(r["bytes"] for r in captures),
            "http_200_206_curl_zero": sum(
                r["curl_exit"] == 0 and r["http_status"] in {200, 206} for r in captures
            ),
            "scope": "xBD capture receipts only; includes failed and overlapping prefixes. Excludes CMA page probe, redirects and software dependencies.",
        },
        "audit_hashes": {
            name: digest(ROOT / name)
            for name in ["outputs_02/AUDIT.json", "xbd_audit_02/AUDIT.json"]
        },
        "checks_passed": True,
        "all_sources_task_ready": False,
    }
    (args.output / "VERIFICATION.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
