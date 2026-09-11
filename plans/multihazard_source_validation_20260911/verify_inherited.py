"""Recheck previously captured samples; do not modify the old bundles."""

import csv
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

import numpy as np
import rasterio
import shapefile

from validate_samples import array_summary, require

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
FEAS = REPO / "plans/v5_0910_feasibility_12h_20260910"
PROBE = REPO / "plans/v5_0910_source_probe_20260910"


def read(p):
    return json.loads(p.read_text())


def main():
    index = {}
    for root in (PROBE, FEAS):
        for f in (root / "specs").glob("*.json"):
            for s in read(f)["probes"]:
                record = root / "batches" / f.stem / (s["id"] + ".json")
                if record.exists():
                    index[s["id"]] = root, read(record).get("final", {})
    files = {}

    def bind(path, expected=None):
        data = path.read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        require(expected is None or sha == expected, "inherited file hash differs")
        files[str(path.relative_to(REPO))] = {"bytes": len(data), "sha256": sha}
        return data

    def capture(ident):
        root, response = index[ident]
        require(response.get("complete") and response["http_status"] in (200, 206), "incomplete inherited response")
        data = bind(root / response["attempt_path"] / "body.bin", response["body_sha256"])
        return data

    reports = []
    products = json.loads(bind(FEAS / "data/NHC_PRODUCTS.json"))
    seen, selected = set(), []
    for r in products:
        if r["storm_id"] in seen:
            continue
        seen.add(r["storm_id"])
        require("FORECAST/ADVISORY" in r["raw_text"] and len(r["forecasts"]) >= 3, "NHC product")
        for ref in r.get("sources", [r.get("source")]):
            if ref:
                bind(REPO / ref["path"], ref["sha256"])
        selected.append({"storm_id": r["storm_id"], "issue_time": r["issue_time"], "advisory_number": r["advisory_number"], "forecast_rows": len(r["forecasts"])})
        if len(selected) == 3:
            break
    require(len(selected) == 3, "three NHC storm products")
    reports.append({"source": "nhc_operational", "level": "inherited_samples_rechecked", "sample_unit": "advisory from distinct previously used storm", "samples": selected})

    arrays = json.loads(bind(FEAS / "data/SEVIR_ARRAYS.json"))
    selected = []
    for r in arrays:
        if r.get("channel") != "vil" or len(selected) == 3:
            continue
        data = bind(FEAS / r["array_path"], r["file_sha256"])
        arr = np.load(io.BytesIO(data), allow_pickle=False)
        require(hashlib.sha256(arr.tobytes()).hexdigest() == r["array_sha256"], "SEVIR array mismatch")
        require(arr.shape[-1] == 49 and len(r["offsets"]) == 49, "SEVIR frame/offset count")
        for ref in r["sources"]:
            bind(REPO / ref["path"], ref["sha256"])
        selected.append({"event_id": r["event_id"], "published_type": r["row"].get("event_type"), "array": array_summary(arr), "missing_255": int((arr == 255).sum()), "time_utc": r["row"]["time_utc"]})
    require(len({r["event_id"] for r in selected}) == 3, "three SEVIR catalogue IDs")
    reports.append({"source": "sevir", "level": "inherited_samples_rechecked", "sample_unit": "VIL sequence with 49 frames", "samples": selected})

    selected = []
    for ident in ("usdm-20240827", "usdm-20240903", "usdm-shapefile-20240910"):
        with zipfile.ZipFile(io.BytesIO(capture(ident))) as z:
            require(z.testzip() is None, "USDM ZIP CRC")
            shp = next(n for n in z.namelist() if n.endswith(".shp"))
            reader = shapefile.Reader(shp=io.BytesIO(z.read(shp)), shx=io.BytesIO(z.read(shp[:-4] + ".shx")), dbf=io.BytesIO(z.read(shp[:-4] + ".dbf")))
            rows = [r.as_dict() for r in reader.records()]
            require({int(r["DM"]) for r in rows} == set(range(5)), "USDM categories")
            selected.append({"capture_id": ident, "features": len(rows), "bbox": list(reader.bbox), "categories": sorted({int(r["DM"]) for r in rows})})
    reports.append({"source": "usdm", "level": "inherited_samples_rechecked", "sample_unit": "weekly source map", "samples": selected, "limits": "Geometry validity and area reasoning are separate; prior point labels not re-admitted here."})

    pairs = json.loads(bind(FEAS / "analysis/SEN1_FEASIBILITY_03.json"))["pairs"]
    selected = []
    for pair in pairs:
        opened = []
        for ident in pair["source_ids"]:
            data = capture(ident)
            with rasterio.io.MemoryFile(data) as mem:
                with mem.open() as ds:
                    arr = ds.read()
                    opened.append({"id": ident, "crs": str(ds.crs), "transform": list(ds.transform), "shape": list(arr.shape), "array": array_summary(arr)})
                    if "LabelHand" in ident:
                        values, counts = np.unique(arr, return_counts=True)
                        require({str(int(v)): int(n) for v, n in zip(values, counts)} == pair["label_counts"], "Sen1 label counts")
        grid_error = max(abs(a - b) for a, b in zip(opened[0]["transform"], opened[1]["transform"]))
        require(opened[0]["crs"] == opened[1]["crs"] and grid_error <= 1e-12 and opened[0]["shape"][-2:] == opened[1]["shape"][-2:], "Sen1 spatial pairing")
        selected.append({"chip": pair["chip"], "event": pair["event"], "rasters": opened, "label_counts": pair["label_counts"]})
    reports.append({"source": "sen1floods11", "level": "inherited_samples_rechecked", "sample_unit": "spatial image-label pair", "samples": selected, "limits": "Three chips from two event regions; dataset-specific rights remain unresolved."})

    data = json.loads(capture("fpafod6-three-features"))
    require(len(data["features"]) == 3 and all(r.get("geometry") for r in data["features"]), "FPA-FOD three geometries")
    reports.append({"source": "fpa_fod6", "level": "inherited_catalog_rechecked", "sample_unit": "fire occurrence record", "samples": data["features"]})

    meta = json.loads(capture("weatherbench-zarr-metadata"))["metadata"]["2m_temperature/.zarray"]
    import numcodecs
    raw = numcodecs.get_codec(meta["compressor"]).decode(capture("weatherbench-temperature-chunk"))
    arr = np.frombuffer(raw, dtype=np.dtype(meta["dtype"])).reshape(meta["chunks"])
    require(arr.shape == (8, 240, 121) and np.isfinite(arr).all(), "WeatherBench2 temperature chunk")
    reports.append({"source": "weatherbench2", "level": "inherited_array_rechecked", "sample_unit": "temperature chunk with eight time slots", "samples": [{"array": array_summary(arr)}], "limits": "Fixed processed ERA5 product; CDS authentication and physical time-coordinate fetch are separate."})

    final = {"schema": "inherited_sample_recheck_v1", "new_downloads": False, "reports": reports, "files": files}
    target = ROOT / "analysis/INHERITED_SAMPLES.json"
    require(not target.exists(), "use a fresh output")
    target.write_text(json.dumps(final, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"sources": len(reports), "files": len(files)}))


if __name__ == "__main__":
    main()
