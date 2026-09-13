"""Decode only downloaded Zarr chunks; never opens the network or fills missing data."""
import csv
import datetime as dt
import io
import json
import zipfile
from pathlib import Path

import numcodecs
import numpy as np

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "raw"


def read_chunk(prefix, variable, key):
    metadata = json.loads((RAW / (prefix + "_metadata.json")).read_text())["metadata"]
    spec = metadata[variable + "/.zarray"]
    if spec["zarr_format"] != 2 or spec.get("filters"):
        raise ValueError("Probe decoder supports only unfiltered Zarr v2 arrays")
    buf = (RAW / prefix / variable / key).read_bytes()
    if spec["compressor"]:
        buf = numcodecs.get_codec(spec["compressor"]).decode(buf)
    dtype = np.dtype(spec["dtype"])
    expected = int(np.prod(spec["chunks"])) * dtype.itemsize
    if len(buf) != expected:
        raise ValueError(f"Chunk size mismatch: {prefix}/{variable}/{key}")
    return np.frombuffer(buf, dtype=dtype).reshape(spec["chunks"], order=spec["order"])


def iso(epoch):
    return dt.datetime.fromtimestamp(float(epoch), dt.timezone.utc).isoformat().replace("+00:00", "Z")


def safe(value):
    return float(value) if np.isfinite(value) else None


def write(name, value):
    (ROOT / name).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def eupp():
    fc, ob = "eupp_ensemble_forecasts_surface", "eupp_forecasts_observations_surface"
    f = read_chunk(fc, "t2m", "0.0.0.0.0")[0, :, :, :, 0]
    o = read_chunk(ob, "t2m", "0.0.0")[:, :, 0]
    steps = read_chunk(fc, "step", "0")
    np.testing.assert_array_equal(steps, read_chunk(ob, "step", "0"))
    station = int(read_chunk(fc, "station_id", "0")[0])
    assert station == int(read_chunk(ob, "station_id", "0")[0])
    np.testing.assert_array_equal(read_chunk(fc, "station_latitude", "0"), read_chunk(ob, "latitude", "0"))
    np.testing.assert_array_equal(read_chunk(fc, "station_longitude", "0"), read_chunk(ob, "longitude", "0"))
    name = str(read_chunk(fc, "station_name", "0")[0])
    members = read_chunk(fc, "number", "0").tolist()
    # A separate DWD product establishes the unlabelled observation unit and retains QC.
    with zipfile.ZipFile(RAW / "dwd_berus_hourly_temperature.zip") as archive:
        assert archive.testzip() is None
        parameter_text = archive.read("Metadaten_Parameter_tu_stunde_00460.txt").decode("latin1")
        parameter_rows = list(csv.DictReader(io.StringIO(parameter_text), delimiter=";"))
        applicable = [row for row in parameter_rows if row.get("Parameter") == "TT_TU"
                      and row["Von_Datum"] <= "20170101" and row["Bis_Datum"] >= "20170108"]
        assert len(applicable) == 1
        assert applicable[0]["Einheit"] == "\u00b0C"
        assert "UTC" in applicable[0]["Zusatz-Info"]
        product = next(n for n in archive.namelist() if n.startswith("produkt_tu_stunde"))
        rows = csv.DictReader(io.StringIO(archive.read(product).decode("utf-8-sig")), delimiter=";")
        dwd = {}
        for row in rows:
            row = {k.strip(): v.strip() for k, v in row.items()}
            if row["MESS_DATUM"].startswith("201701"):
                dwd[row["MESS_DATUM"]] = row
    records, reference_matches = [], []
    for time_index in range(3):
        epoch = int(read_chunk(fc, "time", str(time_index))[0])
        assert epoch == int(read_chunk(ob, "time", str(time_index))[0])
        valid = read_chunk(fc, "valid_time", str(time_index) + ".0")[0]
        np.testing.assert_array_equal(valid, epoch + steps * 3600)
        for j, lead in enumerate(steps):
            hour = dt.datetime.fromtimestamp(float(valid[j]), dt.timezone.utc).strftime("%Y%m%d%H")
            reference = dwd.get(hour)
            observed = safe(o[time_index, j])
            raw_celsius = float(reference["TT_TU"]) if reference else None
            same = observed is not None and raw_celsius is not None and raw_celsius != -999 and abs(observed - (raw_celsius + 273.15)) < 1e-6
            reference_matches.append(same)
            records.append({
                "record_id": f"eupp_dwd_{station}_{epoch}_lead{int(lead)}",
                "dataset": "EUPPBench_station_forecast", "station_id": station,
                "station_name": name, "variable": "2m_temperature", "unit": "K",
                "forecast_reference_time": iso(epoch), "lead_hours": float(lead),
                "valid_time": iso(valid[j]), "target_support": "instant",
                "model_visible": {"member_ids": members, "forecast_members": [safe(x) for x in f[:, time_index, j]]},
                "evaluator_only": {"observation": observed, "dwd_raw_celsius": raw_celsius,
                    "dwd_QN_9": reference.get("QN_9") if reference else None, "dwd_unit_crosscheck": same},
                "historical_forecast_available_at": None,
                "historical_observation_available_at": None,
                "point_forecast_diagnostic_eligible": bool(lead > 0 and same),
                "formal_monitoring_eligible": False,
            })
    result = {"schema_version": "numerical_source_pairs_v1", "selection": "station index 0; initialization indices 0,1,2; all 21 published leads; no label-based selection",
              "purpose": "offline station temperature interface verification; not calibrated probabilities or extreme-event performance",
              "observation_unit_evidence": "Each sampled observation equals DWD TT_TU Celsius + 273.15, within 1e-6 K; EUPP observation metadata omits units",
              "member_count": len(members), "paired_record_count": len(records),
              "dwd_crosscheck_count": sum(reference_matches),
              "dwd_measurement_metadata_verified": {"unit": "Celsius", "time_basis": "UTC", "parameter": "TT_TU", "applicable_from": applicable[0]["Von_Datum"], "applicable_to": applicable[0]["Bis_Datum"]},
              "records": records}
    write("paired_records.json", result)
    return {"records": len(records), "dwd_matches": sum(reference_matches), "positive_lead_records": sum(r["point_forecast_diagnostic_eligible"] for r in records),
            "scientific_values_decoded": int(f.size + o.size), "forecast_shape": list(f.shape), "observation_shape": list(o.shape)}


