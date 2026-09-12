"""Decode recovered native samples, with explicit task limits and source bindings."""

import argparse
import csv
import hashlib
import io
import json
import pickle
import zipfile
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

import h5py
import numpy as np
import rasterio
import tifffile
import xarray as xr
from PIL import Image
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
HASHES = {}


def bind(path):
    path = path.resolve()
    if path not in HASHES:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024**2), b""):
                digest.update(chunk)
        HASHES[path] = {
            "path": str(path.relative_to(REPO)),
            "sha256": digest.hexdigest(),
            "bytes": path.stat().st_size,
        }
    return HASHES[path]


def captured(number, name):
    path = ROOT / f"captures_{number:02d}" / (name + ".body")
    receipt = json.loads(path.with_suffix(".json").read_text())
    bound = bind(path)
    if receipt["http_status"] not in (200, 206) or receipt["curl_exit"]:
        raise ValueError("Incomplete source: " + name)
    if receipt.get("locally_truncated"):
        raise ValueError("Locally truncated source: " + name)
    if receipt["sha256"] != bound["sha256"] or receipt["bytes"] != bound["bytes"]:
        raise ValueError("Capture binding failed: " + name)
    bind(path.with_suffix(".json"))
    return path


def stats(values):
    values = np.asarray(values)
    finite = values[np.isfinite(values)]
    return {
        "shape": list(values.shape),
        "dtype": str(values.dtype),
        "finite": int(finite.size),
        "min": float(finite.min()) if finite.size else None,
        "max": float(finite.max()) if finite.size else None,
    }


def classes(values):
    values, counts = np.unique(values, return_counts=True)
    return {
        str(value): int(count) for value, count in zip(values.tolist(), counts.tolist())
    }


def source_hour(value):
    # Preserve the source's offset-free clock instead of inventing a timezone.
    return datetime.strptime(value, "%Y%m%d%H")  # noqa: DTZ007


class RestrictedArrayUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        allowed = {
            ("numpy.core.multiarray", "_reconstruct"): np._core.multiarray._reconstruct,
            ("numpy", "ndarray"): np.ndarray,
            ("numpy", "dtype"): np.dtype,
        }
        if (module, name) not in allowed:
            raise ValueError("Unsupported metadata pickle global")
        return allowed[module, name]


def tcir(output):
    archive = captured(2, "tcir-full-2017")
    path = ROOT / "extracted_inputs/TCIR-ALL_2017.h5"
    container = json.loads((ROOT / "TCIR_CONTAINER_CHECK.json").read_text())
    if not container["complete_gzip_crc_passed"]:
        raise ValueError("Full gzip verification missing")
    if container["members"] != [{"name": path.name, "bytes": path.stat().st_size}]:
        raise ValueError("TCIR extracted member size mismatch")
    with h5py.File(path, "r") as f:
        numeric_keys = [x.decode() for x in f["info/block0_items"][:]]
        text_keys = [x.decode() for x in f["info/block1_items"][:]]
        numeric = f["info/block0_values"][:]
        text = RestrictedArrayUnpickler(
            io.BytesIO(f["info/block1_values"][0].tobytes())
        ).load()
        if len(numeric) != len(text) or len(text) != f["matrix"].shape[0]:
            raise ValueError("TCIR image/label row count mismatch")
        examples = []
        for i in range(6):
            row = dict(zip(numeric_keys, numeric[i].tolist()))
            row.update(zip(text_keys, text[i].tolist()))
            source_hour(row["time"])
            examples.append(row)
        frames = f["matrix"][:6]
        image_shape = list(f["matrix"].shape)
    if examples[0]["ID"] != examples[4]["ID"]:
        raise ValueError("Sequence crosses a storm")
    cutoff = source_hour(examples[2]["time"])
    target = source_hour(examples[4]["time"])
    if target - cutoff != timedelta(hours=6):
        raise ValueError("Unexpected sequence horizon")
    np.savez_compressed(output / "tcir_six_frames.npz", matrix=frames)
    return {
        "source_id": "D04",
        "level": "paired_native_arrays",
        "files": [bind(archive), bind(path), bind(ROOT / "TCIR_CONTAINER_CHECK.json")],
        "details": {
            "image_shape": image_shape,
            "metadata_rows": len(text),
            "unique_storm_ids": len(set(text[:, text_keys.index("ID")].tolist())),
            "first_six_records": examples,
            "sample_arrays": stats(frames),
            "gzip_crc_checked": True,
            "bounded_metadata_unpickler": True,
            "sequence_example": {
                "input_rows": [0, 1, 2],
                "cutoff": cutoff.isoformat(),
                "future_row": 4,
                "target": target.isoformat(),
                "horizon_hours": 6,
                "reference_vmax": examples[4]["Vmax"],
            },
        },
        "limits": "2017 author split is exposed development material. Intensity is inherited analysis, not independent sensor truth. Historical release time and common professional forecast are not supplied by this sample.",
    }


