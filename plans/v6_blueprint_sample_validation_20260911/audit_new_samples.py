"""Decode the captured scientific samples without creating benchmark labels."""

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path

import eccodes
import netCDF4
import numpy as np
import rasterio
import shapefile
from PIL import Image


ROOT = Path(__file__).resolve().parent


def safe_json(value):
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, np.ndarray):
        value = value.tolist()
    if isinstance(value, float) and not math.isfinite(value):
        return {"nonfinite_metadata_value": str(value)}
    if isinstance(value, dict):
        return {k: safe_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe_json(v) for v in value]
    return value


def plain(value):
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return str(value)


def stats(values):
    data = np.ma.asarray(values, dtype=float)
    valid = data.compressed()
    valid = valid[np.isfinite(valid)]
    return {
        "shape": list(data.shape), "finite_unmasked": int(valid.size),
        "min": float(valid.min()) if valid.size else None,
        "max": float(valid.max()) if valid.size else None,
    }


def grib(raw):
    compressed = raw.startswith(b"\x1f\x8b")
    if compressed:
        raw = gzip.decompress(raw)
    if raw[:4] != b"GRIB" or raw[-4:] != b"7777" or int.from_bytes(raw[8:16], "big") != len(raw):
        raise ValueError("sample is not one complete GRIB2 message")
    handle = eccodes.codes_new_from_message(raw)
    try:
        metadata = {}
        for key in (
            "shortName", "name", "units", "year", "month", "day", "hour", "minute", "second",
            "stepType", "stepRange", "stepUnits", "typeOfLevel", "level", "Ni", "Nj",
            "numberOfDataPoints", "perturbationNumber", "numberOfForecastsInEnsemble",
            "discipline", "parameterCategory", "parameterNumber", "localTablesVersion",
            "bitmapPresent", "missingValue",
        ):
            try:
                metadata[key] = eccodes.codes_get(handle, key)
            except eccodes.CodesInternalError:
                pass
        values = eccodes.codes_get_values(handle)
        valid = values[np.isfinite(values) & (values != metadata.get("missingValue", np.nan))]
        metadata["values"] = stats(valid)
        metadata["negative_code_counts"] = {str(x): int((valid == x).sum()) for x in [-999, -99, -3, -2, -1] if (valid == x).any()}
        metadata["positive_values"] = int((valid > 0).sum())
        metadata["zero_values"] = int((valid == 0).sum())
        metadata["gzip_crc_checked"] = compressed
        metadata["semantic_limit"] = "Negative/local product codes and unknown local units require product-specific definitions; numerical decoding is not Gold admission."
        return metadata
    finally:
        eccodes.codes_release(handle)


def shape_archive(raw):
    output = []
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise ValueError("ZIP CRC failed: " + bad)
        names = archive.namelist()
        for name in names:
            if not name.lower().endswith(".shp"):
                continue
            base = name[:-4]
            index = {n.lower(): n for n in names}
            reader = shapefile.Reader(
                shp=io.BytesIO(archive.read(name)),
                shx=io.BytesIO(archive.read(index[base.lower() + ".shx"])),
                dbf=io.BytesIO(archive.read(index[base.lower() + ".dbf"])),
            )
            records = [x.as_dict() for x in reader.records()]
            prj = index.get(base.lower() + ".prj")
            output.append({
                "member": name, "records": len(records), "bbox": list(reader.bbox),
                "fields": [x[0] for x in reader.fields[1:]], "examples": records[:3],
                "projection": archive.read(prj).decode(errors="replace") if prj else None,
            })
    if not output:
        raise ValueError("no complete shapefile in archive")
    return {"zip_crc_checked": True, "layers": output}


def netcdf(raw):
    with netCDF4.Dataset("captured", memory=raw) as ds:
        result = {
            "dimensions": {k: len(v) for k, v in ds.dimensions.items()},
            "global_attributes": {k: ds.getncattr(k) for k in ds.ncattrs()}, "variables": {},
        }
        for name, variable in ds.variables.items():
            item = {"shape": list(variable.shape), "attributes": {k: variable.getncattr(k) for k in variable.ncattrs()}}
            if variable.dtype.kind in "fiu" and variable.size <= 5000000:
                item["statistics"] = stats(variable[:])
                if variable.size <= 25:
                    item["values"] = variable[:].filled(np.nan).tolist() if isinstance(variable[:], np.ma.MaskedArray) and variable.dtype.kind == "f" else np.asarray(variable[:]).tolist()
            elif variable.dtype.kind in "SU" and variable.size < 10000:
                item["text_sample"] = np.asarray(variable[:]).tolist()
            result["variables"][name] = item
        return result


