"""Audit the full registered EUPP station calendar against native hourly DWD data."""

import csv
import datetime as dt
import hashlib
import io
import json
import shutil
import zipfile
from collections import Counter
from itertools import pairwise
from pathlib import Path

import numcodecs
import numpy as np

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
PRIOR = REPO / "plans/v7_execution_20260913/sources_numerical"
ROOT = HERE / "temperature_extension_01"
OUT = ROOT / "decoded_01"
FC = "eupp_ensemble_forecasts_surface"
OB = "eupp_forecasts_observations_surface"


def load(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def iso(epoch):
    return (
        dt.datetime.fromtimestamp(float(epoch), dt.timezone.utc).isoformat().replace("+00:00", "Z")
    )


def finite(value):
    return float(value) if np.isfinite(value) else None


class VerifiedChunks:
    def __init__(self):
        calendar, acquisition = load(ROOT / "CALENDAR.json"), load(ROOT / "ACQUISITION.json")
        repairs = {}
        if not acquisition["all_verified"]:
            repair = load(ROOT / "retry_01/COMPLETE.json")
            if not repair["all_verified"]:
                raise ValueError(
                    "Coordinate acquisition is incomplete; never silently omit a source"
                )
            attempts = [
                json.loads(line)
                for line in (ROOT / "retry_01/RECEIPTS.jsonl").read_text().splitlines()
            ]
            if len(attempts) != len(acquisition["failures"]) or {
                r["relative"] for r in attempts
            } != {r["relative"] for r in acquisition["failures"]}:
                raise ValueError("Repair must match exactly the original failed source universe")
            repairs = {r["relative"]: r for r in attempts}
        old = [json.loads(line) for line in (PRIOR / "REQUESTS.jsonl").read_text().splitlines()]
        self.receipts = {
            r["name"]: (PRIOR / "raw" / r["name"], r["sha256"])
            for r in old
            if r.get("status") == 200 and "error" not in r
        }
        new = [
            json.loads(line)
            for line in (ROOT / "COORDINATE_RECEIPTS.jsonl").read_text().splitlines()
        ]
        if len(new) != len(calendar["requests"]) or {r["relative"] for r in new} != {
            r["relative"] for r in calendar["requests"]
        }:
            raise ValueError("Coordinate receipts do not cover the frozen request universe")
        for r in new:
            if r["status"] != "verified":
                r = repairs[r["relative"]]
                if r["status"] != "verified":
                    raise ValueError("Failed coordinate repair receipt")
                path = ROOT / "retry_01/coordinates" / r["relative"]
            else:
                path = ROOT / "coordinates" / r["relative"]
            self.receipts[r["relative"]] = (path, r["sha256"])
        self.manifest = {}
        self.metadata = {
            p: load(PRIOR / "raw" / (p + "_metadata.json"))["metadata"] for p in (FC, OB)
        }
        for p in (FC, OB):
            self.read_bytes(p + "_metadata.json")

    def read_bytes(self, name):
        path, sha = self.receipts[name]
        payload = path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != sha:
            raise ValueError("Source bytes differ from acquisition receipt: " + name)
        self.manifest[name] = {"path": str(path), "sha256": sha, "bytes": len(payload)}
        return payload

    def chunk(self, prefix, variable, key):
        spec = self.metadata[prefix][variable + "/.zarray"]
        if spec["zarr_format"] != 2 or spec.get("filters"):
            raise ValueError("Only unfiltered Zarr v2 chunks are registered")
        payload = self.read_bytes(prefix + "/" + variable + "/" + key)
        if spec["compressor"]:
            payload = numcodecs.get_codec(spec["compressor"]).decode(payload)
        dtype = np.dtype(spec["dtype"])
        if len(payload) != int(np.prod(spec["chunks"])) * dtype.itemsize:
            raise ValueError("Decoded source chunk has incorrect size")
        return np.frombuffer(payload, dtype=dtype).reshape(spec["chunks"], order=spec["order"])


def point_summary(rows):
    scored = [
        r for r in rows if r["forecast_complete"] and r["evaluator_only"]["dwd_K"] is not None
    ]
    result = {
        "registered": len(rows),
        "scored": len(scored),
        "missing_native_outcome": sum(r["evaluator_only"]["dwd_K"] is None for r in rows),
        "missing_forecast": sum(not r["forecast_complete"] for r in rows),
        "native_quality_counts": dict(Counter(r["evaluator_only"]["QN_9"] for r in rows)),
        "arms": {},
    }
    for arm in ("mean", "median"):
        errors = [r["predictions"][arm] - r["evaluator_only"]["dwd_K"] for r in scored]
        result["arms"][arm] = {
            "MAE_K": float(np.mean(np.abs(errors))) if errors else None,
            "RMSE_K": float(np.sqrt(np.mean(np.square(errors)))) if errors else None,
            "bias_K": float(np.mean(errors)) if errors else None,
        }
    for name, op, threshold in [
        ("cold_point_lt_273_15K", "lt", 273.15),
        ("hot_point_ge_303_15K", "ge", 303.15),
    ]:
        labels = [
            int(r["evaluator_only"]["dwd_K"] < threshold)
            if op == "lt"
            else int(r["evaluator_only"]["dwd_K"] >= threshold)
            for r in scored
        ]
        probs = [r["point_probabilities"][name] for r in scored]
        unique = {r["valid_time"]: y for r, y in zip(scored, labels)}
        result[name] = {
            "scored": len(labels),
            "positive_opportunities": sum(labels),
            "unique_scored_targets": len(unique),
            "unique_positive_targets": sum(unique.values()),
            "raw_ensemble_Brier": float(np.mean([(p - y) ** 2 for p, y in zip(probs, labels)]))
            if labels
            else None,
            "probability_calibrated": False,
            "duration_event": False,
        }
    return result


def main():
    card = load(ROOT / "THERMAL_TARGET_CARD.json")
    if not card["no_refit"]:
        raise ValueError("Unexpected mutable target card")
    source = VerifiedChunks()
    OUT.mkdir(exist_ok=False)
    shutil.copyfile(__file__, OUT / "decoder.py")
    save(
        OUT / "FROZEN_INPUTS.json",
        {
            "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "calendar_sha256": digest(ROOT / "CALENDAR.json"),
            "card_sha256": digest(ROOT / "THERMAL_TARGET_CARD.json"),
            "acquisition_sha256": digest(ROOT / "ACQUISITION.json"),
            "decoder_sha256": digest(OUT / "decoder.py"),
        },
    )
    f = source.chunk(FC, "t2m", "0.0.0.0.0")[0, :, :, :, 0].astype(np.float64)
    o = source.chunk(OB, "t2m", "0.0.0")[:, :, 0]
    steps = source.chunk(FC, "step", "0")
    np.testing.assert_array_equal(steps, source.chunk(OB, "step", "0"))
    if f.shape != (51, 730, 21) or o.shape != (730, 21):
        raise ValueError("Unexpected source array shapes")
    if (
        source.metadata[FC]["t2m/.zattrs"]["units"] != "K"
        or source.metadata[FC]["t2m/.zattrs"]["GRIB_stepType"] != "instant"
    ):
        raise ValueError("Forecast unit or temporal support changed")
    for prefix in (FC, OB):
        if source.metadata[prefix]["time/.zattrs"]["units"] != "seconds since 1970-01-01":
            raise ValueError("Unexpected time epoch")
    station = int(source.chunk(FC, "station_id", "0")[0])
    if station != 460 or station != int(source.chunk(OB, "station_id", "0")[0]):
        raise ValueError("Station identity differs")
    for a, b in [("station_latitude", "latitude"), ("station_longitude", "longitude")]:
        np.testing.assert_array_equal(source.chunk(FC, a, "0"), source.chunk(OB, b, "0"))
    members = source.chunk(FC, "number", "0").tolist()
    if len(set(members)) != 51:
        raise ValueError("Ensemble member identity incomplete")
    origins, valid_times = [], []
    for i in range(730):
        origin = int(source.chunk(FC, "time", str(i))[0])
        if origin != int(source.chunk(OB, "time", str(i))[0]):
            raise ValueError("Forecast and packaged observation initialization differ")
        valid = source.chunk(FC, "valid_time", str(i) + ".0")[0]
        np.testing.assert_array_equal(valid, origin + steps * 3600)
        origins.append(origin)
        valid_times.append(valid)
    if len(set(origins)) != 730 or any(b <= a for a, b in pairwise(origins)):
        raise ValueError("Initialization calendar is duplicate or unordered")
    first = dt.datetime.fromtimestamp(min(map(min, valid_times)), dt.timezone.utc).strftime(
        "%Y%m%d"
    )
    last = dt.datetime.fromtimestamp(max(map(max, valid_times)), dt.timezone.utc).strftime("%Y%m%d")
    native_zip = source.read_bytes("dwd_berus_hourly_temperature.zip")
    with zipfile.ZipFile(io.BytesIO(native_zip)) as archive:
        if archive.testzip() is not None:
            raise ValueError("DWD archive CRC failure")
        meta_text = archive.read("Metadaten_Parameter_tu_stunde_00460.txt").decode("latin1")
        meta = [
            {k.strip(): (v or "").strip() for k, v in row.items() if k is not None}
            for row in csv.DictReader(io.StringIO(meta_text), delimiter=";")
        ]
        applicable = [
            r
            for r in meta
            if r.get("Parameter") == "TT_TU" and r["Von_Datum"] <= first and r["Bis_Datum"] >= last
        ]
        if (
            len(applicable) != 1
            or applicable[0]["Einheit"] != "\u00b0C"
            or "UTC" not in applicable[0]["Zusatz-Info"]
        ):
            raise ValueError("DWD unit and UTC convention do not cover the whole calendar")
        product = next(n for n in archive.namelist() if n.startswith("produkt_tu_stunde"))
        product_bytes = archive.read(product)
        dwd, duplicates = {}, 0
        for row in csv.DictReader(io.StringIO(product_bytes.decode("utf-8-sig")), delimiter=";"):
            row = {k.strip(): (v or "").strip() for k, v in row.items() if k is not None}
            hour = row["MESS_DATUM"]
            if first <= hour[:8] <= last:
                if int(row["STATIONS_ID"]) != station:
                    raise ValueError("DWD row belongs to another station")
                if hour in dwd:
                    duplicates += 1
                    if dwd[hour] != row:
                        raise ValueError("Conflicting DWD rows at one target time")
                dwd[hour] = row
    records, consistency = [], Counter()
    for i, (origin, valid) in enumerate(zip(origins, valid_times)):
        for j, lead in enumerate(steps):
            at = dt.datetime.fromtimestamp(float(valid[j]), dt.timezone.utc)
            raw = dwd.get(at.strftime("%Y%m%d%H"))
            value_c = float(raw["TT_TU"]) if raw and raw["TT_TU"] else None
            if value_c == -999 or (value_c is not None and not np.isfinite(value_c)):
                value_c = None
            value = value_c + 273.15 if value_c is not None else None
            obs = finite(o[i, j])
            match = value is not None and obs is not None and abs(value - obs) < 1e-6
            compare = (
                "match"
                if match
                else (
                    "both_missing"
                    if value is None and obs is None
                    else "native_missing"
                    if value is None
                    else "packaged_missing"
                    if obs is None
                    else "disagreement"
                )
            )
            consistency[compare] += 1
            complete = bool(np.isfinite(f[:, i, j]).all())
            row = {
                "record_id": f"eupp_dwd_{station}_{origin}_lead{int(lead)}",
                "initialization_index": i,
                "forecast_reference_time": iso(origin),
                "valid_time": iso(valid[j]),
                "lead_hours": int(lead),
                "season": ["DJF", "MAM", "JJA", "SON"][(at.month % 12) // 3],
                "year": at.year,
                "target_support": "instant",
                "unit": "K",
                "forecast_complete": complete,
                "future_eligible": bool(lead > 4),
                "model_visible": {
                    "member_ids": members,
                    "members_K": [finite(x) for x in f[:, i, j]],
                },
                "predictions": {
                    "mean": float(np.mean(f[:, i, j], dtype=np.float64)) if complete else None,
                    "median": float(np.median(f[:, i, j])) if complete else None,
                },
                "point_probabilities": {
                    "cold_point_lt_273_15K": float(np.mean(f[:, i, j] < 273.15))
                    if complete
                    else None,
                    "hot_point_ge_303_15K": float(np.mean(f[:, i, j] >= 303.15))
                    if complete
                    else None,
                },
                "evaluator_only": {
                    "dwd_K": value,
                    "dwd_raw_C": value_c,
                    "QN_9": raw.get("QN_9") if raw else None,
                    "native_row": raw,
                    "eupp_packaged_K": obs,
                    "source_comparison": compare,
                },
            }
            records.append(row)
    future = [r for r in records if r["future_eligible"]]
    if len(records) != 15330 or len(future) != 14600:
        raise ValueError("Frozen denominator changed")
    # Select replay units by calendar index only, before inspecting their losses.
    monthly = {}
    for i, epoch in enumerate(origins):
        monthly.setdefault(iso(epoch)[:7], i)
    replay_ids = [r["record_id"] for r in future if r["initialization_index"] in monthly.values()]
    save(
        OUT / "REPLAY_SELECTION.json",
        {
            "rule": "first native initialization in every calendar month, all positive leads",
            "opportunity_ids": replay_ids,
            "outcome_selection": False,
        },
    )
    with (OUT / "RECORDS.jsonl").open("x") as handle:
        for row in records:
            handle.write(json.dumps(row, allow_nan=False) + "\n")
    report = {
        "schema": "disastertrace.temperature_calendar_decode.v1",
        "records": len(records),
        "initializations": len(origins),
        "forecast_date_start": iso(origins[0]),
        "forecast_date_end": iso(origins[-1]),
        "valid_time_start": first,
        "valid_time_end": last,
        "forecast_shape": list(f.shape),
        "observation_shape": list(o.shape),
        "initialization_step_hours": dict(
            Counter(str((b - a) / 3600) for a, b in pairwise(origins))
        ),
        "source_comparison": dict(consistency),
        "DWD_parameter_metadata": applicable[0],
        "duplicate_identical_DWD_rows": duplicates,
        "DWD_product": product,
        "DWD_product_sha256": hashlib.sha256(product_bytes).hexdigest(),
        "source_zip_sha256": hashlib.sha256(native_zip).hexdigest(),
        "all_future": point_summary(future),
        "by_season": {
            s: point_summary([r for r in future if r["season"] == s])
            for s in ("DJF", "MAM", "JJA", "SON")
        },
        "by_lead_hours": {
            str(int(h)): point_summary([r for r in future if r["lead_hours"] == h])
            for h in steps
            if h > 4
        },
        "model_calls": 0,
        "historical_publication_proved": False,
        "independent_confirmation": False,
        "limitations": [
            "One station; repeated leads and adjacent valid times are dependent.",
            "Archive availability uses initialization +3h, cutoff +4h; not actual first-seen proof.",
            "Native QN_9 is retained, without retroactive outcome-dependent filtering.",
            "Hot/cold point diagnostics do not define heatwaves, cold waves or frost damage.",
            "Packaged and native observations remain distinct; no silent replacement.",
        ],
    }
    save(OUT / "SOURCE_MANIFEST.json", source.manifest)
    save(OUT / "REPORT.json", report)
    save(
        OUT / "VALIDATION.json",
        {
            "passed": True,
            "verified_source_objects": len(source.manifest),
            "all_time_coordinates_verified": True,
            "all_native_records_retained": True,
            "qualified_future_opportunities": len(future),
            "forecast_and_native_units_and_UTC_verified": True,
            "output_files": {p.name: digest(p) for p in OUT.iterdir() if p.is_file()},
            "model_calls": 0,
        },
    )
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "records",
                    "forecast_date_start",
                    "forecast_date_end",
                    "source_comparison",
                    "all_future",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