def camels(output):
    archive = ROOT / "camels_zip_01"
    receipt = json.loads((archive / "RESULT.json").read_text())
    if receipt["status"] != "complete_members":
        raise ValueError("Incomplete CAMELSH members")
    details, files = [], [bind(archive / "RESULT.json")]
    for item in receipt["members"]:
        path = archive / item["file"]
        binding = bind(path)
        if binding["sha256"] != item["sha256"] or not item["crc_checked"]:
            raise ValueError("CAMELSH member identity mismatch")
        files.append(binding)
        with xr.open_dataset(path) as dataset:
            times = dataset.time.values
            if not np.all(np.diff(times) == np.timedelta64(1, "h")):
                raise ValueError("Irregular nominal hourly grid")
            variables = {}
            for name in ("streamflow", "water_level"):
                values = dataset[name].values
                indices = np.flatnonzero(np.isfinite(values))
                sample = indices[-3:]
                variables[name] = {
                    **stats(values),
                    "units": dataset[name].attrs.get("units"),
                    "missing": int((~np.isfinite(values)).sum()),
                    "last_valid_records": [
                        {"time": str(times[i]), "value": float(values[i])}
                        for i in sample
                    ],
                }
            details.append(
                {
                    "member": item["member"],
                    "nominal_hours": len(times),
                    "first": str(times[0]),
                    "last": str(times[-1]),
                    "variables": variables,
                }
            )
    return {
        "source_id": "D71",
        "level": "native_hourly_series",
        "files": files,
        "details": details,
        "limits": "Three stations from author Hourly2 version 16729675. Grid coverage is not valid-observation coverage. Gage-height datum, maturity, original arrival and business-forecast pairing remain separate gates. Meteorological forcing is not included in these observation-only members.",
    }


def cems(output):
    path = captured(1, "cems-product-proxy")
    details = []
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("CEMS member CRC failure")
        for name in archive.namelist():
            if not name.endswith(".json"):
                continue
            obj = json.loads(archive.read(name))
            features = obj["features"]
            located = [
                i
                for i, feature in enumerate(features)
                if feature.get("geometry") is not None
            ]
            geometries = [shape(features[i]["geometry"]) for i in located]
            details.append(
                {
                    "member": name,
                    "features": len(features),
                    "geometry_types": dict(Counter(g.geom_type for g in geometries)),
                    "missing_geometries": len(features) - len(located),
                    "first_geometry_row_index": located[0] if located else None,
                    "invalid_geometries": sum(not g.is_valid for g in geometries),
                    "first_properties": features[0]["properties"] if features else {},
                    "first_bounds": list(geometries[0].bounds) if geometries else [],
                    "crs": obj.get("crs"),
                }
            )
    return {
        "source_id": "D18",
        "level": "native_vector_product",
        "files": [bind(path)],
        "details": details,
        "sample_hazards": ["H16"],
        "limits": "EMSR842 AOI01 is a Zamora wildfire grading product; it does not validate a flood AOI. Burned area and damage are retrospective mapped references; no original satellite raster is included.",
    }


