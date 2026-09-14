"""Decode real MRMS grids without inventing unknown units or negative-code meanings."""

import datetime as dt
import gzip
import hashlib
import json
from collections import Counter
from itertools import pairwise
from pathlib import Path

import eccodes
import numpy as np

ROOT = Path(__file__).resolve().parents[1] / "h07_extension_01"
OUT = ROOT / "decoded_01"


def save(name, value):
    with (OUT / name).open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def main():
    plan = json.loads((ROOT / "PLAN.json").read_text())
    receipts = [json.loads(line) for line in (ROOT / "RECEIPTS.jsonl").read_text().splitlines()]
    rows = [r for r in receipts if r["kind"] == "native_grid"]
    if len(rows) != 12 or any(r["status"] != "verified" for r in rows):
        raise ValueError("Full fixed twelve-hour universe is required")
    OUT.mkdir(exist_ok=False)
    keys = [
        "edition",
        "discipline",
        "centre",
        "subCentre",
        "tablesVersion",
        "localTablesVersion",
        "parameterCategory",
        "parameterNumber",
        "productDefinitionTemplateNumber",
        "typeOfFirstFixedSurface",
        "gridType",
        "Ni",
        "Nj",
        "latitudeOfFirstGridPointInDegrees",
        "longitudeOfFirstGridPointInDegrees",
        "latitudeOfLastGridPointInDegrees",
        "longitudeOfLastGridPointInDegrees",
        "iDirectionIncrementInDegrees",
        "jDirectionIncrementInDegrees",
        "iScansNegatively",
        "jScansPositively",
        "jPointsAreConsecutive",
        "alternativeRowScanning",
        "dataDate",
        "dataTime",
        "second",
        "stepType",
        "startStep",
        "endStep",
        "units",
        "name",
        "numberOfDataPoints",
        "bitmapPresent",
        "missingValue",
    ]
    reports, patches, times = [], [], []
    previous_grid = None
    for row in rows:
        path = ROOT / "raw" / row["name"]
        payload = path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != row["sha256"]:
            raise ValueError("Native bytes differ from HTTP receipt")
        native = gzip.decompress(payload)
        if (
            native[:4] != b"GRIB"
            or native[-4:] != b"7777"
            or int.from_bytes(native[8:16], "big") != len(native)
        ):
            raise ValueError("Single complete GRIB2 message required")
        gid = eccodes.codes_new_from_message(native)
        try:
            meta = {k: eccodes.codes_get(gid, k) for k in keys}
            if [meta[k] for k in ("discipline", "parameterCategory", "parameterNumber")] != [
                209,
                6,
                37,
            ]:
                raise ValueError("MRMS local parameter identity changed")
            if [
                meta[k]
                for k in (
                    "Ni",
                    "Nj",
                    "iScansNegatively",
                    "jScansPositively",
                    "jPointsAreConsecutive",
                    "alternativeRowScanning",
                )
            ] != [7000, 3500, 0, 0, 0, 0]:
                raise ValueError("Grid orientation differs from the registered native geometry")
            when = dt.datetime.strptime(
                str(meta["dataDate"]) + str(meta["dataTime"]).zfill(4), "%Y%m%d%H%M"
            ).replace(tzinfo=dt.timezone.utc)
            if (
                when.isoformat().replace("+00:00", "Z") != row["nominal_time"]
                or meta["second"] != 0
            ):
                raise ValueError("Filename and GRIB reference time differ")
            times.append(when)
            latitude = (
                meta["latitudeOfFirstGridPointInDegrees"]
                - np.arange(meta["Nj"]) * meta["jDirectionIncrementInDegrees"]
            )
            longitude = (
                meta["longitudeOfFirstGridPointInDegrees"]
                + np.arange(meta["Ni"]) * meta["iDirectionIncrementInDegrees"]
                - 360
            )
            grid = {k: meta[k] for k in keys if k not in ("dataDate", "dataTime", "second")}
            if previous_grid is not None and previous_grid != grid:
                raise ValueError("Temporal sequence changes grid or product metadata")
            previous_grid = grid
            values = eccodes.codes_get_values(gid).reshape(meta["Nj"], meta["Ni"])
            if not np.isfinite(values).all():
                raise ValueError("Nonfinite packed values require another validity contract")
            negative, counts = np.unique(values[values < 0], return_counts=True)
            box = plan["regional_diagnostic_bounds"]
            iy = np.flatnonzero((latitude >= box["lat_min"]) & (latitude <= box["lat_max"]))
            ix = np.flatnonzero((longitude >= box["lon_min"]) & (longitude <= box["lon_max"]))
            patch = values[np.ix_(iy, ix)].copy()
            patches.append(patch)
            # The mathematical grid formula is checked against ecCodes' geolocation.
            ji, ii = int(iy[len(iy) // 2]), int(ix[len(ix) // 2])
            nearest = eccodes.codes_grib_find_nearest(
                gid, float(latitude[ji]), float(longitude[ii])
            )[0]
            if (
                nearest["index"] != ji * meta["Ni"] + ii
                or abs(nearest["value"] - values[ji, ii]) > 1e-9
            ):
                raise ValueError("Regional crop geolocation differs from native decoder")
            reports.append(
                {
                    "name": row["name"],
                    "source_sha256": row["sha256"],
                    "metadata": meta,
                    "gzip_crc_and_grib_length_verified": True,
                    "numeric_values": int(values.size),
                    "negative_raw_codes": {str(float(x)): int(n) for x, n in zip(negative, counts)},
                    "positive_raw_values": int(np.sum(values > 0)),
                    "zero_raw_values": int(np.sum(values == 0)),
                    "raw_min": float(values.min()),
                    "raw_max": float(values.max()),
                    "crop_shape": list(patch.shape),
                    "crop_nonnegative": int(np.sum(patch >= 0)),
                    "crop_negative_codes": dict(Counter(str(float(v)) for v in patch[patch < 0])),
                    "S3_last_modified": row["last_modified"],
                    "time_interpretation": "native GRIB reference time; physical accumulation support awaits official mapping",
                }
            )
            print(json.dumps({"decoded": len(reports), "expected": 12}), flush=True)
        finally:
            eccodes.codes_release(gid)
    if any((b - a).total_seconds() != 3600 for a, b in pairwise(times)):
        raise ValueError("Sequence contains missing or duplicate nominal hours")
    np.savez_compressed(
        OUT / "native_regional_patches.npz",
        raw_values=np.stack(patches),
        latitude=latitude[iy],
        longitude=longitude[ix],
        reference_epoch_seconds=np.array([int(t.timestamp()) for t in times]),
    )
    save(
        "REPORT.json",
        {
            "hazard": "H07",
            "source_objects": 12,
            "decoded_numeric_values": 12 * 24_500_000,
            "nominal_hourly_continuity_verified": True,
            "native_product_identity": {"discipline": 209, "category": 6, "number": 37},
            "grids": reports,
            "semantic_gates": {
                "official_product_local_table_mapping": False,
                "accumulation_interval": False,
                "units": False,
                "negative_code_meanings": False,
                "historical_available_at": False,
            },
            "remaining": [
                "Replace retired NSSL operational documentation URLs (verified TLS yields HTTP410).",
                "Bind official product table and quality-code definitions before assigning physical units or scores.",
                "Pass2 product estimates are not physical ground truth or a radar rain-rate stream.",
                "A twelve-hour sequence is a continuity pilot, not an independent extreme process confirmation.",
            ],
            "formal_F_score": False,
            "native_MM_comparison": False,
            "model_calls": 0,
        },
    )
    save(
        "VALIDATION.json",
        {
            "passed_native_decode": True,
            "files": {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in OUT.iterdir()
                if p.is_file()
            },
            "physical_semantics_qualified": False,
            "model_calls": 0,
        },
    )


if __name__ == "__main__":
    main()