def ghcnh(raw, tail=False):
    prefix = (ROOT / "captures_05/ghcnh-denver-prefix.body").read_bytes()
    header = prefix.split(b"\n", 1)[0].decode().rstrip("\r")
    if tail:
        raw = header.encode() + b"\n" + raw.split(b"\n", 1)[1]
    if not raw.endswith(b"\n"):
        raw = raw.rsplit(b"\n", 1)[0] + b"\n"
    table = list(csv.DictReader(io.StringIO(raw.decode()), delimiter="|"))
    if not table or any(None in row or any(value is None for value in row.values()) for row in table):
        raise ValueError("incomplete PSV rows")
    variables = ["temperature", "wind_speed", "wind_gust", "precipitation", "visibility", "snow_depth", "pres_wx_MW1", "pres_wx_AW1", "pres_wx_AU1"]
    details = {}
    for name in variables:
        populated = [r for r in table if r.get(name, "").strip()]
        details[name] = {
            "nonempty": len(populated), "first_values": [r[name] for r in populated[:5]],
            "quality_codes": dict(Counter(r.get(name + "_Quality_Code", "") for r in populated)),
        }
    return {
        "complete_rows_in_requested_byte_sample": len(table), "whole_station_file": False,
        "station_ids": sorted({r["STATION"] for r in table}),
        "time_min": min(r["DATE"] for r in table), "time_max": max(r["DATE"] for r in table),
        "column_count": len(table[0]), "fields": details,
        "examples": [{k: r.get(k) for k in ["STATION", "DATE", "LATITUDE", "LONGITUDE", "temperature", "wind_speed", "visibility", "temperature_Quality_Code"]} for r in table[:3]],
        "limits": "Raw provider values/QC retained; no ISD decoder reuse or new extreme-event labels. Partial edge rows discarded."
    }


def aviation(raw, taf=False):
    rows = json.loads(raw)
    if not rows or not all("icaoId" in r for r in rows):
        raise ValueError("no aviation records with station identity")
    keep = ["icaoId", "issueTime", "validTimeFrom", "validTimeTo", "rawTAF", "fcsts"] if taf else ["icaoId", "obsTime", "reportTime", "receiptTime", "rawOb", "temp", "dewp", "wdir", "wspd", "wgst", "visib", "wxString"]
    return {
        "records": len(rows), "station_ids": sorted({r["icaoId"] for r in rows}),
        "examples": [{k: r.get(k) for k in keep} for r in rows[:3]],
        "limits": "TAF change/probability groups need explicit interpretation; live rolling samples do not prove historical archive availability."
    }


def petss(raw):
    text = raw.decode()
    stations = []
    current = None
    for line in text.splitlines()[3:]:
        # The bulletin includes both numeric gauge IDs and lower-case est IDs.
        if len(line) > 12 and line[0] == " " and re.fullmatch(r"[A-Za-z0-9]{7}", line[1:8]) and line[8] == " " and re.search(r"[A-Za-z]", line[9:]):
            fields = line[9:].rsplit(None, 1)
            current = {"station_id": line[1:8], "name": fields[0], "trailing_header_code_uninterpreted": fields[-1], "raw_tenths_ft": []}
            stations.append(current)
        elif current is not None and line.strip() and re.fullmatch(r"[\s\d-]+", line):
            current["raw_tenths_ft"].extend(int(line[i:i + 4]) for i in range(0, len(line.rstrip()), 4))
        elif line.strip():
            raise ValueError("unrecognized bulletin line: " + line)
    if not stations:
        raise ValueError("no station blocks")
    if len({s["station_id"] for s in stations}) != len(stations):
        raise ValueError("duplicate bulletin station IDs")
    if any(len(s["raw_tenths_ft"]) != 102 for s in stations):
        raise ValueError("sample station does not contain the expected 102 numerical fields")
    values = [x for s in stations for x in s["raw_tenths_ft"]]
    return {
        "header": text.splitlines()[:3], "station_blocks": len(stations),
        "numeric_station_ids": sum(s["station_id"].isdigit() for s in stations),
        "estimated_location_ids": sum(s["station_id"].startswith("est") for s in stations),
        "values_per_station": dict(Counter(len(s["raw_tenths_ft"]) for s in stations)),
        "negative_400_code_count_uninterpreted": values.count(-400), "examples": stations[:2],
        "explicit_tropical_exclusion": "NOT VALID FOR TROPICAL STORM" in text,
        "limits": "Retain special codes; datum, hour alignment and e10 probability convention must be matched before outcome comparison."
    }


def iem(raw):
    rows = list(csv.DictReader(io.StringIO(raw.decode())))
    counts = Counter()
    examples = []
    for row in rows:
        tokens = row["metar"].split(" RMK ", 1)[0].split()
        phenomena = sorted({t.lstrip("+-") for t in tokens if t.lstrip("+-") in {"FZRA", "FZDZ", "DS", "SS", "BLDU", "BLSA", "FG", "FZFG"}})
        counts.update(phenomena)
        if phenomena and len(examples) < 4:
            examples.append({**row, "weather_tokens_before_remarks": phenomena})
    return {
        "rows": len(rows), "stations": sorted({r["station"] for r in rows}),
        "start": min(r["valid"] for r in rows), "end": max(r["valid"] for r in rows),
        "phenomenon_record_counts": dict(counts), "examples": examples,
        "limits": "IEM historical METAR archive, not a new independent sensor; exclude RMK/vicinity mentions from station-weather token counts. These selected historical cases are development-exposed."
    }


