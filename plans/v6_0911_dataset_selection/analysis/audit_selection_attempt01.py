"""Reproduce V6 sample checks using captured bytes only, without external code execution."""

import base64
import csv
import hashlib
import io
import json
import re
import struct
import sys
import zipfile
import zlib
from collections import Counter
from datetime import datetime
from pathlib import Path

import netCDF4
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import rasterio
from PIL import Image

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
PRIOR = ROOT.parent / "multihazard_source_validation_20260911"
V5 = ROOT.parent / "v5_0910_source_probe_20260910"
sys.path.insert(0, str(PRIOR))
from validate_samples import captures, geotiff_sample, netcdf_sample, require


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_text())


def collect(root):
    specs = {s["id"]: s for p in root.glob("specs/*.json") for s in read(p).get("probes", [])}
    result = {}
    for path in sorted(root.glob("batches/*/*.json")):
        r = read(path)
        if "final" not in r:
            continue
        spec = specs.get(r["id"], {"id": r["id"], "kind": r["kind"], "url": r["requested_url"]})
        response = r["final"]
        body = (root / response["attempt_path"] / "body.bin").read_bytes()
        require(sha(body) == response["body_sha256"], "capture hash mismatch")
        require(len(body) == response["captured_bytes"], "capture size mismatch")
        result[r["id"]] = spec, response, body
    return result


class CapturedRanges(io.RawIOBase):
    """A local sparse reader that refuses access to bytes never downloaded."""

    def __init__(self, length, blocks):
        self.length, self.blocks, self.pos = length, blocks, 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        self.pos = offset if whence == 0 else self.pos + offset if whence == 1 else self.length + offset
        require(0 <= self.pos <= self.length, "seek outside object")
        return self.pos

    def read(self, size=-1):
        size = min(size if size >= 0 else self.length - self.pos, self.length - self.pos)
        for start, data in self.blocks:
            if start <= self.pos and self.pos + size <= start + len(data):
                result = data[self.pos - start:self.pos - start + size]
                self.pos += size
                return result
        raise ValueError("read of uncaptured bytes")


