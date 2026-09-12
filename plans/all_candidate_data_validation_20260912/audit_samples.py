"""Decode acquired content and retain role-specific scientific limitations."""

import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import struct
import tarfile
import xml.etree.ElementTree as ET
import zlib

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def stats(array):
    a = np.ma.asarray(array)
    values = a.compressed()
    values = values[np.isfinite(values)]
    return dict(shape=list(a.shape), dtype=str(a.dtype), finite_count=int(values.size),
                minimum=float(values.min()) if values.size else None,
                maximum=float(values.max()) if values.size else None)


def raster(raw):
    with rasterio.io.MemoryFile(raw) as memory, memory.open() as ds:
        array = ds.read(masked=True)
        return dict(values=stats(array), crs=str(ds.crs), transform=list(ds.transform),
                    bounds=list(ds.bounds),
                    nodata=(str(ds.nodata) if ds.nodata is not None and not np.isfinite(ds.nodata) else ds.nodata),
                    band_descriptions=list(ds.descriptions))


def varint(data, position):
    value = 0
    for shift in range(0, 70, 7):
        byte = data[position]
        position += 1
        value |= (byte & 127) << shift
        if byte < 128:
            return value, position
    raise ValueError("Invalid protobuf varint")


def fields(data):
    position = 0
    while position < len(data):
        tag, position = varint(data, position)
        wire = tag & 7
        if wire == 2:
            size, position = varint(data, position)
            value = data[position:position + size]
            if len(value) != size:
                raise ValueError("Truncated protobuf field")
            position += size
        elif wire == 0:
            value, position = varint(data, position)
        elif wire in (1, 5):
            size = 8 if wire == 1 else 4
            value = data[position:position + size]
            position += size
        else:
            raise ValueError("Unexpected protobuf wire type")
        yield tag >> 3, wire, value