def radar(path):
    # CPU parsing does not need the host's incompatible optional CuPy backend.
    sys.modules["cupy"] = None
    from metpy.io import Level2File
    volume = Level2File(str(path))
    moments = Counter()
    samples = []
    for sweep in volume.sweeps:
        for ray in sweep:
            moments.update(k.decode() for k in ray[-1])
        if sweep and b"REF" in sweep[0][-1]:
            header, values = sweep[0][-1][b"REF"]
            samples.append({"header": str(header), "first_radial_statistics": stats(values)})
    return {
        "volume_time": volume.dt.isoformat(), "sweeps": len(volume.sweeps),
        "rays_per_sweep": [len(s) for s in volume.sweeps], "radials_with_moment": dict(moments),
        "reflectivity_examples": samples[:3],
        "limits": "MetPy reports unknown message 32; reflectivity/polarimetric radial arrays decode, but not every message is interpreted or scientifically QC-certified."
    }


def decode(record, path):
    ident = record["id"]
    if record.get("assembly"):
        return None
    raw = path.read_bytes()
    if ident.startswith("ghcnh-denver-") and not ident.endswith("list"):
        return "station_rows_decoded", ghcnh(raw, tail=ident.endswith("tail"))
    if ident in {"metar-json", "taf-json"}:
        return "aviation_rows_decoded", aviation(raw, ident == "taf-json")
    if ident.startswith("petss-") and ident.endswith("sample"):
        return "forecast_station_table_decoded", petss(raw)
    if ident == "nexrad-sample":
        return "radar_moments_decoded", radar(path)
    if ident in {"iem-freezing-rain", "iem-dust-storm"}:
        return "historical_metar_phenomena_decoded", iem(raw)
    if raw.startswith(b"GRIB") or ident in {"mrms-mesh-sample", "mrms-qpe-sample"}:
        return "grib_values_decoded", grib(raw)
    if raw.startswith(b"PK") and ident in {"spc-day1-shapes", "cpc-seasonal-complete"}:
        return "forecast_shapes_decoded", shape_archive(raw)
    if raw.startswith(b"\x89HDF") or raw[:3] == b"CDF":
        return "netcdf_values_decoded", netcdf(raw)
    if ident == "eddi-grid":
        with rasterio.io.MemoryFile(raw) as memory, memory.open(driver="AAIGrid") as ds:
            return "drought_index_grid_decoded", {"driver": ds.driver, "bounds": list(ds.bounds), "crs": str(ds.crs), "nodata": ds.nodata, "values": stats(ds.read(1, masked=True)), "aggregation": "01mn as encoded in the selected source filename; not a flash-drought label"}
    if ident in {"gwis-fwi-map", "wpc-qpf-index"}:
        with Image.open(io.BytesIO(raw)) as im:
            im.load()
            return "rendered_product_only", {"format": im.format, "size": list(im.size), "mode": im.mode, "limits": "Rendered map is not a raw forecast grid; issue time and pixel-to-value semantics not independently established."}
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("audit output must be new")
    reports = []
    for manifest in sorted(ROOT.glob("captures_*/MANIFEST.json")):
        for record in json.loads(manifest.read_text()):
            if record["status"] != "received" or not record.get("raw"):
                continue
            path = manifest.parent / record["raw"]
            if hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
                raise ValueError("raw sample changed: " + str(path))
            result = {"capture_id": record["id"], "source": record["source"], "raw_path": str(path.relative_to(ROOT)), "sha256": record["sha256"]}
            try:
                decoded = decode(record, path)
                if decoded is None:
                    continue
                result.update(level=decoded[0], details=decoded[1])
            except Exception as exc:
                result.update(level="decode_failed", error=type(exc).__name__ + ": " + str(exc))
            reports.append(result)
            print(json.dumps({k: result[k] for k in ("capture_id", "level", "error") if k in result}), flush=True)
    assembly_path = ROOT / "ASSEMBLY_MANIFEST.json"
    if assembly_path.exists():
        for item in json.loads(assembly_path.read_text()):
            path = ROOT / item["path"]
            raw = path.read_bytes()
            if len(raw) != item["bytes"] or hashlib.sha256(raw).hexdigest() != item["sha256"]:
                raise ValueError("assembled sample changed")
            result = {"capture_id": item["id"], "source": "OFS" if path.suffix == ".nc" else "CPC", "raw_path": item["path"], "sha256": item["sha256"]}
            try:
                result.update(level="assembled_netcdf_decoded" if path.suffix == ".nc" else "assembled_shapes_decoded", details=netcdf(raw) if path.suffix == ".nc" else shape_archive(raw))
            except Exception as exc:
                result.update(level="decode_failed", error=type(exc).__name__ + ": " + str(exc))
            reports.append(result)
            print(json.dumps({k: result[k] for k in ("capture_id", "level", "error") if k in result}), flush=True)
    report = safe_json({"reports": reports, "formal_new_tasks": 0, "new_model_calls": 0})
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=plain, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