def floodnet(output):
    files, details = [], []
    for ident in ("6279", "6287", "6332"):
        image_path = captured(6, "floodnet-" + ident + "-jpg")
        mask_path = captured(6, "floodnet-" + ident + "_lab-png")
        files.extend([bind(image_path), bind(mask_path)])
        with Image.open(image_path) as image, Image.open(mask_path) as mask:
            image.load()
            mask.load()
            if image.size != mask.size or image.mode != "RGB" or mask.mode != "L":
                raise ValueError("FloodNet pair geometry/mode mismatch")
            values = np.asarray(mask)
            if not set(np.unique(values).tolist()) <= set(range(10)):
                raise ValueError("Unexpected FloodNet label code")
            details.append(
                {
                    "id": ident,
                    "size": list(image.size),
                    "classes": classes(values),
                    "flooded_building_or_road_pixels": int(
                        np.isin(values, [1, 3]).sum()
                    ),
                }
            )
    return {
        "source_id": "D17",
        "level": "paired_native_images_masks",
        "files": files,
        "details": details,
        "limits": "Three matched original-author training pairs; selected masks have no flooded-building/road classes. Post-Harvey imagery supports perception diagnostics, not a pre-event forecast without independent timing/context.",
    }


def senfor(output):
    paths = sorted((ROOT / "captures_06").glob("senfor-000000-*.body"))
    if len(paths) != 7:
        raise ValueError("Expected seven SenForFlood components")
    files, details, reference = [], [], None
    for path in paths:
        captured(6, path.stem)
        files.append(bind(path))
        with rasterio.open(path) as dataset:
            identity = (
                str(dataset.crs),
                tuple(dataset.transform),
                dataset.height,
                dataset.width,
            )
            if reference is None:
                reference = identity
            if identity != reference:
                raise ValueError("SenForFlood grids do not align")
            values = dataset.read()
            details.append(
                {
                    "file": path.name,
                    "arrays": stats(values),
                    "crs": str(dataset.crs),
                    "transform": list(dataset.transform),
                    "bounds": list(dataset.bounds),
                    "nodata": dataset.nodata,
                    "band_descriptions": list(dataset.descriptions),
                    "classes": classes(values) if "mask" in path.name else None,
                }
            )
    return {
        "source_id": "D64",
        "level": "paired_before_during_multimodal",
        "files": files,
        "details": details,
        "limits": "One EMSR339 512x512 chip with SAR/optical before and during, terrain, LULC and mask. CEMS-derived mask is dependent on CEMS. Exact sensing times, band semantics and mask-code legend must be confirmed before time-gated or binary-flood scoring; no automatic conversion of every nonzero code to flood.",
    }


def crisis(output):
    path = captured(1, "crisismmd-splits-proxy")
    selection = json.loads((ROOT / "CRISIS_SELECTION.json").read_text())
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("CrisisMMD label archive CRC failed")
        records = list(
            csv.DictReader(
                io.StringIO(archive.read(selection["member"]).decode()), delimiter="\t"
            )
        )
    indexed = {r["image_id"]: r for r in records}
    details, files = [], [bind(path), bind(ROOT / "CRISIS_SELECTION.json")]
    for i, selected in enumerate(selection["records"]):
        if (
            indexed[selected["image_id"]] != selected
            or "earthquake" in selected["event_name"]
        ):
            raise ValueError("Selected weather annotation mismatch")
        image_path = captured(8, "crisis-pair-" + str(i))
        files.append(bind(image_path))
        with Image.open(image_path) as image:
            image.load()
            details.append(
                {
                    "annotation": selected,
                    "decoded_size": list(image.size),
                    "mode": image.mode,
                    "exact_path_join": True,
                }
            )
    return {
        "source_id": "D45",
        "level": "paired_text_image_labels",
        "files": files,
        "details": {"training_rows": len(records), "pairs": details},
        "limits": "Official QCRI-hosted image paths join the original label ZIP. Social relevance/impact labels are not meteorological observations or verified capture times. Reposts, upstream licences and non-weather event filtering remain required.",
    }


