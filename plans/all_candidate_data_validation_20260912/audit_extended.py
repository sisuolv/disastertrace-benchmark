"""Validate newer native samples and GEE extracts without admitting tasks."""

import argparse
import csv
import io
import json
from pathlib import Path
import struct
import tarfile
import zlib

import h5py
import netCDF4
import numpy as np

from audit_samples import ROOT, REPO, digest, raster, stats


def netcdf(path):
    arrays = {}
    with netCDF4.Dataset(str(path)) as dataset:
        def walk(group):
            for name, variable in group.variables.items():
                if np.dtype(variable.dtype).kind not in "iuf":
                    continue
                a = variable[:]
                attributes = {k: str(variable.getncattr(k)) for k in variable.ncattrs()}
                arrays[group.path + "/" + name] = dict(values=stats(a), attributes=attributes)
            for child in group.groups.values():
                walk(child)
        walk(dataset)
    return arrays


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Use a new audit path")
    reports = []

    def record(source, ident, paths, operation):
        if not all(p.exists() for p in paths):
            return
        report = dict(source_id=source, check_id=ident,
                      files=[dict(path=str(p.relative_to(REPO)), bytes=p.stat().st_size, sha256=digest(p.read_bytes())) for p in paths])
        try:
            level, details = operation()
            report.update(level=level, details=details)
        except Exception as error:
            report.update(level="decode_failed", error_type=type(error).__name__, error=str(error))
        reports.append(report)
        print(source, ident, report["level"], flush=True)

    for source, ident, folder, target in [
        ("D32", "smap-l3-coarse", "captures_07", "soil_moisture"),
        ("D36", "s5p-coarse", "captures_07", "aerosol_index_354_388"),
        ("D29", "imerg-E-subset", "captures_06", "precipitation"),
        ("D29", "imerg-L-subset", "captures_06", "precipitation"),
    ]:
        path = ROOT / folder / (ident + ".body")

        def decode(path=path, target=target):
            result = netcdf(path)
            variables = [v for k, v in result.items() if k.rsplit("/", 1)[-1] == target]
            assert variables and all(v["values"]["finite_count"] > 0 for v in variables)
            return "numeric_sample_decoded", dict(variables=result,
                limitation="Actual native product values with source metadata. Full product QC, event/time pairing and public release latency remain unvalidated.")

        record(source, ident, [path], decode)

    path = ROOT / "captures_06/gesla-bounded-day.body"

    def gesla():
        rows = list(csv.DictReader(path.read_text().splitlines()))
        assert rows.pop(0)["sea_level"] == "m"
        assert len(rows) == 4
        for row in rows:
            assert np.isfinite(float(row["sea_level"])) and row["record_id"] == "abbot_point-59300-aus-bom"
        return "station_records_decoded", dict(rows=rows,
            limitation="Current GESLA endpoint, not necessarily release GESLA-3. Station datum and flag1/flag2 conventions must be bound before tide/surge scoring.")

    record("D69", "gesla-hourly-levels", [path], gesla)
    files = [ROOT / "captures_07/worldflood-S2-complete.body", ROOT / "captures_06/worldflood-gt.body", ROOT / "captures_06/worldflood-meta.body"]

    def worldflood():
        image, label = [raster(p.read_bytes()) for p in files[:2]]
        assert image["crs"] == label["crs"] and image["transform"] == label["transform"]
        assert image["values"]["shape"][-2:] == label["values"]["shape"][-2:]
        return "paired_arrays_decoded", dict(image=image, label=label, metadata=json.loads(files[2].read_text()),
            limitation="One original train event image/label pair. Label semantics, mixed-source licences, event grouping and active-warning temporal use require separate admission.")

    record("D51", "worldflood-native-pair", files, worldflood)
    path = ROOT / "captures_07/urban-sar-chip.body"
    record("D14", "urbansarfloods-native-chip", [path],
           lambda: ("numeric_sample_decoded", dict(image=raster(path.read_bytes()),
               limitation="Native chip from testing_case_256/20210727_Weihui; no corresponding mask validated. Exposed original test chip is access-only, not eligible as untouched heldout.")))

    path = REPO / "plans/multihazard_source_validation_20260911/attempts/0203/body.bin"

    def senfor():
        desired = {f"{index:06}_{suffix}.tif" for index in range(3) for suffix in ["LULC", "flood_mask", "s1_before_flood"]}
        extracted = {}
        with tarfile.open(fileobj=io.BytesIO(path.read_bytes()), mode="r|*") as archive:
            for member in archive:
                name = Path(member.name).name
                if member.isfile() and name in desired:
                    raw = archive.extractfile(member).read()
                    assert len(raw) == member.size
                    extracted[name] = dict(archive_path=member.name, sha256=digest(raw), raster=raster(raw))
                if set(extracted) == desired:
                    break
        assert set(extracted) == desired
        return "paired_arrays_decoded", dict(members=extracted, complete_members=9,
            limitation="Three pre-flood SAR/mask/background groups, not three contemporaneous post-flood pairs. Native post-event assets and issue/target times remain unverified.")

    record("D64", "senfor-existing-prefix-native-groups", [path], senfor)
    path = ROOT / "captures_08/digital-typhoon-three-frame-prefix.body"

    def digital():
        raw = path.read_bytes()
        offset, samples = 0, []
        while len(samples) < 3:
            header = struct.unpack_from("<4s5H3I2H", raw, offset)
            assert header[0] == b"PK\x03\x04" and not (header[2] & 8)
            name = raw[offset + 30:offset + 30 + header[-2]].decode()
            start = offset + 30 + header[-2] + header[-1]
            end = start + header[7]
            assert end <= len(raw)
            compressed = raw[start:end]
            body = zlib.decompress(compressed, -15) if header[3] == 8 else compressed
            assert len(body) == header[8] and zlib.crc32(body) == header[6]
            offset = end
            if not name.endswith(".h5"):
                continue
            arrays = {}
            with h5py.File(io.BytesIO(body)) as dataset:
                def collect(key, obj):
                    if isinstance(obj, h5py.Dataset) and obj.dtype.kind in "iuf":
                        arrays[key] = stats(obj[:])
                dataset.visititems(collect)
            assert arrays
            samples.append(dict(member=name, member_sha256=digest(body), zip_member_crc_checked=True, arrays=arrays))
        return "numeric_sample_decoded", dict(samples=samples,
            limitation="Three consecutive native frames from one typhoon; intensity-label metadata and independent storm/split coverage are not yet joined.")

    record("D03", "digital-typhoon-native-frames", [path], digital)
    for directory in sorted(ROOT.glob("gee_collections_*")):
        for path in sorted(directory.glob("*/RECEIPT.json")):
            receipt = json.loads(path.read_text())
            if receipt["status"] != "numeric_pixels_downloaded":
                continue
            files = [path, path.parent / "sample.json", path.parent / "metadata.json"]
            if (path.parent / "sample.tif").exists():
                files.append(path.parent / "sample.tif")

            def gee(path=path, receipt=receipt):
                raw = (path.parent / "sample.json").read_bytes()
                assert digest(raw) == receipt["sample_sha256"]
                features = json.loads(raw)["features"]
                assert features
                special = []
                for feature in features:
                    values = feature["properties"]
                    for key in ["soil_moisture_am", "sm_surface", "sm_rootzone"]:
                        if key in values:
                            assert 0 <= values[key] <= 1
                    if "SCL" in values and values["SCL"] in {3, 8, 9, 10}:
                        special.append("cloud_or_cloud_shadow_pixel")
                    if "retrieval_qual_flag_am" in values and values["retrieval_qual_flag_am"] & 1:
                        special.append("SMAP_recommended_quality_bit_not_passed")
                details = dict(collection=receipt["collection"], image_id=receipt["image_id"],
                               samples=features, quality_cautions=sorted(set(special)),
                               limitation="Readability verified; collection scale factors, QA, task semantics and historical availability require explicit contracts. GEE is a delivery path, not an independent observation source.")
                if (path.parent / "sample.tif").exists():
                    raw = (path.parent / "sample.tif").read_bytes()
                    assert digest(raw) == receipt["geotiff_sha256"]
                    details["downloaded_raster"] = raster(raw)
                return "numeric_sample_decoded", details

            record(receipt["source_id"], directory.name + "/" + receipt["id"], files, gee)
    path = ROOT / "gee_mtbs_boundaries_01/sample.geojson"

    def mtbs():
        data = json.loads(path.read_text())
        assert len(data["features"]) == 3 and all(f["geometry"] for f in data["features"])
        return "vector_records_decoded", dict(features=3, properties=[f["properties"] for f in data["features"]],
            limitation="Burned-area perimeters are retrospective impact products, not independent daily fire-spread forecasts.")

    record("D24", "mtbs-perimeter-features", [path], mtbs)
    args.output.write_text(json.dumps(dict(reports=reports, formal_new_tasks=0), indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
