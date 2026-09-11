"""Offline sample verification spanning the earlier captures and V6 decisions."""

import csv
import hashlib
import io
import json
import re
import sys
import tarfile
import zlib
from pathlib import Path

import h5py
import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parent
PRIOR = ROOT.parent / "multihazard_source_validation_20260911"
sys.path.insert(0, str(PRIOR))
from validate_samples import captures, validate, require, array_summary, geotiff_sample, netcdf_sample
from assemble_samples import assemble


def digest(data):
    return hashlib.sha256(data).hexdigest()


def record_file(path, expected=None):
    data = path.read_bytes()
    require(expected is None or digest(data) == expected, "asset hash mismatch")
    return data


def main():
    output = ROOT / "analysis/DOWNLOADED_AUDIT.json"
    require(not output.exists(), "new output required")
    rows = captures()
    reports, failures = [], []
    for ident, (spec, response, body) in rows.items():
        r = {"id": ident, "source": spec.get("source"), "capture_bundle": str(PRIOR.name), "capture_path": response.get("attempt_path"), "sha256": digest(body), "bytes": len(body), "is_new_in_v6": False}
        try:
            r["level"], r["details"] = validate(spec, response, body)
        except Exception as exc:
            r.update(level="not_validated", error_type=type(exc).__name__, error=str(exc))
        reports.append(r)

    for ident in sorted({s["completes"] for s, _, _ in rows.values() if "completes" in s}):
        r = {"id": ident + "-assembled", "source": rows[ident][0]["source"], "is_new_in_v6": False}
        try:
            spec, body, inputs = assemble(rows, ident)
            level, details = validate(spec, {"complete": True, "http_status": 200}, body)
            existing = PRIOR / "assemblies/completion_01" / (ident + ".bin")
            if existing.exists():
                require(digest(existing.read_bytes()) == digest(body), "earlier assembly differs")
                path = str(existing.relative_to(ROOT.parent.parent))
            else:
                target = ROOT / "samples" / (ident + ".bin")
                target.write_bytes(body)
                path = str(target.relative_to(ROOT.parent.parent))
            r.update(level=level, details=details, inputs=inputs, asset_path=path, sha256=digest(body), bytes=len(body), new_http_response=False)
        except Exception as exc:
            r.update(level="not_validated", error_type=type(exc).__name__, error=str(exc))
        reports.append(r)

    archive_members = {}
    for f in sorted((PRIOR / "archive_runs").glob("*/RESULT.json")):
        result = json.loads(f.read_text())
        for member in result["members"]:
            data = record_file(PRIOR / member["path"], member["sha256"])
            require(zlib.crc32(data) == member["crc32"], "ZIP member CRC mismatch")
            archive_members[member["name"]] = member, data

    pairs = []
    for ident in ("1", "10", "100"):
        image, ib = archive_members[f"TrainData/img/image_{ident}.h5"]
        mask, mb = archive_members[f"TrainData/mask/mask_{ident}.h5"]
        with h5py.File(io.BytesIO(ib)) as f:
            im = f["img"][:]
        with h5py.File(io.BytesIO(mb)) as f:
            labels = f["mask"][:]
        require(im.shape == (128, 128, 14) and labels.shape == (128, 128), "Landslide4Sense shape")
        values, counts = np.unique(labels, return_counts=True)
        require(set(values) <= {0, 1}, "Landslide4Sense classes")
        pairs.append({"sample_id": ident, "image": image, "mask": mask, "image_array": array_summary(im), "label_counts": {str(int(v)): int(n) for v, n in zip(values, counts)}})
    reports.append({"id": "landslide-three-pairs", "source": "landslide4sense", "level": "paired_arrays_decoded", "details": {"samples": pairs, "limits": "No geospatial/time metadata inside these HDF5 chips; upstream event linkage and rainfall cause unresolved."}})

    caravan, wildfire = [], []
    for name, (member, data) in archive_members.items():
        if name.startswith("Caravan/timeseries/"):
            rs = list(csv.DictReader(io.StringIO(data.decode())))
            require(len(rs) >= 3 and "date" in rs[0] and "streamflow" in rs[0], "Caravan daily timeseries")
            good = [r for r in rs if r["streamflow"] and r["streamflow"].lower() != "nan"]
            require(len(good) >= 3, "Caravan flow values")
            for r in good[:3]:
                require(np.isfinite(float(r["streamflow"])), "Caravan finite flow")
            caravan.append({"name": name, "member": member, "rows": len(rs), "flow_rows": len(good), "columns": list(rs[0]), "examples": good[:3]})
        if re.match(r"\d{4}/fire_\d+/.*\.tif$", name):
            d = geotiff_sample(data)
            with rasterio.io.MemoryFile(data) as mem:
                with mem.open() as ds:
                    last = ds.read(ds.count)
                    values, counts = np.unique(last, return_counts=True)
                    d["last_band_raw_values"] = {str(float(v)): int(n) for v, n in zip(values, counts)} if len(values) < 100 else {"unique_values": len(values)}
            wildfire.append({"name": name, "member": member, **d})
    reports.append({"id": "caravan-three-basins", "source": "caravan", "level": "sample_decoded", "details": {"samples": caravan, "basins": len(caravan), "limits": "Daily basin records; original conventions and catchment metadata must be linked before flood thresholds."}})
    reports.append({"id": "wildfire-three-days", "source": "wildfirespreadts", "level": "arrays_decoded_label_semantics_pending", "details": {"samples": wildfire, "source_event_ids": sorted({r["name"].split('/')[1] for r in wildfire}), "limits": "Same-event daily files; numerical nodata/fire-mask interpretation must follow the author reader."}})

    for ident, source in [("tornet-three-prefix", "tornet"), ("senforflood-tar-prefix", "senforflood")]:
        spec, response, body = rows[ident]
        result = {"id": ident + "-members", "source": source, "level": "not_validated", "details": {"archive_complete": False, "members": []}}
        try:
            require(body and response["http_status"] == 206, "archive prefix not received")
            with tarfile.open(fileobj=io.BytesIO(body), mode="r|*") as tar:
                for m in tar:
                    if not m.isfile() or not m.name.endswith((".nc", ".tif")):
                        continue
                    require(m.size <= 48 * 1024**2, "archive member too large")
                    data = tar.extractfile(m).read(m.size + 1)
                    require(len(data) == m.size, "incomplete archive member")
                    details = netcdf_sample(data) if m.name.endswith(".nc") else geotiff_sample(data)
                    item = {"name": m.name, "bytes": len(data), "sha256": digest(data), "details": details}
                    if source == "tornet":
                        import netCDF4
                        with netCDF4.Dataset("sample", memory=data) as ds:
                            item["attributes"] = {k: str(ds.getncattr(k)) for k in ds.ncattrs()}
                    out = ROOT / "samples" / (source + "-" + str(len(result["details"]["members"])) + (".nc" if source == "tornet" else ".tif"))
                    out.write_bytes(data)
                    item["asset_path"] = str(out.relative_to(ROOT))
                    result["details"]["members"].append(item)
                    if len(result["details"]["members"]) == 3:
                        break
            require(len(result["details"]["members"]) == 3, "fewer than three complete members")
            result["level"] = "radar_samples_decoded" if source == "tornet" else "background_only_decoded"
        except Exception as exc:
            result.update(error_type=type(exc).__name__, error=str(exc))
        reports.append(result)

    geoid = []
    for index in range(3):
        parts = {}
        try:
            for role in ("pre", "post", "label", "validity"):
                ident = f"geoid-{role}-{index}"
                spec, response, body = rows[ident]
                require(response["complete"] and response["http_status"] == 200, "incomplete GEOID " + ident)
                parts[role] = geotiff_sample(body)
            ref = parts["post"]
            require(all(v["crs"] == ref["crs"] and v["transform"] == ref["transform"] and v["array"]["shape"][-2:] == ref["array"]["shape"][-2:] for v in parts.values()), "GEOID grids disagree")
            geoid.append({"tile_id": f"EMSR712-10-{index}", "status": "aligned", "parts": parts})
        except Exception as exc:
            geoid.append({"tile_id": f"EMSR712-10-{index}", "status": "incomplete", "error": str(exc), "parts": parts})
    reports.append({"id": "geoid-paired-check", "source": "geoid", "level": "paired_rasters_checked", "details": {"tiles": geoid, "parent_activation": "EMSR712", "limits": "One parent activation/AOI, not three independent floods; mirror payload provenance and validity derivation require separate checks."}})

    for ident in ["ts-satfire-sample-0", "ts-satfire-sample-1", "ts-satfire-sample-2"]:
        spec, response, body = rows[ident]
        r = {"id": ident + "-decoded", "source": "ts_satfire"}
        try:
            require(response["complete"] and response["http_status"] == 200, "TS-SatFire asset incomplete")
            r.update(level="sample_decoded", details=geotiff_sample(body))
        except Exception as exc:
            r.update(level="not_validated", error_type=type(exc).__name__, error=str(exc))
        reports.append(r)

    summary = {"schema": "offline_downloaded_validation_v1", "reports": reports,
               "new_model_calls": 0, "new_gpu_jobs": 0, "new_formal_benchmark_episodes": 0,
               "limits": "No global event-family count or whole-source admission is inferred from these checks."}
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    from collections import Counter
    print(json.dumps(dict(Counter(r["level"] for r in reports)), sort_keys=True))


if __name__ == "__main__":
    main()