def seeps():
    fp, op = "seeps_ifs", "seeps_obs"
    f = read_chunk(fp, "forecast", "0.0.0")
    o = read_chunk(op, "observation", "4.0")
    stnid = read_chunk(fp, "stnid", "0")
    np.testing.assert_array_equal(stnid, read_chunk(op, "stnid", "0"))
    for variable in ["lat", "lon"]:
        np.testing.assert_array_equal(read_chunk(fp, variable, "0"), read_chunk(op, variable, "0"))
    run = read_chunk(fp, "run", "0")
    lead = read_chunk(fp, "step", "0")
    obstime = read_chunk(op, "time", "0")
    np.testing.assert_array_equal(lead, np.arange(1, 11))
    obs_epoch = dt.datetime(2022, 1, 1, tzinfo=dt.timezone.utc)
    run_epoch = dt.datetime(2024, 6, 1, tzinfo=dt.timezone.utc)
    records = []
    for ir in range(3):
        init = run_epoch + dt.timedelta(days=int(run[ir]))
        for il in range(2):
            end = init + dt.timedelta(days=int(lead[il]))
            day_index = (end - obs_epoch).days
            indices = np.flatnonzero(obstime == day_index)
            assert len(indices) == 1
            oi = int(indices[0]) - 800
            assert 0 <= oi < o.shape[0]
            for si in range(3):
                obs = safe(o[oi, si])
                forecast = safe(f[il, ir, si])
                records.append({
                    "record_id": f"seeps_{int(stnid[si])}_{init.strftime('%Y%m%d')}_d{int(lead[il])}",
                    "dataset": "SEEPS4ALL_IFS_ECAD", "station_id": int(stnid[si]),
                    "forecast_reference_time": init.isoformat(), "lead_days": int(lead[il]),
                    "nominal_window_start": (end-dt.timedelta(days=1)).isoformat(),
                    "nominal_window_end": end.isoformat(), "variable": "precipitation_24h", "unit": "mm",
                    "model_visible": {"deterministic_forecast": forecast},
                    "evaluator_only": {"observation": obs, "source_qc_retained_as_individual_flags": False},
                    "station_physical_24h_window_verified": False,
                    "historical_forecast_available_at": None,
                    "historical_observation_available_at": None,
                    "formal_monitoring_eligible": False,
                    "nominal_offline_pair_present": forecast is not None and obs is not None,
                })
    result = {"schema_version": "numerical_source_pairs_v1", "selection": "station indices 0,1,2; initialization indices 0,1,2; lead indices 0,1; no label-based selection",
              "purpose": "nominal daily-pair decode diagnostic; physical station accumulation windows unverified",
              "metadata_cautions": ["forecast and observation unit attrs absent; mm inferred from pinned builder conversions", "ECA&D dates are shifted +24h in source builder; station-specific observation-hour convention absent", "source QC removes some extremes and does not retain per-record reasons"],
              "records": records}
    write("paired_rainfall_records.json", result)
    finite_f = f[np.isfinite(f)]
    return {"records": len(records), "nonmissing_pairs": sum(r["nominal_offline_pair_present"] for r in records),
            "scientific_values_decoded": int(f.size + o.size), "forecast_chunk_shape": list(f.shape), "observation_chunk_shape": list(o.shape),
            "negative_forecast_count_in_downloaded_chunk": int((finite_f < 0).sum()),
            "forecast_chunk_min_mm": float(finite_f.min()),
            "observation_chunk_missing_count": int(np.isnan(o).sum())}


def main():
    results = {"eupp": eupp(), "seeps4all": seeps(), "formal_monitoring_admissions": 0,
               "fresh_model_calls": 0, "network_required_for_decode": False,
               "decoder": {"numpy": np.__version__, "numcodecs": numcodecs.__version__}}
    write("DECODE_VALIDATION.json", results)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
