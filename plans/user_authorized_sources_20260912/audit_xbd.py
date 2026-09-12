"""Verify complete xBD members recovered from bounded authorized archive prefixes."""

import argparse
import gzip
import hashlib
import json
import tarfile
from collections import Counter
from datetime import datetime
from pathlib import Path

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.transform import Affine
from shapely import wkt
from shapely.affinity import affine_transform

ROOT = Path(__file__).resolve().parent


def bound(path):
    data = path.read_bytes()
    return {
        "path": str(path.relative_to(ROOT)),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def selected_members(path, names):
    found, boundary = {}, None
    try:
        with tarfile.open(path, mode="r|gz") as archive:
            for member in archive:
                name = Path(member.name).name
                if member.isfile() and name in names:
                    raw = archive.extractfile(member).read()
                    if len(raw) == member.size:
                        if name in found:
                            raise ValueError("Duplicate selected archive member")
                        found[name] = raw
    except (EOFError, tarfile.ReadError) as error:
        boundary = type(error).__name__
    if set(found) != set(names):
        raise ValueError("Not all selected members are complete")
    return found, boundary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    selection = json.loads((ROOT / "decoded/XBD_SELECTION_02.json").read_text())
    names = [
        ident + "_" + phase + "_disaster"
        for ident in selection["ids"]
        for phase in ["pre", "post"]
    ]
    sources = {
        "native": ROOT / "captures/xbd_full_prefix_03/response.body",
        "labels": ROOT / "captures/xbd_hold_prefix_03/response.body",
        "geotransforms": ROOT / "captures/xbd_geotransforms_02/response.body",
    }
    bindings = []
    for path in sources.values():
        receipt = json.loads((path.parent / "RECEIPT.json").read_text())
        binding = bound(path)
        if receipt["curl_exit"] or receipt["http_status"] not in [200, 206]:
            raise ValueError("Source transfer is incomplete")
        if (
            binding["sha256"] != receipt["sha256"]
            or binding["bytes"] != receipt["bytes"]
        ):
            raise ValueError("Source receipt mismatch")
        bindings.extend([binding, bound(path.parent / "RECEIPT.json")])
    if (
        hashlib.sha1(sources["geotransforms"].read_bytes()).hexdigest()
        != "0b3bda08084ac102d8b540261ebbba0094203a2f"
    ):
        raise ValueError("Published metadata SHA1 does not match")
    with gzip.open(sources["geotransforms"], "rb") as stream:
        while stream.read(1024**2):
            pass
    with tarfile.open(sources["geotransforms"], "r:gz") as archive:
        geo = json.loads(archive.extractfile("xview_geotransforms.json").read())
    native, native_boundary = selected_members(
        sources["native"], {n + ".tif" for n in names}
    )
    labels, label_boundary = selected_members(
        sources["labels"], {n + ".json" for n in names}
    )
    rows, pairs = [], []
    for name in names:
        path = ROOT / "extracted/xbd_pairs" / (name + ".tif")
        if path.read_bytes() != native[name + ".tif"]:
            raise ValueError("Extracted image differs from captured member")
        if path.with_suffix(".json").read_bytes() != labels[name + ".json"]:
            raise ValueError("Extracted label differs from captured member")
        label = json.loads(labels[name + ".json"])
        metadata = label["metadata"]
        if (
            metadata["img_name"] != name + ".png"
            or metadata["disaster"] != "hurricane-florence"
        ):
            raise ValueError("Annotation is not for the selected image")
        with rasterio.open(path) as dataset:
            expected, crs = geo[metadata["img_name"]]
            if dataset.crs != CRS.from_wkt(crs) or not np.allclose(
                tuple(dataset.transform),
                tuple(Affine.from_gdal(*expected)),
                rtol=0,
                atol=1e-12,
            ):
                raise ValueError("Native georeferencing differs from official metadata")
            if (dataset.width, dataset.height) != (
                metadata["width"],
                metadata["height"],
            ):
                raise ValueError("Image/annotation dimensions differ")
            transform = dataset.transform
            values = dataset.read()
            xy = {f["properties"]["uid"]: f for f in label["features"]["xy"]}
            geographic = {
                f["properties"]["uid"]: f for f in label["features"]["lng_lat"]
            }
            if (
                set(xy) != set(geographic)
                or len(xy) != len(label["features"]["xy"])
                or len(geographic) != len(label["features"]["lng_lat"])
            ):
                raise ValueError("Building identities do not align")
            residuals, pixel_residuals, invalid = [], [], 0
            inverse = ~transform
            for uid, feature in xy.items():
                pixels = wkt.loads(feature["wkt"])
                ground = wkt.loads(geographic[uid]["wkt"])
                projected = affine_transform(
                    pixels,
                    [
                        transform.a,
                        transform.b,
                        transform.d,
                        transform.e,
                        transform.c,
                        transform.f,
                    ],
                )
                residuals.append(projected.hausdorff_distance(ground))
                ground_pixels = affine_transform(
                    ground,
                    [inverse.a, inverse.b, inverse.d, inverse.e, inverse.c, inverse.f],
                )
                pixel_residuals.append(pixels.hausdorff_distance(ground_pixels))
                invalid += int(not pixels.is_valid or not ground.is_valid)
            rows.append(
                {
                    "image": path.name,
                    "shape": list(values.shape),
                    "dtype": str(values.dtype),
                    "min": int(values.min()),
                    "max": int(values.max()),
                    "crs": str(dataset.crs),
                    "transform": list(transform),
                    "capture_time": metadata["capture_date"],
                    "disaster": metadata["disaster"],
                    "disaster_type": metadata["disaster_type"],
                    "sensor": metadata["sensor"],
                    "features": len(xy),
                    "damage_labels": dict(
                        Counter(
                            f["properties"].get("subtype", "not_provided_pre_event")
                            for f in xy.values()
                        )
                    ),
                    "invalid_geometry_pairs": invalid,
                    "max_xy_to_geographic_residual_degrees": max(residuals, default=0),
                    "max_geometry_residual_pixels": max(pixel_residuals, default=0),
                    "median_geometry_residual_pixels": float(np.median(pixel_residuals))
                    if pixel_residuals
                    else None,
                    "geometry_pairs_exceeding_one_pixel": sum(
                        v > 1 for v in pixel_residuals
                    ),
                    "geographic_label_alignment_passed": bool(pixel_residuals)
                    and invalid == 0
                    and max(pixel_residuals) <= 1,
                    "image_sha256": hashlib.sha256(native[name + ".tif"]).hexdigest(),
                    "label_sha256": hashlib.sha256(labels[name + ".json"]).hexdigest(),
                }
            )
            bindings.extend([bound(path), bound(path.with_suffix(".json"))])
    for ident in selection["ids"]:
        pre, post = [
            next(r for r in rows if r["image"] == ident + "_" + phase + "_disaster.tif")
            for phase in ["pre", "post"]
        ]
        first, second = [
            datetime.fromisoformat(r["capture_time"].replace("Z", "+00:00"))
            for r in [pre, post]
        ]
        if second <= first:
            raise ValueError("Post-event acquisition does not follow pre-event image")
        pairs.append(
            {
                "id": ident,
                "pre_capture": pre["capture_time"],
                "post_capture": post["capture_time"],
                "gap_hours": (second - first).total_seconds() / 3600,
                "same_native_transform": pre["transform"] == post["transform"],
                "post_damage_labels": post["damage_labels"],
            }
        )
    report = {
        "source_id": "D44",
        "state": "decoded_sample",
        "paired_samples": len(pairs),
        "metadata_entries": len(geo),
        "metadata_published_sha1_and_gzip_crc_verified": True,
        "full_native_archive_sha1_verified": False,
        "full_challenge_archive_sha1_verified": False,
        "prefix_boundaries": {"native": native_boundary, "labels": label_boundary},
        "selection": selection,
        "images": rows,
        "pairs": pairs,
        "files": bindings,
        "spatial_grounding_admitted": all(
            r["geographic_label_alignment_passed"] for r in rows
        ),
        "spatial_check_tolerance_pixels": 1,
        "native_pixel_label_overlay_validated": False,
        "new_formal_tasks": 0,
        "new_model_calls": 0,
        "limits": "Three development pairs from the published hold split, one Florence process. Unclassified damage stays unknown. Complete selected members, not complete multi-part archives. Capture times do not establish publication/availability times. Native and challenge representations share an official image identity, not independent evidence. Pixel/geographic annotation transforms are inconsistent with the native affine; spatial grounding is blocked and original PNG-to-TIFF pixel alignment is not established. No empirical repair fitted on evaluation labels.",
    }
    (args.output / "AUDIT.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n"
    )
    print(
        json.dumps(
            {
                "paired_samples": len(pairs),
                "pairs": pairs,
                "geometry_residual_degrees": max(
                    r["max_xy_to_geographic_residual_degrees"] for r in rows
                ),
            }
        )
    )


if __name__ == "__main__":
    main()