def main():
    rows = collect(ROOT)
    old = captures()
    refs = ROOT / "references"
    refs.mkdir(exist_ok=True)
    reports = []

    def checked(ident):
        spec, response, body = rows[ident]
        require(response["complete"] and response["http_status"] in (200, 206) and body, "incomplete HTTP asset: " + ident)
        return body

    def check(ident, source, func):
        result = {"id": ident, "source": source, "level": "not_validated"}
        try:
            result["details"] = func()
            result["level"] = "verified"
        except Exception as exc:
            result.update(error_type=type(exc).__name__, error=str(exc))
        reports.append(result)

    for ident, (spec, response, body) in rows.items():
        if spec["kind"] == "github_blob" and response["complete"] and response["http_status"] == 200:
            obj = json.loads(body)
            raw = base64.b64decode(obj["content"])
            blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
            require(blob == obj["sha"] == spec["url"].rsplit("/", 1)[-1], "Git blob verification")
            (refs / (ident + ".bin")).write_bytes(raw)

    def lightning():
        samples = []
        for i in range(3):
            ident = f"D10-glm-{i}"
            data = checked(ident)
            with netCDF4.Dataset("glm", memory=data) as ds:
                entry = {"capture_id": ident, "sha256": sha(data), "start": ds.time_coverage_start,
                         "end": ds.time_coverage_end, "counts": {}, "quality_flags": {}}
                for unit in ["flash", "group", "event"]:
                    values = ds[unit + "_id"][:]
                    entry["counts"][unit] = len(values)
                    require(len(np.unique(values)) == len(values), "duplicate GLM ID within product")
                for child, parent in [("event", "group"), ("group", "flash")]:
                    require(np.isin(ds[f"{child}_parent_{parent}_id"][:], ds[parent + "_id"][:]).all(), "GLM parent missing")
                for unit in ["flash", "group"]:
                    values, counts = np.unique(ds[unit + "_quality_flag"][:], return_counts=True)
                    entry["quality_flags"][unit] = {str(int(v)): int(c) for v, c in zip(values, counts)}
                samples.append(entry)
        return {"samples": samples, "unit": "three consecutive 20-second GLM files", "extreme_lightning_confirmed": False,
                "limits": "Density baseline, spatial grouping, duplicate boundary flashes and extreme thresholds remain to be defined."}

    check("glm-three-products", "D10", lightning)

    def coldwave():
        data = checked("D47-coldwave-pinned")
        require(sha(data) == rows["D47-coldwave-pinned"][0]["expected_sha256"], "HF linked checksum mismatch")
        samples = []
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            require(sum(m.file_size for m in z.infolist()) < 16 * 1024**2, "archive expansion cap")
            require(z.testzip() is None, "ZIP CRC")
            for name in sorted(n for n in z.namelist() if n.endswith(".nc")):
                raw = z.read(name)
                with netCDF4.Dataset("coldwave", memory=raw) as ds:
                    require(ds["t2m"].units == "K", "t2m units")
                    arr = ds["t2m"][:]
                    dates = netCDF4.num2date(ds["time"][:], ds["time"].units)
                    times = [d.strftime("%Y-%m-%d") for d in dates]
                    seq_name = name[:-3] + "_sequence.csv"
                    seq = list(csv.DictReader(io.StringIO(z.read(seq_name).decode())))
                    require([r["date"] for r in seq] == times, "sequence date mismatch")
                    require(np.isfinite(arr).all(), "nonfinite coldwave array")
                    samples.append({"case_id": name.split("/")[1], "member": name, "sha256": sha(raw),
                                    "shape": list(arr.shape), "time_steps": len(times), "start": times[0], "end": times[-1],
                                    "units": "K", "min": float(arr.min()), "max": float(arr.max()),
                                    "bbox": [float(ds["longitude"][:].min()), float(ds["latitude"][:].min()),
                                             float(ds["longitude"][:].max()), float(ds["latitude"][:].max())],
                                    "sequence_rows": len(seq)})
            return {"sha256": sha(data), "hf_commit": rows["D47-coldwave-pinned"][0]["revision"],
                    "members": len(z.infolist()), "file_members": sum(not m.is_dir() for m in z.infolist()),
                    "uncompressed_bytes": sum(m.file_size for m in z.infolist()), "samples": samples,
                    "source_case_ids": len(samples), "deduplicated_event_families": None,
                    "time_steps": sum(s["time_steps"] for s in samples), "countries_by_case_suffix": sorted({s["case_id"].split("-")[-1] for s in samples}),
                    "limits": "Country-disaster IDs are source cases, not independently verified synoptic systems. ERA5 field lineage, event extrema definitions and EM-DAT derivative rights need checking."}

    check("exebench-coldwave", "D47", coldwave)

    def drought():
        data = checked("D52-train-prefix-encoded")
        require(data[:4] == b"PK\x03\x04" and struct.unpack_from("<H", data, 8)[0] == 8, "ZIP deflate local header")
        n, e = struct.unpack_from("<HH", data, 26)
        name = data[30:30 + n].decode()
        dec = zlib.decompressobj(-15)
        raw = dec.decompress(data[30 + n + e:], 16 * 1024**2)
        raw = raw[:raw.rfind(b"\n") + 1]
        rs = list(csv.DictReader(io.StringIO(raw.decode())))
        require({"fips", "date", "T2M", "PRECTOT", "score"} <= rs[0].keys(), "DroughtED schema")
        for r in rs:
            datetime.fromisoformat(r["date"])
            require(np.isfinite(float(r["T2M"])), "temperature")
        labeled = [r for r in rs if r["score"]]
        require(len(labeled) >= 3, "DroughtED labeled sample")
        out = ROOT / "samples/droughted_train_prefix.csv"
        out.write_bytes(raw)
        return {"member": name, "prefix_rows": len(rs), "counties": sorted({r["fips"] for r in rs}),
                "nonmissing_score_rows": len(labeled), "examples": labeled[:3], "archive_complete": False,
                "full_member_crc_checked": False, "prefix_sha256": sha(raw), "asset_path": str(out.relative_to(REPO)),
                "license_provider": "CC0: Public Domain (captured Kaggle metadata)",
                "limits": "Partial compressed member; row boundaries parsed, whole-member CRC unavailable. Weekly USDM-derived scores are not daily labels or a new independent gold source."}

    check("droughted-prefix", "D52", drought)

    def hourly():
        footer = checked("D48-ghcnh-full-footer")
        prefix = checked("D48-ghcnh-rg0")
        rf, rp = rows["D48-ghcnh-full-footer"][1], rows["D48-ghcnh-rg0"][1]
        require(rf["headers"]["etag"] == rp["headers"]["etag"], "Parquet object changed")
        start, end, total = map(int, re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", rf["headers"]["content-range"]).groups())
        require(len(footer) == end - start + 1 and end + 1 == total, "footer range")
        require(rp["headers"]["content-range"] == f"bytes 0-{len(prefix)-1}/{total}", "prefix range")
        reader = CapturedRanges(total, [(0, prefix), (start, footer)])
        pf = pq.ParquetFile(reader)
        table = pf.read_row_group(0)
        require(table.num_rows == pf.metadata.row_group(0).num_rows, "row group count")
        df = table.to_pandas()
        good = df[df.surface_air_temperature.notna() & (df.valid_time < "2024-01-03")]
        require(len(good) >= 3, "sample rows")
        ex = good.groupby("station", sort=True).head(1).head(3).to_dict("records")
        return {"object_declared_rows": pf.metadata.num_rows, "metadata_row_groups": pf.metadata.num_row_groups,
                "decoded_row_groups": 1, "decoded_rows": len(df), "stations": int(df.station.nunique()),
                "examples": [{k: str(v) if k == "valid_time" else v for k, v in r.items()} for r in ex],
                "columns": list(df.columns), "object_bytes": total,
                "limits": "Only row group 0 downloaded, not 298 million rows. GHCN-hourly is distinct from GHCN-Daily; temperature conventions and missing wind codes require source documentation. No EWB event alignment admitted."}

    check("ewb-hourly-rowgroup", "D48", hourly)

    def geoid():
        v5rows = collect(V5)
        checksum_text = v5rows["geoid-mirror-checksums"][2].decode()
        checksums = {line.split(maxsplit=1)[1].strip(): line.split()[0] for line in checksum_text.splitlines() if line.strip()}
        tiles = []
        for i in range(3):
            parts, arrays = {}, {}
            for role in ["pre", "post", "label", "validity"]:
                ident = f"geoid-{role}-{i}"
                retry = f"D12-{ident}-retry"
                spec, response, data = rows[retry] if retry in rows else old[ident]
                require(response["complete"] and response["http_status"] == 200, "incomplete GEOID role")
                name = spec["url"].split("/868407460bf3db492f50730a57585916baa71dc6/", 1)[1]
                require(checksums[name] == sha(data), "GEOID pinned manifest checksum")
                parts[role] = {"sha256": sha(data), "member": name, **geotiff_sample(data)}
                with rasterio.io.MemoryFile(data) as mem:
                    with mem.open() as ds:
                        arrays[role] = ds.read()
            ref = parts["post"]
            require(all(p["crs"] == ref["crs"] and np.allclose(p["transform"], ref["transform"], rtol=0, atol=1e-8)
                        and p["array"]["shape"][-2:] == ref["array"]["shape"][-2:] for p in parts.values()), "GEOID grid mismatch")
            label, validity = arrays["label"][0], arrays["validity"][0]
            require(set(np.unique(label)) <= {0, 1, 2, 255}, "GEOID label classes")
            tiles.append({"tile_id": f"EMSR712-10-{i}", "parts": parts,
                          "flood_pixels": int((label == 2).sum()),
                          "validity_equals_label_not255": bool(np.array_equal(validity > 0, label != 255))})
        cems = json.loads(checked("D18-EMSR712"))["results"][0]
        aoi = next(a for a in cems["aois"] if a["number"] == 10)
        products = [{"product_id": p["id"], "type": p["type"], "monitoring_number": p["monitoringNumber"],
                     "version": p["version"], "images": p["images"]} for p in aoi["products"]]
        return {"tiles": tiles, "tile_pairs": len(tiles), "activation_count": 1, "activation": "EMSR712", "aoi": 10,
                "cems_name": cems["name"], "aoi_name": aoi["name"], "event_time": cems["eventTime"], "products": products,
                "external_split": "test (EMSR712 sample catalogue)", "new_disastertrace_split": "AUDIT_ONLY_ALREADY_OBSERVED",
                "limits": "Audit samples cannot become unseen tests. Activation/AOI bridge established; exact original scene and annotation revision links still require matching. Gold-derived validity is private QA, not independent sensor quality evidence."}

    check("geoid-complete-pairs-and-cems", "D12", geoid)

    def fire():
        reader = (refs / "D19-reader-blob.bin").read_text()
        require("y = (y > 0).long()" in reader and "torch.nan_to_num(y, nan=0.0)" in reader, "author mask semantics changed")
        run = read(PRIOR / "archive_runs/wildfirespreadts_01/RESULT.json")
        samples = []
        for m in run["members"]:
            data = (PRIOR / m["path"]).read_bytes()
            require(sha(data) == m["sha256"], "fire member hash")
            with rasterio.io.MemoryFile(data) as mem:
                with mem.open() as ds:
                    last = ds.read(ds.count)
            mask = np.nan_to_num(last, nan=0) > 0
            samples.append({"name": m["name"], "nan_pixels": int(np.isnan(last).sum()), "positive_pixels": int(mask.sum()),
                            "total_pixels": int(mask.size), "mask_sha256": sha(mask.astype(np.uint8).tobytes())})
        return {"samples": samples, "source_events": 1, "reader_git_blob": "a7422287ea43725a6deaa27e2af548626ea15629",
                "rule": "NaN to zero; detection HHMM > 0 becomes active-fire label, per author reader",
                "limits": "Reader semantics verified; detecting fire is not proof of weather causation, valid sensor coverage, or forecast-as-of provenance."}

    check("wildfire-label-semantics", "D19", fire)

    def coastal():
        samples = []
        for station in ["8761724", "8518750", "9414290"]:
            s1, _, b1 = old[f"coops-{station}-water_level"]
            s2, _, b2 = old[f"coops-{station}-predictions"]
            require(all(x in s1["url"] and x in s2["url"] for x in ["datum=MLLW", "units=metric", "time_zone=gmt"]), "datum/time/units mismatch")
            water = json.loads(b1)["data"]
            pred = {r["t"]: float(r["v"]) for r in json.loads(b2)["predictions"]}
            values = [float(r["v"]) - pred[r["t"]] for r in water if r["q"] == "v" and r["v"] and r["t"] in pred]
            require(len(values) == 240, "coastal pairing count")
            samples.append({"station": station, "matched_times": len(values), "residual_min_m": min(values), "residual_max_m": max(values)})
        return {"samples": samples, "datum": "MLLW", "timezone": "GMT", "residual_is_pure_storm_surge": False}

    check("coops-time-pairing", "D37", coastal)

    def isd_codes():
        results = []
        for station in ["54511099999", "40416099999"]:
            rs = list(csv.DictReader(io.StringIO(old["isd-" + station][2].decode())))
            kinds = {"dust_storm_codes_30_35": {str(v) for v in range(30, 36)}, "fog_codes_40_49": {str(v) for v in range(40, 50)},
                     "freezing_rain_codes_66_67": {"66", "67"}, "blowing_snow_codes_36_39": {str(v) for v in range(36, 40)}}
            for kind, codes in kinds.items():
                selected = []
                for r in rs:
                    parts = r.get("MW1", "").split(",")
                    vis = r["VIS"].split(",")
                    if len(parts) >= 2 and parts[0] in codes and parts[1] in {"0", "1", "4", "5"} and vis[1] in {"0", "1", "4", "5"} and int(vis[0]) != 999999:
                        selected.append({k: r.get(k) for k in ["STATION", "DATE", "LATITUDE", "LONGITUDE", "MW1", "VIS", "WND"]})
                results.append({"station": station, "phenomenon_code_group": kind, "qc_accepted_reports": len(selected), "examples": selected[:3]})
        return {"groups": results, "limits": "Code-specific presence probes; WMO/ISD code definitions are required for final subtype admission. No independent event or local-extreme threshold inferred."}

    check("isd-phenomenon-samples", "D27", isd_codes)

    def cyport():
        result = []
        for storm in ["DORIAN_2019", "HARVEY_2017", "FLORENCE_2018"]:
            parts = {}
            for ext in ["png", "txt"]:
                ident = f"D50-{storm}-{ext}"
                blob = refs / (ident + "-blob.bin")
                data = blob.read_bytes() if blob.exists() else checked(ident)
                if ext == "png":
                    with Image.open(io.BytesIO(data)) as im:
                        im.load()
                        parts[ext] = {"size": list(im.size), "format": im.format, "sha256": sha(data)}
                else:
                    text = data.decode()
                    ids = sorted(set(re.findall(r"AL\d{6}", text)))
                    require(ids, "missing NHC storm ID")
                    parts[ext] = {"storm_ids": ids, "sha256": sha(data), "prefix": text[:800]}
            result.append({"source_storm_name": storm, "parts": parts})
        return {"samples": result, "storms_by_filename": len(result), "limits": "Filename-level text/graphic bundle checked. Exact matching advisory issue and image-printed timestamp still pending; no port decision labels adopted."}

    check("cyport-three-storm-bundles", "D50", cyport)
    output = {"schema": "v6_offline_supplement_audit_v1", "reports": reports, "model_calls": 0, "gpu_jobs": 0,
              "new_formal_episodes": 0, "checked_capture_ids": sorted(rows)}
    path = ROOT / "analysis/SELECTION_AUDIT.json"
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2, default=str, allow_nan=False) + "\n")
    print(json.dumps({r["id"]: r["level"] + (": " + r["error"] if "error" in r else "") for r in reports}, indent=2))


if __name__ == "__main__":
    main()
