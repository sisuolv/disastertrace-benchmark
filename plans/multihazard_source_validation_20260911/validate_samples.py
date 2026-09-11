"""Reconstruct sample checks from saved responses without network access."""

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import re
import tarfile
import zipfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def require(condition, message):
    if not condition:
        raise ValueError(message)


def captures():
    result = {}
    for specfile in sorted((ROOT / "specs").glob("*.json")):
        for spec in json.loads(specfile.read_text())["probes"]:
            path = ROOT / "batches" / specfile.stem / (spec["id"] + ".json")
            if not path.exists():
                continue
            record = json.loads(path.read_text())
            response = record.get("final", {})
            body = (ROOT / response["attempt_path"] / "body.bin").read_bytes() if response else b""
            if response:
                require(hashlib.sha256(body).hexdigest() == response["body_sha256"], "capture hash mismatch")
            require(spec["id"] not in result, "duplicate probe ID")
            result[spec["id"]] = (spec, response, body)
    return result


def csv_rows(body, delimiter=","):
    reader = csv.DictReader(io.StringIO(body.decode("utf-8-sig")), delimiter=delimiter)
    rows = list(reader)
    require(rows and None not in rows[0], "empty CSV or invalid header")
    return rows


def scalar(value):
    result = float(value)
    require(math.isfinite(result), "nonfinite number")
    return result


def array_summary(array):
    import numpy as np
    a = np.ma.asarray(array)
    if a.dtype.kind not in "biuf":
        return {"shape": list(a.shape), "dtype": str(a.dtype), "examples": a.reshape(-1)[:3].astype(str).tolist()}
    good = np.isfinite(a.filled(float("nan")) if a.dtype.kind == "f" else a.data) & ~np.ma.getmaskarray(a)
    values = np.asarray(a)[good]
    return {"shape": list(a.shape), "dtype": str(a.dtype), "valid_values": int(good.sum()),
            "masked_values": int(np.ma.getmaskarray(a).sum()),
            "min": float(values.min()) if values.size else None,
            "max": float(values.max()) if values.size else None}


def netcdf_sample(body):
    import netCDF4
    with netCDF4.Dataset("capture.nc", memory=body) as dataset:
        variables = {}
        for name, var in dataset.variables.items():
            if var.size > 50_000_000:
                variables[name] = {"shape": list(var.shape), "not_decoded": "size_limit"}
                continue
            variables[name] = {**array_summary(var[:]), "dimensions": list(var.dimensions),
                               "units": getattr(var, "units", None),
                               "long_name": getattr(var, "long_name", None)}
        require(variables, "no NetCDF variables")
        return {"dimensions": {k: len(v) for k, v in dataset.dimensions.items()}, "variables": variables}


def geotiff_sample(body):
    import numpy as np
    import rasterio
    with rasterio.io.MemoryFile(body) as mem:
        with mem.open() as ds:
            require(ds.crs and ds.width > 1 and ds.height > 1, "raster spatial metadata")
            array = ds.read(masked=True)
            result = {"crs": str(ds.crs), "transform": list(ds.transform), "nodata": ds.nodata,
                      "bounds": list(ds.bounds), "descriptions": list(ds.descriptions), "array": array_summary(array)}
            if ds.count <= 2 and array.dtype.kind in "iu":
                values, counts = np.unique(array.data, return_counts=True)
                if len(values) < 100:
                    result["raw_value_counts"] = {str(int(v)): int(n) for v, n in zip(values, counts)}
            return result


