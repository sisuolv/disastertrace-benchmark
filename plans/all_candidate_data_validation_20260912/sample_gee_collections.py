"""Bounded authenticated GEE sampling, with data receipts per exact collection."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys


def worker(spec, output):
    import ee
    import requests
    output.mkdir(parents=True, exist_ok=False)
    report = dict(spec, started_at=datetime.now(timezone.utc).isoformat(), status="pending")
    try:
        ee.Initialize(project="disastertrace-gee")
        ee.data.setDeadline(45000)
        region = ee.Geometry.Rectangle(spec.get("bbox", [116.2, 39.7, 116.6, 40.1]))
        collection = ee.ImageCollection(spec["collection"])
        if spec.get("start"):
            collection = collection.filterDate(spec["start"], spec["end"]).filterBounds(region)
        image = ee.Image(collection.sort("system:time_start").first())
        metadata = image.toDictionary().getInfo()
        bands = image.bandNames().getInfo()
        report["collection_band_names"] = bands
        selected = spec.get("bands", bands[:3])
        if not set(selected) <= set(bands):
            raise ValueError("Requested bands not in collection schema")
        if spec.get("native_geometry"):
            region = image.geometry()
        values = image.select(selected).sample(region=region, scale=spec.get("scale", 1000),
                                               numPixels=spec.get("sample_pixels", 10), seed=17, geometries=True).limit(3).getInfo()
        raw = json.dumps(values, indent=2, allow_nan=False).encode()
        (output / "sample.json").write_bytes(raw)
        (output / "metadata.json").write_text(json.dumps(metadata, indent=2, allow_nan=False) + "\n")
        report.update(image_id=image.id().getInfo(), collection_band_names=bands, selected_bands=selected,
                      samples=len(values.get("features", [])), sample_sha256=hashlib.sha256(raw).hexdigest(),
                      metadata_sha256=hashlib.sha256((output / "metadata.json").read_bytes()).hexdigest())
        numeric = [v for f in values.get("features", []) for k, v in f["properties"].items()
                   if k in selected and isinstance(v, (int, float)) and math.isfinite(v)]
        report["numeric_values"] = len(numeric)
        report["status"] = "numeric_pixels_downloaded" if numeric else "asset_accessible_no_valid_pixels"
        if numeric and spec.get("geotiff"):
            point = ee.Geometry.Point(values["features"][0]["geometry"]["coordinates"])
            url = image.select(selected).toFloat().getDownloadURL(dict(region=point.buffer(1500).bounds(),
                                                                       scale=spec.get("scale", 1000), format="GEO_TIFF"))
            # The signed URL stays in memory, outside publication receipts.
            with requests.get(url, stream=True, timeout=45) as response:
                response.raise_for_status()
                chunks = bytearray()
                for chunk in response.iter_content(65536):
                    chunks.extend(chunk)
                    if len(chunks) > 2 * 1024 * 1024:
                        raise ValueError("Raster sample exceeds 2 MiB cap")
            (output / "sample.tif").write_bytes(chunks)
            report.update(geotiff_bytes=len(chunks), geotiff_sha256=hashlib.sha256(chunks).hexdigest())
    except Exception as error:
        # EE errors contain public collection/permission diagnostics; omit arbitrary transport URLs.
        report.update(status="failed", error_type=type(error).__name__)
        message = str(error)
        report["error"] = message[:1000] if "https://" not in message and "token" not in message.lower() else "Transport or credential error; private URL omitted"
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    report["task_admitted"] = False
    (output / "RECEIPT.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("spec", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--index", type=int)
    args = parser.parse_args()
    specs = json.loads(args.spec.read_text())
    if args.index is not None:
        result = worker(specs[args.index], args.output)
        print(result["id"], result["status"], result.get("numeric_values", 0))
        return
    args.output.mkdir(parents=True, exist_ok=False)

    def run(index):
        destination = args.output / specs[index]["id"]
        try:
            process = subprocess.run([sys.executable, __file__, str(args.spec), str(destination), "--index", str(index)],
                                     capture_output=True, timeout=180)
            if (destination / "RECEIPT.json").exists():
                return json.loads((destination / "RECEIPT.json").read_text())
            return dict(id=specs[index]["id"], source_id=specs[index]["source_id"], status="worker_failed", exit_code=process.returncode)
        except subprocess.TimeoutExpired:
            return dict(id=specs[index]["id"], source_id=specs[index]["source_id"], status="worker_deadline")

    with ThreadPoolExecutor(max_workers=4) as pool:
        reports = list(pool.map(run, range(len(specs))))
    (args.output / "MANIFEST.json").write_text(json.dumps(dict(reports=reports), indent=2) + "\n")
    for report in reports:
        print(report["id"], report["status"], report.get("numeric_values", 0))


if __name__ == "__main__":
    main()