def nextday():
    import google_crc32c
    origin = REPO / "plans/multihazard_source_validation_20260911/attempts/0227/body.bin"
    raw = origin.read_bytes()
    header = struct.unpack_from("<4s5H3I2H", raw)
    assert header[0] == b"PK\x03\x04" and header[3] == 8
    offset = 30 + header[-2] + header[-1]
    body = zlib.decompressobj(-15).decompress(raw[offset:], 3_000_000)

    def crc(data):
        value = google_crc32c.value(data)
        return (((value >> 15) | (value << 17)) + 0xA282EAD8) & 0xFFFFFFFF

    samples = []
    position = 0
    for _ in range(3):
        length = struct.unpack_from("<Q", body, position)[0]
        assert crc(body[position:position + 8]) == struct.unpack_from("<I", body, position + 8)[0]
        example = body[position + 12:position + 12 + length]
        assert len(example) == length
        assert crc(example) == struct.unpack_from("<I", body, position + 12 + length)[0]
        position += 16 + length
        feature_map = {}
        outer = list(fields(example))
        assert len(outer) == 1 and outer[0][0] == 1
        for _, _, entry in fields(outer[0][2]):
            parts = {key: value for key, _, value in fields(entry)}
            name = parts[1].decode()
            feature = list(fields(parts[2]))
            assert len(feature) == 1 and feature[0][0] == 2, "Expected FloatList"
            packed = b"".join(value for _, _, value in fields(feature[0][2]))
            values = np.frombuffer(packed, dtype="<f4")
            assert values.size == 4096 and np.isfinite(values).all()
            feature_map[name] = stats(values.reshape(64, 64))
            if name in {"PrevFireMask", "FireMask"}:
                unique, counts = np.unique(values, return_counts=True)
                assert set(unique) <= {-1, 0, 1}
                feature_map[name]["label_counts"] = {str(int(v)): int(n) for v, n in zip(unique, counts)}
        assert {"PrevFireMask", "FireMask"} <= feature_map.keys()
        samples.append(dict(example_sha256=digest(example), features=feature_map, tfrecord_crc_checked=True))
    return dict(samples=samples, source_path=str(origin.relative_to(REPO)), source_sha256=digest(raw),
                full_zip_crc_checked=False, full_archive_downloaded=False,
                limitation="Complete TFRecords from a partial ZIP; original ZIP CRC and event/time/split independence unverified.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Use a new audit path")
    rows = []

    def record(source, ident, kind, files, function):
        row = dict(source_id=source, check_id=ident, level=kind,
                   files=[dict(path=str(p.relative_to(REPO)), sha256=digest(p.read_bytes()), bytes=p.stat().st_size) for p in files])
        try:
            row["details"] = function()
        except Exception as error:
            row.update(level="decode_failed", error_type=type(error).__name__, error=str(error))
        rows.append(row)
        print(source, ident, row["level"], flush=True)

    for ident, source in [("modis-lst-full", "D34"), ("modis-snow-revised-full", "D33")]:
        path = ROOT / "captures_01" / (ident + ".body")

        def modis(path=path, source=source):
            from pyhdf.SD import SD, SDC
            dataset = SD(str(path), SDC.READ)
            try:
                name = "LST_Day_1km" if source == "D34" else "NDSI_Snow_Cover"
                qa_name = "QC_Day" if source == "D34" else "NDSI_Snow_Cover_Basic_QA"
                a, qa = dataset.select(name), dataset.select(qa_name)
                values, quality = a[:], qa[:]
                attributes = a.attributes()
                low, high = attributes["valid_range"]
                valid = (values >= low) & (values <= high) & (values != attributes["_FillValue"])
                good = valid & (((quality & 3) == 0) if source == "D34" else (quality <= 1))
                assert good.any()
                scaled = values[good] * attributes.get("scale_factor", 1)
                return dict(variable=name, raw=stats(values), valid_pixels=int(valid.sum()), qa_selected_pixels=int(good.sum()),
                            selected_scaled=stats(scaled), attributes=attributes,
                            qa_counts={str(int(v)): int(n) for v, n in zip(*np.unique(quality, return_counts=True))},
                            qa_rule="mandatory QA bits 0-1 equal 0" if source == "D34" else "basic QA 0 or 1, NDSI 0-100",
                            limitation="One tile/day. LST is not 2m air temperature; snow cover is not blizzard or freezing rain. Full task QC remains product-specific.")
            finally:
                dataset.end()

        record(source, ident, "numeric_sample_decoded", [path], modis)

    path = ROOT / "captures_01/merra2-dust-subset.body"
    attrs = ROOT / "captures_01/merra2-dust-attributes.body"

    def merra():
        text = path.read_text()
        output = {}
        for variable in ["DUEXTTAU", "DUSMASS"]:
            matches = re.findall(r"^" + variable + r"(?:\." + variable + r")?\[[^\n]+?\], (.+)$", text, re.M)
            values = [float(v.strip()) for line in matches for v in line.split(",")]
            assert len(values) == 27 and np.isfinite(values).all()
            output[variable] = dict(values=stats(np.array(values).reshape(3, 3, 3)))
        return dict(variables=output, attributes_file=str(attrs.relative_to(REPO)),
                    limitation="Dust AOD and near-surface dust mass from reanalysis; not independently observed dust-storm occurrence.")

    record("D35", "merra2-dust", "numeric_sample_decoded", [path, attrs], merra)
    for folder in sorted(ROOT.glob("zip_*")):
        report_path = folder / "ZIP_SAMPLE.json"
        if not report_path.exists():
            continue
        report = json.loads(report_path.read_text())
        if not report["members"]:
            continue

        def zip_arrays(folder=folder, report=report):
            samples = []
            for member in report["members"]:
                path = folder / member["local_file"]
                assert digest(path.read_bytes()) == member["sha256"]
                if path.suffix == ".npz":
                    with np.load(path, allow_pickle=False) as data:
                        sample = dict(member=member["archive_member"], arrays={k: stats(data[k]) for k in data.files})
                        assert data["image"].shape[-2:] == data["label"].shape
                        sample["label_counts"] = {str(int(v)): int(n) for v, n in zip(*np.unique(data["label"], return_counts=True))}
                else:
                    from PIL import Image
                    with Image.open(path) as image:
                        image.load()
                        sample = dict(member=member["archive_member"], format=image.format, size=list(image.size), mode=image.mode)
                samples.append(sample)
            return dict(samples=samples, full_member_crc_checked=True,
                        limitation="Convenience samples, not independent events. DAWN condition folders do not establish weather severity/time; Sen2Fire temporal/positive coverage remains unproved.")

        record(report["source_id"], folder.name, "paired_arrays_decoded" if report["source_id"] == "D22" else "images_decoded",
               [report_path] + [folder / r["local_file"] for r in report["members"]], zip_arrays)

    files = [ROOT / "captures_03" / ("sn8-" + s + ".body") for s in ["pre", "post", "labels"]]

    def sn8():
        pre, post = [raster(p.read_bytes()) for p in files[:2]]
        labels = json.loads(files[2].read_text())["features"]
        assert labels and all("geometry" in f and "properties" in f for f in labels)
        return dict(pre=pre, post=post, label_features=len(labels),
                    label_property_examples=[f["properties"] for f in labels[:3]],
                    mapping_file="SN8_PAIR_SELECTION.json", native_grids_equal=pre["transform"] == post["transform"],
                    limitation="Matched by provider mapping; image warping and annotation rasterization/coverage validation are still required.")

    record("D16", "spacenet8-image-label-pair", "paired_content_decoded", files, sn8)
    files = [ROOT / "captures_02" / ("s2-" + key + ".body") for key in ["coastal", "scl"]]
    record("D43", "sentinel2-native-l2a", "numeric_sample_decoded", files,
           lambda: dict(assets=[raster(p.read_bytes()) for p in files], metadata="captures_01/s2-stac.body",
                        limitation="AWS L2A assets, not a GEE SR_HARMONIZED query. Preserve baseline/reflectance-offset metadata; resample SCL explicitly."))

    path = ROOT / "captures_04/kuro-tar-prefix.body"

    def kuro():
        groups = {}
        with tarfile.open(fileobj=io.BytesIO(path.read_bytes()), mode="r|*") as archive:
            for member in archive:
                if not member.isfile():
                    continue
                raw = archive.extractfile(member).read()
                assert len(raw) == member.size
                group = groups.setdefault(str(Path(member.name).parent), {})
                name = Path(member.name).name
                group[name] = dict(sha256=digest(raw), bytes=len(raw),
                                   data=json.loads(raw) if name == "info.json" else raster(raw))
                if len(groups) == 3 and name == "info.json":
                    break
        assert len(groups) == 3 and all(len(g) == 8 and "info.json" in g for g in groups.values())
        return dict(groups=groups, complete_groups=3, full_archive_downloaded=False,
                    limitation="Three complete groups from one archive prefix. Preserve activation/split and provider label legend; no event-independence claim.")

    record("D13", "kuro-three-native-groups", "paired_arrays_decoded", [path], kuro)
    path = REPO / "plans/multihazard_source_validation_20260911/attempts/0227/body.bin"
    record("D20", "nextday-three-tfrecords", "paired_arrays_decoded", [path], nextday)

    for source, name in [("D40", "eonet-events"), ("D41", "gdacs-events"), ("D74", "billion-events")]:
        path = ROOT / "captures_01" / (name + ".body")

        def events(path=path, source=source):
            if source == "D40":
                events = json.loads(path.read_text())["events"]
                assert all(e.get("geometry") and e.get("id") for e in events)
                return dict(events=len(events), examples=events[:3], limitation="Discovery catalog, not pixel/forecast outcome truth; includes nonweather events.")
            if source == "D41":
                tree = ET.fromstring(path.read_bytes())
                items = tree.findall(".//item")
                assert items
                return dict(items=len(items), examples=[dict(title=e.findtext("title"), pubDate=e.findtext("pubDate")) for e in items[:3]],
                            limitation="Alert/event feed, not independent observed hazard labels; includes nonweather hazards.")
            text = path.read_text()
            assert "<html" not in text.lower()
            rows = list(csv.reader(io.StringIO(text)))
            assert len(rows) > 10
            return dict(rows=len(rows), first_rows=rows[:5], limitation="Economic impact event index; values and selection are not physical weather thresholds.")

        record(source, name, "catalog_records_decoded", [path], events)

    path = ROOT / "captures_04/wpc-numeric-qpf.body"

    def qpf():
        import eccodes
        values = []
        with path.open("rb") as stream:
            while (handle := eccodes.codes_grib_new_from_file(stream)) is not None:
                try:
                    keys = ["shortName", "name", "units", "dataDate", "dataTime", "stepType", "stepRange", "validityDate", "validityTime"]
                    values.append(dict(metadata={k: eccodes.codes_get(handle, k) for k in keys},
                                       values=stats(eccodes.codes_get_values(handle))))
                finally:
                    eccodes.codes_release(handle)
        assert values and all(x["values"]["finite_count"] > 0 for x in values)
        return dict(messages=values, limitation="Actual numerical QPF; winter products are a separate unverified product scope.")

    record("AW-WPC", "wpc-qpf-grib", "numeric_sample_decoded", [path], qpf)
    args.output.write_text(json.dumps(dict(reports=rows, formal_new_tasks=0), indent=2, ensure_ascii=True, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