def validate(spec, response, body):
    kind = spec["kind"]
    require(response.get("http_status") in (200, 206), "HTTP request unsuccessful")
    require(response.get("complete") and body, "incomplete or empty response")
    if spec.get("git_blob_sha1"):
        actual = hashlib.sha1(b"blob " + str(len(body)).encode() + b"\0" + body).hexdigest()
        require(actual == spec["git_blob_sha1"], "Git blob differs from captured repository tree")
    if kind == "ghcnd":
        rows = json.loads(body)
        require(len(rows) >= 3, "fewer than three station days")
        require(all(r["STATION"] == spec["station"] and spec["start"] <= r["DATE"] <= spec["end"] for r in rows), "station/date filter mismatch")
        require(len({r["DATE"] for r in rows}) == len(rows), "duplicate station day")
        metrics = {}
        for field in ("TMAX", "TMIN", "PRCP", "SNOW", "SNWD"):
            present = [r for r in rows if field in r]
            accepted = [r for r in present if len(r.get(field + "_ATTRIBUTES", "").split(",")) >= 3 and not r[field + "_ATTRIBUTES"].split(",")[1]]
            vals = [scalar(r[field]) for r in accepted]
            if vals:
                metrics[field] = {"records": len(present), "empty_qflag_records": len(vals), "min": min(vals), "max": max(vals),
                                  "trace_records": sum(r[field + "_ATTRIBUTES"].split(",")[0] == "T" for r in accepted)}
        require(metrics, "no QC-readable values")
        return "sample_decoded", {"records": len(rows), "station": rows[0]["STATION"], "name": rows[0].get("NAME"), "latitude": scalar(rows[0]["LATITUDE"]), "longitude": scalar(rows[0]["LONGITUDE"]), "variables": metrics, "examples": rows[:3], "time_semantics": "station calendar day; not asserted UTC interval"}
    if kind == "isd":
        rows = csv_rows(body)
        require({"STATION", "DATE", "WND", "VIS", "TMP"} <= rows[0].keys(), "ISD fields absent")
        stations = sorted({r["STATION"] for r in rows})
        require(len(stations) == 1 and len(rows) >= 3, "ISD station sample")
        for r in rows[:3]:
            datetime.fromisoformat(r["DATE"])
            require(-90 <= scalar(r["LATITUDE"]) <= 90 and -180 <= scalar(r["LONGITUDE"]) <= 180, "coordinates")
        stats = {}
        for field, ix, missing, scale in [("TMP", 0, 9999, 0.1), ("VIS", 0, 999999, 1), ("WND", 3, 9999, 0.1)]:
            good = []
            for r in rows:
                parts = r[field].split(",")
                if len(parts) <= ix + 1:
                    continue
                raw = int(parts[ix])
                if raw != missing and parts[ix + 1] in {"0", "1", "4", "5"}:
                    good.append(raw * scale)
            stats[field] = {"QC_accepted_values": len(good), "min": min(good) if good else None, "max": max(good) if good else None}
        codes = Counter(r.get("MW1", "").split(",")[0] for r in rows if r.get("MW1"))
        examples = [{k: r.get(k) for k in ("STATION", "DATE", "LATITUDE", "LONGITUDE", "WND", "VIS", "TMP", "MW1", "AW1")} for r in rows[:3]]
        return "sample_decoded", {"records": len(rows), "stations": stations, "distinct_times": len({r["DATE"] for r in rows}), "variables": stats, "manual_weather_codes": dict(codes), "examples": examples, "limits": "Multiple reports at one time are retained; weather codes and missing sentinels require product interpretation."}
    if kind == "usgs":
        rows = json.loads(body)["features"]
        require(len(rows) >= 3 and len({r["id"] for r in rows}) == len(rows), "three distinct USGS records required")
        for row in rows:
            r = row["properties"]
            require(r["monitoring_location_id"] == spec["station"] and r["parameter_code"] == "00060", "USGS query filter")
            scalar(r["value"])
            datetime.fromisoformat(r["time"])
            require(r["unit_of_measure"] == "ft^3/s" and row.get("geometry"), "unit/geometry")
        return "sample_decoded", {"records": len(rows), "examples": rows[:3], "time_semantics": "returned dates, not assumed latest or consecutive"}
    if kind == "nwps":
        obj = json.loads(body)
        details = {}
        for name in ("observed", "forecast"):
            block = obj.get(name, {})
            rows = block.get("data", [])
            if rows:
                datetime.fromisoformat(block["issuedTime"].replace("Z", "+00:00"))
                for r in rows[:3]:
                    datetime.fromisoformat(r["validTime"].replace("Z", "+00:00"))
                    scalar(r["primary"])
            details[name] = {"records": len(rows), "issued_time": block.get("issuedTime"), "primary_units": block.get("primaryUnits"), "secondary_units": block.get("secondaryUnits"), "missing_primary_minus999": sum(r["primary"] == -999 for r in rows), "missing_secondary_minus999": sum(r.get("secondary") == -999 for r in rows), "examples": rows[:3]}
        require(details["observed"]["records"] >= 3, "no NWPS observations")
        return "sample_decoded", details
    if kind == "coops":
        obj = json.loads(body)
        rows = obj.get("data", obj.get("predictions", []))
        require(len(rows) >= 3, "no water-level samples")
        if spec["product"] == "water_level":
            require(obj["metadata"]["id"] == spec["station"], "CO-OPS station mismatch")
        values = [scalar(r["v"]) for r in rows if r["v"]]
        require(len(values) >= 3, "not enough numeric water levels")
        require(len({r["t"] for r in rows}) == len(rows), "duplicate water-level time")
        return "sample_decoded", {"records": len(rows), "station": spec["station"], "datum": "MLLW", "units": "m", "time_zone": "GMT", "min": min(values), "max": max(values), "examples": rows[:3]}
    if kind == "ndbc":
        lines = body.decode().splitlines()
        header = lines[0].split()
        require(header[0] == "#YY" and "WVHT" in header, "NDBC columns")
        rows = [dict(zip(header, r.split())) for r in lines[2:] if r.strip()]
        good = [r for r in rows if r.get("WVHT") not in (None, "MM")]
        require(len(good) >= 3, "not enough wave measurements")
        vals = [scalar(r["WVHT"]) for r in good]
        return "sample_decoded", {"records": len(rows), "wave_records": len(good), "wave_height_m_min": min(vals), "wave_height_m_max": max(vals), "examples": good[:3]}
    if kind == "netcdf":
        return "sample_decoded", netcdf_sample(body)
    if kind == "geotiff":
        return "sample_decoded", geotiff_sample(body)
    if kind == "grib_range":
        import eccodes
        match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", response["headers"].get("content-range", ""))
        require(response["http_status"] == 206 and match is not None, "complete GRIB message range required")
        start, end, total = map(int, match.groups())
        require(f"bytes={start}-{end}" == spec["range"] and len(body) == end - start + 1, "GRIB range mismatch")
        require(body[:4] == b"GRIB" and body[-4:] == b"7777", "GRIB framing")
        require(int.from_bytes(body[8:16], "big") == len(body), "GRIB2 message length")
        gid = eccodes.codes_new_from_message(body)
        try:
            attrs = {key: eccodes.codes_get(gid, key) for key in ["shortName", "name", "units", "dataDate", "dataTime", "validityDate", "validityTime", "typeOfLevel", "level", "numberOfPoints"]}
            values = eccodes.codes_get_values(gid)
            require(len(values) == attrs["numberOfPoints"], "GRIB point count")
            return "sample_decoded", {"metadata": attrs, "array": array_summary(values), "sample_unit": "one forecast/analysis variable field, not an independent event"}
        finally:
            eccodes.codes_release(gid)
    if kind == "storm_events":
        rows = csv_rows(gzip.decompress(body))
        require({"EVENT_ID", "EPISODE_ID", "EVENT_TYPE", "BEGIN_DATE_TIME", "CZ_TIMEZONE"} <= rows[0].keys(), "Storm Events schema")
        count = Counter(r["EVENT_TYPE"] for r in rows)
        examples, seen = defaultdict(list), defaultdict(set)
        for r in rows:
            kind_name = r["EVENT_TYPE"]
            if len(examples[kind_name]) < 3 and r["EPISODE_ID"] not in seen[kind_name]:
                examples[kind_name].append({k: r[k] for k in ("EVENT_ID", "EPISODE_ID", "EVENT_TYPE", "STATE", "BEGIN_DATE_TIME", "END_DATE_TIME", "CZ_TIMEZONE", "BEGIN_LAT", "BEGIN_LON", "MAGNITUDE", "MAGNITUDE_TYPE", "TOR_F_SCALE")})
                seen[kind_name].add(r["EPISODE_ID"])
        return "catalog_records_decoded", {"records": len(rows), "distinct_record_ids": len({r["EVENT_ID"] for r in rows}), "published_episode_ids": len({r["EPISODE_ID"] for r in rows}), "type_counts": dict(sorted(count.items())), "examples_per_type": dict(sorted(examples.items())), "time_semantics": "retrospective event report with local zone; publication/availability not established"}
    if kind == "hanze":
        rows = csv_rows(body)
        require({"ID", "Start date", "End date", "Type", "Country code", "References"} <= rows[0].keys(), "HANZE schema")
        for r in rows[:3]:
            datetime.fromisoformat(r["Start date"])
        return "catalog_records_decoded", {"records": len(rows), "countries": len({r["Country code"] for r in rows}), "types": dict(Counter(r["Type"] for r in rows)), "examples": rows[:3]}
    if kind == "dheed":
        with zipfile.ZipFile(io.BytesIO(body)) as z:
            name = "MergedEventStats_landonly_int.csv"
            rows = csv_rows(z.read(name))
        require({"label", "start_time", "end_time", "longitude_min", "heat", "compound"} <= rows[0].keys(), "Dheed schema")
        for row in rows[:3]:
            datetime.strptime(row["start_time"], "%Y-%m-%dT%H:%M:%S.%f")
            require(0 <= scalar(row["longitude_min"]) <= 360, "Dheed longitude convention")
        return "derived_event_records_decoded", {"records": len(rows), "examples": rows[:3], "reference_kind": "source-derived hot/dry event catalogue, not independent station truth"}
    if kind == "ibtracs":
        rows = csv_rows(body)
        units, rows = rows[0], rows[1:]
        require({"SID", "ISO_TIME", "LAT", "LON", "BASIN"} <= units.keys(), "IBTrACS schema")
        selected, seen = [], set()
        for r in rows:
            if r["SID"] not in seen and len(selected) < 3:
                datetime.fromisoformat(r["ISO_TIME"])
                scalar(r["LAT"]); scalar(r["LON"])
                selected.append({k: r[k] for k in ("SID", "NAME", "BASIN", "ISO_TIME", "LAT", "LON", "WMO_WIND", "WMO_PRES", "USA_WIND")})
                seen.add(r["SID"])
        require(len(selected) == 3, "IBTrACS distinct storms")
        return "sample_decoded", {"records": len(rows), "storm_ids": len({r["SID"] for r in rows}), "basins": dict(Counter(r["BASIN"] for r in rows)), "examples": selected, "limits": "Best-track agency conventions and provisional records preserved; no public input eligibility established."}
    if kind == "firms":
        rows = csv_rows(body)
        require({"latitude", "longitude", "acq_date", "confidence"} <= rows[0].keys(), "FIRMS schema")
        for r in rows[:3]:
            scalar(r["latitude"]); scalar(r["longitude"])
        require(len(rows) >= 3, "fewer than three fire detections")
        return "sample_decoded", {"records": len(rows), "examples": rows[:3], "limits": "Detections do not prove wildfire extent or absence outside detections."}
    if kind == "snodas":
        import numpy as np
        with tarfile.open(fileobj=io.BytesIO(body), mode="r:") as archive:
            names = archive.getnames()
            data_name = next(n for n in names if "ssmv11034" in n and n.endswith(".dat.gz"))
            hdr_name = data_name.replace(".dat.gz", ".txt.gz")
            header = gzip.decompress(archive.extractfile(hdr_name).read()).decode()
            raw = gzip.decompress(archive.extractfile(data_name).read())
        def field(name):
            match = re.search(r"^\s*" + re.escape(name) + r"\s*:\s*(.+)$", header, re.M | re.I)
            require(match, "SNODAS header missing " + name)
            return match.group(1).strip()
        rows, cols = int(field("Number of rows")), int(field("Number of columns"))
        require(len(raw) == rows * cols * 2, "SNODAS byte count")
        require("16" in field("Data bytes per pixel") or field("Data bytes per pixel") == "2", "SNODAS numeric encoding")
        arr = np.frombuffer(raw, dtype=">i2").reshape(rows, cols)
        require(int(arr.max()) == int(float(field("Maximum data value"))), "SNODAS header/value or endian mismatch")
        return "sample_decoded", {"member": data_name, "header": header, "array": array_summary(np.ma.masked_equal(arr, -9999)), "limits": "Snow water equivalent analysis; not a direct blizzard label."}
    if kind == "repo_asset":
        name = spec["repo_path"]
        if spec["source"] == "ewb" and name.endswith("events.yaml"):
            import yaml
            obj = yaml.safe_load(body)
            require(isinstance(obj, list) and len(obj) >= 3, "EWB event list")
            require(len({r["case_id_number"] for r in obj}) == len(obj), "duplicate EWB case IDs")
            examples = defaultdict(list)
            for r in obj:
                require(r["start_date"] <= r["end_date"] and r.get("location"), "EWB event time/location")
                if len(examples[r["event_type"]]) < 3:
                    examples[r["event_type"]].append({**r, "start_date": r["start_date"].isoformat(), "end_date": r["end_date"].isoformat()})
            return "benchmark_case_definitions_decoded", {"records": len(obj), "type_counts": dict(Counter(r["event_type"] for r in obj)), "examples_per_type": dict(examples)}
        if spec["source"] == "cllmate" and name.endswith(".json"):
            obj = json.loads(body)
            require(isinstance(obj, dict) and len(obj) >= 3, "CLLMate node dictionary")
            selected = {k: v for k, v in obj.items() if v.get("event") in {"heavy rainfall", "typhoon", "heatwave", "drought", "snowstorm"}}
            for r in list(selected.values())[:3]:
                datetime.strptime(r["time"], "%Y/%m/%d")
                require(len(r["coordinate"].split(",")) == 4, "CLLMate region bounds")
            return "benchmark_records_decoded", {"records": len(obj), "selected_weather_nodes": len(selected), "examples": dict(list(selected.items())[:3]), "limits": "Event/causal graph metadata only; image files and independent causal truth not verified."}
        if name.endswith(".csv"):
            rows = csv_rows(body)
            if spec["source"] == "meteonet":
                require({"number_sta", "date", "lat", "lon", "t", "precip"} <= rows[0].keys(), "MeteoNet station columns")
                selected = [r for r in rows if r["t"] and r["precip"]][:3]
                require(len(selected) == 3, "MeteoNet numeric observations")
                for r in selected:
                    datetime.strptime(r["date"], "%Y%m%d %H:%M")
                    scalar(r["lat"]); scalar(r["lon"]); scalar(r["t"]); scalar(r["precip"])
                return "sample_decoded", {"records": len(rows), "stations": len({r["number_sta"] for r in rows}), "times": len({r["date"] for r in rows}), "columns": list(rows[0]), "examples": selected}
            level = "sample_decoded" if spec["source"] == "meteonet" else "catalog_records_decoded"
            return level, {"records": len(rows), "columns": list(rows[0]), "examples": rows[:3]}
        if name.endswith(".nc"):
            return "sample_decoded", netcdf_sample(body)
        if name.endswith(".npz"):
            import numpy as np
            arrays = {}
            with zipfile.ZipFile(io.BytesIO(body)) as z:
                for member in z.namelist():
                    with z.open(member) as stream:
                        version = np.lib.format.read_magic(stream)
                        shape, order, dtype = np.lib.format._read_array_header(stream, version)
                    if dtype.hasobject:
                        arrays[member] = {"shape": list(shape), "dtype": str(dtype), "not_decoded": "object array requires pickle; not executed"}
                    else:
                        arrays[member] = array_summary(np.load(io.BytesIO(z.read(member)), allow_pickle=False))
            require(any(v.get("valid_values", 0) for v in arrays.values()), "no decoded numeric array")
            return "array_values_decoded_time_unresolved", {"arrays": arrays}
        return "reference_material", {"git_blob_verified": bool(spec.get("git_blob_sha1"))}
    return "not_a_validated_sample", {"kind": kind}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = ROOT / args.output
    require(not output.exists(), "use a new report path")
    reports = []
    for ident, (spec, response, body) in captures().items():
        result = {"id": ident, "source": spec.get("source"), "kind": spec["kind"], "response": response.get("attempt_path"), "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body), "benchmark_admitted": False}
        try:
            level, details = validate(spec, response, body)
            result.update(level=level, details=details)
        except Exception as exc:
            result.update(level="not_validated", error_type=type(exc).__name__, error=str(exc))
        reports.append(result)
    output.write_text(json.dumps({"schema": "saved_sample_checks_v1", "reports": reports}, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps(dict(Counter(r["level"] for r in reports)), sort_keys=True))


if __name__ == "__main__":
    main()
