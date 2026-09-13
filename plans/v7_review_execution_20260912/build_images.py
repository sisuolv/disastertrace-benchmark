"""Decode same-time GOES-18 channels into auditable regional thermal panels."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import netCDF4
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pyproj import CRS, Transformer


ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_channel(path, expected_band):
    receipt = json.loads(path.with_suffix(".json").read_text())
    if not receipt["complete"] or sha(path) != receipt["sha256"] or path.stat().st_size != receipt["expected_size"]:
        raise ValueError("Unverified complete image source")
    with netCDF4.Dataset(path) as dataset:
        projection = dataset.variables["goes_imager_projection"]
        attrs = {k: getattr(projection, k) for k in projection.ncattrs()}
        band = int(dataset.variables["band_id"][:].item())
        if band != expected_band or dataset.platform_ID != "G18":
            raise ValueError("Wrong historical platform/channel")
        cmi = dataset.variables["CMI"][:]
        quality = dataset.variables["DQF"][:]
        if dataset.variables["CMI"].units != "K":
            raise ValueError("Expected calibrated brightness temperature")
        x, y = dataset.variables["x"][:], dataset.variables["y"][:]
        metadata = {"platform": dataset.platform_ID, "band": band,
            "time_coverage_start": dataset.time_coverage_start, "time_coverage_end": dataset.time_coverage_end,
            "date_created": dataset.date_created, "projection": attrs, "units": "K",
            "full_shape": list(cmi.shape), "source_path": str(path.relative_to(ROOT)), "sha256": sha(path),
            "object_last_modified": receipt["object_last_modified"]}
    return np.ma.filled(cmi, np.nan), np.ma.filled(quality, 255), np.asarray(x), np.asarray(y), metadata


def build(output):
    plan = json.loads((ROOT / "IMAGE_FETCH_03.json").read_text())
    output.mkdir(parents=True, exist_ok=False)
    stations = {}
    for station in ("KSFO", "KOAK", "KSJC"):
        with (ROOT / "captures_03" / ("metar-routine-" + station + ".body")).open() as stream:
            row = next(csv.DictReader(stream))
            stations[station] = (float(row["lon"]), float(row["lat"]))
    entries = []
    for day in ("005", "006"):
        records = [read_channel(ROOT / "image_captures_03" / f"goes18-2024{day}-0041-C{band:02d}.body", band) for band in (7, 13)]
        a, b = records
        if not np.array_equal(a[2], b[2]) or not np.array_equal(a[3], b[3]):
            raise ValueError("Channels have different physical grids")
        start_times = [datetime.strptime(r[4]["time_coverage_start"], "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc) for r in records]
        if abs((start_times[0] - start_times[1]).total_seconds()) > 1:
            raise ValueError("Channels are not from the same scan")
        attrs = a[4]["projection"]
        height = attrs["perspective_point_height"]
        crs = CRS.from_proj4(f"+proj=geos +h={height} +lon_0={attrs['longitude_of_projection_origin']} +sweep={attrs['sweep_angle_axis']} +a={attrs['semi_major_axis']} +b={attrs['semi_minor_axis']}")
        transform = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
        west, south, east, north = plan["roi_lonlat"]
        lons = np.concatenate([np.linspace(west, east, 40)] * 2 + [np.full(40, west), np.full(40, east)])
        lats = np.concatenate([np.full(40, south), np.full(40, north)] + [np.linspace(south, north, 40)] * 2)
        border_x, border_y = transform.transform(lons, lats)
        x, y = a[2] * height, a[3] * height
        xi = np.flatnonzero((x >= np.min(border_x)) & (x <= np.max(border_x)))
        yi = np.flatnonzero((y >= np.min(border_y)) & (y <= np.max(border_y)))
        if len(xi) < 10 or len(yi) < 10:
            raise ValueError("Region not in image footprint")
        ys, xs = slice(yi.min(), yi.max() + 1), slice(xi.min(), xi.max() + 1)
        channels = [r[0][ys, xs] for r in records]
        quality = [r[1][ys, xs] for r in records]
        valid = np.logical_and.reduce([np.isfinite(c) & (q == 0) for c, q in zip(channels, quality)])
        if float(valid.mean()) < 0.9:
            raise ValueError("Registered region lacks 90% best-quality paired pixels")
        roi = np.stack(channels)
        array_path = output / f"goes18-2024{day}-0041.npz"
        np.savez_compressed(array_path, brightness_temperature_K=roi, DQF=np.stack(quality),
                            x_m=x[xs], y_m=y[ys], best_quality_pair=valid)
        panels = [channels[0], channels[1], channels[0] - channels[1]]
        limits = [(230, 300), (230, 300), (-15, 15)]
        titles = ["GOES-18 C07 / 3.9 um / K", "GOES-18 C13 / 10.3 um / K", "C07 minus C13 / K"]
        width = 320
        panel_height = round(width * roi.shape[1] / roi.shape[2])
        canvas = Image.new("RGB", (3 * width, panel_height + 80), (248, 248, 243))
        draw = ImageDraw.Draw(canvas)
        font_path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
        font = ImageFont.truetype(str(font_path), 13) if font_path.exists() else ImageFont.load_default()
        sensor_markers = {}
        for index, (panel, (low, high), title) in enumerate(zip(panels, limits, titles)):
            scale = np.clip((panel - low) / (high - low), 0, 1)
            gray = np.uint8(np.nan_to_num(scale, nan=0) * 255)
            rgb = np.stack([gray] * 3, axis=-1)
            rgb[~valid] = [150, 65, 65]
            image = Image.fromarray(rgb).resize((width, panel_height), Image.Resampling.NEAREST)
            canvas.paste(image, (index * width, 30))
            draw.text((index * width + 7, 8), title, fill=(15, 35, 35), font=font)
            draw.text((index * width + 7, panel_height + 35), f"black={low}  white={high}; DQF=0", fill=(15, 35, 35), font=font)
            for station, (lon, lat) in stations.items():
                px, py = transform.transform(lon, lat)
                col = int(np.argmin(abs(x[xs] - px)))
                row = int(np.argmin(abs(y[ys] - py)))
                if not (x[xs].min() <= px <= x[xs].max() and y[ys].min() <= py <= y[ys].max()):
                    raise ValueError("Station outside rendered footprint")
                sx, sy = index * width + (col + 0.5) / roi.shape[2] * width, 30 + (row + 0.5) / roi.shape[1] * panel_height
                draw.ellipse((sx - 2, sy - 2, sx + 2, sy + 2), fill=(255, 185, 35))
                draw.text((sx + 3, sy - 13), station, fill=(255, 190, 40), font=font, stroke_width=1, stroke_fill=(0, 0, 0))
                sensor_markers[station] = {"row": row, "column": col, "longitude": lon, "latitude": lat}
        draw.text((7, panel_height + 59), f"2024 day {day} 00:41 UTC. Derived thermal context; not a fog mask. No outcome labels.", fill=(15, 35, 35), font=font)
        image_path = output / f"goes18-2024{day}-0041.png"
        canvas.save(image_path)
        entries.append({"scene_id": f"goes18-2024{day}-0041", "image_file": image_path.name, "image_sha256": sha(image_path),
            "array_file": array_path.name, "array_sha256": sha(array_path), "channels": [r[4] for r in records],
            "roi_shape": list(roi.shape), "best_quality_pair_fraction": float(valid.mean()), "station_pixels": sensor_markers,
            "pixel_statistics": [{"band": band, "minimum_K": float(np.nanmin(c)), "maximum_K": float(np.nanmax(c)),
                                   "mean_K": float(np.nanmean(c))} for band, c in zip((7, 13), channels)],
            "representation": "same_source_lossy_fixed_scale_thermal_panels", "native_model_processor_input_verified": False,
            "support_assumption": "public_sensor_values_and_quality_only_not_hidden_weather_labels"})
    report = {"built_at": datetime.now(timezone.utc).isoformat(), "scenes": entries,
              "roi_lonlat": plan["roi_lonlat"], "source_plan_sha256": sha(ROOT / "IMAGE_FETCH_03.json"),
              "roi_selection": "projected rectangle enclosing the registered lon/lat boundary; not an exact geographic polygon mask",
              "historical_platform_checked": True, "temporal_spatial_join_checked": True,
              "native_model_processor_input_verified": False, "outcome_labels_used": False}
    (output / "REGIONAL_IMAGE_JOIN.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"scenes": len(entries), "shapes": [e["roi_shape"] for e in entries]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    build(parser.parse_args().output)