def urban(output):
    spec_path = ROOT / "URBAN_SELECTED_PAIR.json"
    spec = json.loads(spec_path.read_text())
    prefix = ROOT / "captures_10/urban-positive-mask-strips.body"
    tail = captured(13, "urban-positive-mask-tail")
    left_receipt = json.loads(prefix.with_suffix(".json").read_text())
    right_receipt = json.loads(tail.with_suffix(".json").read_text())
    left, right = prefix.read_bytes(), tail.read_bytes()
    if (
        bind(prefix)["sha256"] != left_receipt["sha256"]
        or len(left) != left_receipt["bytes"]
    ):
        raise ValueError("Partial prefix identity changed")
    if (
        left_receipt["http_status"] != 206
        or left_receipt["url"] != right_receipt["url"]
    ):
        raise ValueError("Range assembly source mismatch")
    if not left_receipt["response_headers"].get("etag") or (
        left_receipt["response_headers"]["etag"]
        != right_receipt["response_headers"].get("etag")
    ):
        raise ValueError("Range assembly version mismatch")
    tail_start = spec["start"] + len(left) - 65536
    if right_receipt["range"] != f"{tail_start}-{spec['end']}":
        raise ValueError("Tail begins at the wrong offset")
    full_size = 927142786
    for receipt, start in [(left_receipt, spec["start"]), (right_receipt, tail_start)]:
        if (
            receipt["response_headers"].get("content-range")
            != f"bytes {start}-{spec['end']}/{full_size}"
        ):
            raise ValueError("Unexpected source Content-Range")
    if left[-65536:] != right[:65536]:
        raise ValueError("Range overlap differs")
    combined = left + right[65536:]
    if len(combined) != spec["end"] - spec["start"] + 1:
        raise ValueError("Incomplete recovered window")
    header = captured(5, "urban-label-full-header")
    header_receipt = json.loads(header.with_suffix(".json").read_text())
    if (
        header_receipt["response_headers"].get("etag")
        != left_receipt["response_headers"]["etag"]
    ):
        raise ValueError("Header and strips have different versions")
    with tifffile.TiffFile(io.BytesIO(header.read_bytes())) as tiff:
        geo = tiff.geotiff_metadata
        page = tiff.pages[0]
        if page.compression != 1 or page.rowsperstrip != 1:
            raise ValueError("Unsupported strip encoding")
        for i in range(256):
            if (
                page.dataoffsets[spec["row_start"] + i]
                != spec["start"] + i * spec["full_width"] * 4
            ):
                raise ValueError("Strip order assumption violated")
    mask = np.frombuffer(combined, dtype=spec["dtype"]).reshape(256, spec["full_width"])
    mask = mask[:, spec["col_start"] : spec["col_start"] + 256].copy()
    if not set(np.unique(mask).tolist()) <= {0, 1, 2}:
        raise ValueError("Urban mask violates published label codes")
    sar = captured(10, "urban-positive-sar")
    with rasterio.open(sar) as dataset:
        transform = dataset.transform
        x = geo["ModelTiepoint"][3] + spec["col_start"] * geo["ModelPixelScale"][0]
        y = geo["ModelTiepoint"][4] - spec["row_start"] * geo["ModelPixelScale"][1]
        if dataset.shape != mask.shape or str(dataset.crs) != "EPSG:4326":
            raise ValueError("Urban pair dimensions or CRS disagree")
        if not np.allclose(
            [transform.a, transform.e, transform.c, transform.f],
            [geo["ModelPixelScale"][0], -geo["ModelPixelScale"][1], x, y],
            rtol=0,
            atol=1e-10,
        ):
            raise ValueError("Urban pair geolocation mismatch")
        details = {
            "sar": stats(dataset.read()),
            "transform": list(transform),
            "mask_classes": classes(mask),
            "tile_row": spec["tile_row"],
            "tile_col": spec["tile_col"],
            "restored_window_bytes": len(combined),
            "overlap_checked_bytes": 65536,
            "source_prefix_curl_exit": left_receipt["curl_exit"],
            "first_sample_all_zero_retained": True,
            "label_codes_from_paper": {
                "0": "non-flooded",
                "1": "flooded_open",
                "2": "flooded_urban",
            },
        }
    np.save(output / "urban_matched_mask.npy", mask, allow_pickle=False)
    return {
        "source_id": "D14",
        "level": "paired_native_sar_mask",
        "details": details,
        "files": [
            bind(p)
            for p in [
                header,
                prefix,
                prefix.with_suffix(".json"),
                tail,
                sar,
                spec_path,
                ROOT / "captures_10/urban-paper.body",
            ]
        ],
        "limits": "Full author mask spatially matched to an exposed test chip. The initial all-zero sample stays retained. Positive tile was selected after a label row scan for development feasibility; not an unbiased or heldout estimate. SAR-derived labels may share information with SAR inputs.",
    }


def gwis(output):
    path = captured(11, "gwis-native-chart-api")
    obj = json.loads(path.read_text())
    dates = [datetime.fromisoformat(x) for x in obj["x_data"]]
    if dates != sorted(set(dates)) or "fwi" not in obj["y_data"]:
        raise ValueError("Unexpected fire-index time series")
    for values in obj["y_data"].values():
        if len(values) != len(dates) or not np.isfinite(values).all():
            raise ValueError("Invalid fire-index values")
    return {
        "source_id": "AW-GWIS",
        "level": "native_point_index_series",
        "files": [bind(path), bind(captured(9, "gwis-app-code"))],
        "details": {"location": {"lon": -4, "lat": 40}, "model": "ecmwf", **obj},
        "limits": "Official GWIS chart backend provides five daily points and eight indices. FWI is a fire-weather index, not fire occurrence probability. The response does not distinguish archived issue versions or certify historical release times; raw forecast-grid export is still separate.",
    }


def effis(output):
    config = captured(14, "effis-page-code-1")
    code = config.read_text()
    start = code.index('le={domain:"effis"')
    end = code.index("app_code=EFFISCSV", start)
    endpoint = "https://api.effis.emergency.copernicus.eu/rest/2/burntareas/charts/wms?model=ecmwf"
    if endpoint not in code[start:end] or 'case"effis":N=le' not in code:
        raise ValueError("EFFIS-specific frontend does not bind the numerical API")
    path = captured(15, "effis-native-chart-api")
    obj = json.loads(path.read_text())
    dates = [datetime.fromisoformat(x) for x in obj["x_data"]]
    if dates != sorted(set(dates)) or "fwi" not in obj["y_data"]:
        raise ValueError("Unexpected EFFIS series")
    for values in obj["y_data"].values():
        if len(values) != len(dates) or not np.isfinite(values).all():
            raise ValueError("Invalid EFFIS index values")
    return {
        "source_id": "AW-EFFIS",
        "level": "native_point_index_series",
        "files": [bind(path), bind(config), bind(captured(12, "effis-v2-app"))],
        "details": {
            "location": {"lon": -7, "lat": 42},
            "model": "ecmwf",
            **obj,
            "frontend_binding_verified": True,
            "shares_backend_with": "AW-GWIS",
        },
        "limits": "New EFFIS frontend explicitly binds the sampled numeric API. This is another point query on the shared GWIS/EFFIS ECMWF backend, not independent evidence. Original issue/version times and full native grid export are not verified.",
    }


def context_examples(output):
    result = []
    for sid, number, ident in [
        ("D44", 5, "xbd-author-image"),
        ("D53", 5, "m4fog-author-example"),
    ]:
        path = captured(number, ident)
        with Image.open(path) as image:
            image.load()
            details = {"size": list(image.size), "mode": image.mode}
        result.append(
            {
                "source_id": sid,
                "level": "public_author_example_only",
                "files": [bind(path)],
                "details": details,
                "limits": "Author example only; no upgrade to complete xBD labels or native M4Fog multichannel cubes.",
            }
        )
    path = captured(5, "mscar-author-normalization")
    result.append(
        {
            "source_id": "D72",
            "level": "code_metadata_only",
            "files": [bind(path)],
            "details": json.loads(path.read_text()),
            "limits": "Normalization metadata is not a downloaded MSETCD image sample.",
        }
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    reports, failures = [], []
    for function in [tcir, camels, cems, floodnet, senfor, crisis, urban, gwis, effis]:
        try:
            report = function(args.output)
            reports.append(report)
            print(report["source_id"], report["level"], flush=True)
        except Exception as error:  # noqa: BLE001 -- Preserve each decoder failure in the report.
            failures.append(
                {
                    "decoder": function.__name__,
                    "type": type(error).__name__,
                    "error": str(error),
                }
            )
    reports.extend(context_examples(args.output))
    result = {
        "reports": reports,
        "failures": failures,
        "formal_new_tasks": 0,
        "new_model_calls": 0,
        "new_gpu_jobs": 0,
    }
    (args.output / "AUDIT.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n"
    )
    (args.output / "SOURCE_BINDINGS.json").write_text(
        json.dumps(list(HASHES.values()), indent=2) + "\n"
    )
    print(json.dumps({"reports": len(reports), "failures": failures}), flush=True)
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
