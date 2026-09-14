"""Pair native six-hour extrema with DWD daily references under an explicit scenario."""

import datetime as dt
import hashlib
import json
import math
import shutil
from collections import Counter, defaultdict
from pathlib import Path

import numcodecs
import numpy as np

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE / "temperature_daily_forecast_01"
OUT = ROOT / "analysis_01"
REF = HERE / "temperature_daily_reference_01/qualification_01"


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, value):
    with (OUT / name).open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def iso(epoch):
    return dt.datetime.fromtimestamp(int(epoch), dt.timezone.utc).isoformat()


def main():
    OUT.mkdir(exist_ok=False)
    shutil.copyfile(Path(__file__), OUT / "EXECUTED_SOURCE.py")
    spec = {
        "schema": "disastertrace.native_daily_extreme_candidate.v1",
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "station_id": 460,
        "member_count": 51,
        "initialization_selection": "All730acquired native coordinate indices, no event filtering.",
        "forecast_available_at_scenario": "native initialization plus3h;not historically proved first publication",
        "forecast_cutoff": "native initialization plus4h",
        "daily_target_indices": [1, 2, 3, 4],
        "daily_target_window": "UTC00:00to24:00;day0retained as an excluded partial-window case",
        "daily_maximum": "max of four complete consecutive native mx2t6 intervals",
        "daily_minimum": "min of four complete consecutive native mn2t6 intervals",
        "daily_predicates": read(REF / "TASK_SPEC.json")["daily_predicates"],
        "duration_candidates": read(REF / "TASK_SPEC.json")["duration_candidates"],
        "duration_start_day_indices": [1, 2],
        "duration_probability": "fraction of same-initialization ensemble members satisfying all3daily predicates;never a product of marginal probabilities",
        "outcome_reference_period": ["2017-01-01", "2018-12-31"],
        "out_of_reference_period": "retained as unscored, never imputed or selectively dropped",
        "forecast_track": "raw operational-ensemble product coordinate diagnostic under declared archive availability",
        "independent_confirmation": False,
        "new_model_calls": 0,
    }
    save("TASK_SPEC.json", spec)
    assert read(ROOT / "coordinates_01/COMPLETE.json")["all_coordinates_downloaded"]
    meta_receipt = read(ROOT / "ensemble_forecasts.receipt.json")
    assert sha(ROOT / "ensemble_forecasts.zmetadata") == meta_receipt["sha256"]
    metadata = read(ROOT / "ensemble_forecasts.zmetadata")["metadata"]
    receipts = {
        r["name"]: (ROOT / "sample_01" / r["name"], r["sha256"])
        for r in read(ROOT / "sample_01/RECEIPTS.json")
        if r["status"] == "downloaded"
    }
    for line in (ROOT / "coordinates_01/RECEIPTS.jsonl").read_text().splitlines():
        row = json.loads(line)
        assert row["status"] == "downloaded" and row["name"] not in receipts
        receipts[row["name"]] = (ROOT / "coordinates_01" / row["name"], row["sha256"])
    bindings = {}

    def chunk(variable, key):
        name = variable + "/" + key
        path, digest = receipts[name]
        payload = path.read_bytes()
        assert hashlib.sha256(payload).hexdigest() == digest
        array = metadata[variable + "/.zarray"]
        assert (
            array["zarr_format"] == 2
            and not array.get("filters")
            and array["order"] == "C"
        )
        decoded = numcodecs.get_codec(array["compressor"]).decode(payload)
        values = np.frombuffer(decoded, dtype=array["dtype"])
        assert values.size == math.prod(array["chunks"])
        bindings[name] = {"path": str(path.relative_to(HERE)), "sha256": digest}
        return values.reshape(array["chunks"])

    assert chunk("station_id", "0").item() == 460
    members = chunk("number", "0").reshape(-1)
    assert members.tolist() == list(range(51))
    steps = chunk("step", "0").reshape(-1)
    assert steps.tolist() == list(range(6, 121, 6))
    assert metadata["time/.zattrs"]["units"] == "seconds since 1970-01-01"
    assert metadata["valid_time/.zattrs"]["units"] == "hours since 2017-01-01T06:00:00"
    valid_origin = int(dt.datetime(2017, 1, 1, 6, tzinfo=dt.timezone.utc).timestamp())
    times = np.array([chunk("time", str(i)).item() for i in range(730)], dtype=np.int64)
    valid = np.stack(
        [
            chunk("valid_time", str(i) + ".0").reshape(-1) * 3600 + valid_origin
            for i in range(730)
        ]
    )
    assert np.array_equal(valid, times[:, None] + steps[None, :] * 3600)
    assert np.all(np.diff(times) == 86400) and np.all(times % 86400 == 0)
    assert iso(times[0]).startswith("2017-01-01T00:00")
    assert iso(times[-1]).startswith("2018-12-31T00:00")
    maximum = chunk("mx2t6", "0.0.0.0.0").reshape(51, 730, 20).astype(np.float64)
    minimum = chunk("mn2t6", "0.0.0.0.0").reshape(51, 730, 20).astype(np.float64)
    assert np.all(np.isfinite(maximum)) and np.all(np.isfinite(minimum))
    assert np.all(minimum <= maximum)
    daily_max = maximum.reshape(51, 730, 5, 4).max(axis=3)
    daily_min = minimum.reshape(51, 730, 5, 4).min(axis=3)
    # A scalar decoder independently checks every interval union and extreme.
    for i in range(730):
        for day in range(5):
            ends = valid[i, day * 4 : day * 4 + 4].tolist()
            assert ends == [
                int(times[i]) + day * 86400 + hour * 3600 for hour in (6, 12, 18, 24)
            ]
            for member in range(51):
                assert daily_max[member, i, day] == max(
                    maximum[member, i, day * 4 : day * 4 + 4].tolist()
                )
                assert daily_min[member, i, day] == min(
                    minimum[member, i, day * 4 : day * 4 + 4].tolist()
                )
    docs = ROOT / "docs_01/EUPPBench_datasets.rst.txt"
    table = ROOT / "units_01/eccodes_table_128.txt"
    assert (
        "over the last 6 hours\npreceding a given forecast timestamp"
        in docs.read_text()
    )
    for text in (
        "121 mx2t6 Maximum temperature at 2 metres in the last 6 hours (K)",
        "122 mn2t6 Minimum temperature at 2 metres in the last 6 hours (K)",
    ):
        assert text in table.read_text()
    references = {row["date"]: row for row in read(REF / "DAILY_REFERENCES.json")}
    assert len(references) == 730 and read(REF / "VALIDATION.json")["passed"]
    daily_rows, duration_rows, metrics = [], [], defaultdict(list)
    positive_keys = defaultdict(set)
    for i, initialization in enumerate(times.tolist()):
        cutoff = initialization + 4 * 3600
        for day in (1, 2, 3, 4):
            start = initialization + day * 86400
            assert cutoff < start
            date = iso(start)[:10]
            reference = references.get(date)
            maximum_C, minimum_C = (
                daily_max[:, i, day] - 273.15,
                daily_min[:, i, day] - 273.15,
            )
            if reference is not None:
                assert reference["physical_start"] == iso(start)
                assert reference["physical_end_exclusive"] == iso(start + 86400)
            row = {
                "initialization_index": i,
                "initialization": iso(initialization),
                "cutoff": iso(cutoff),
                "target_date": date,
                "day_index": day,
                "forecast_max_members_C": maximum_C.tolist(),
                "forecast_min_members_C": minimum_C.tolist(),
                "reference": reference,
                "reference_status": "mature_product"
                if reference
                else "outside_reference_period",
                "probabilities": {},
            }
            for event, flags in (
                ("hot_day", daily_max[:, i, day] >= 303.15),
                ("frost_day", daily_min[:, i, day] < 273.15),
                ("ice_day", daily_max[:, i, day] < 273.15),
            ):
                probability = float(flags.sum()) / 51
                row["probabilities"][event] = probability
                outcome = (
                    int(reference["daily_predicates"][event]) if reference else None
                )
                metrics[(event, day)].append((probability, outcome, date))
                if outcome == 1:
                    positive_keys[event].add(date)
            daily_rows.append(row)
        for start_day in (1, 2):
            dates = [
                iso(initialization + day * 86400)[:10]
                for day in range(start_day, start_day + 3)
            ]
            refs = [references.get(date) for date in dates]
            for name, daily_name, flags in (
                (
                    "fixed_threshold_hot_spell_3d",
                    "hot_day",
                    daily_max[:, i, start_day : start_day + 3] >= 303.15,
                ),
                (
                    "fixed_threshold_ice_spell_3d",
                    "ice_day",
                    daily_max[:, i, start_day : start_day + 3] < 273.15,
                ),
            ):
                count = int(flags.all(axis=1).sum())
                assert count == sum(
                    all(bool(value) for value in flags[member]) for member in range(51)
                )
                probability = count / 51
                outcome = (
                    int(all(r["daily_predicates"][daily_name] for r in refs))
                    if all(r is not None for r in refs)
                    else None
                )
                row = {
                    "initialization_index": i,
                    "initialization": iso(initialization),
                    "cutoff": iso(initialization + 4 * 3600),
                    "start_day_index": start_day,
                    "target_dates": dates,
                    "event": name,
                    "member_positive_count": count,
                    "probability": probability,
                    "outcome": outcome,
                }
                duration_rows.append(row)
                metrics[(name, start_day)].append((probability, outcome, dates[0]))
                if outcome == 1:
                    positive_keys[name].add(dates[0])
    scores = []
    for (event, day), rows in sorted(metrics.items()):
        settled = [(p, y) for p, y, _ in rows if y is not None]
        loss = sum((p - y) ** 2 for p, y in settled)
        lower, upper = loss, loss
        for p, y, _ in rows:
            if y is None:
                lower += min(p * p, (p - 1) ** 2)
                upper += max(p * p, (p - 1) ** 2)
        scores.append(
            {
                "event": event,
                "start_day_index": day,
                "registered": len(rows),
                "settled": len(settled),
                "missing": len(rows) - len(settled),
                "positive_forecast_rows": sum(y == 1 for _, y in settled),
                "raw_ensemble_brier": loss / len(settled) if settled else None,
                "full_denominator_loss_bounds": [lower / len(rows), upper / len(rows)],
            }
        )
    save("DAILY_FORECASTS.json", daily_rows)
    save("DURATION_FORECASTS.json", duration_rows)
    save("SCORES.json", scores)
    save(
        "SOURCE_BINDINGS.json",
        {
            "chunks": bindings,
            "metadata_sha256": sha(ROOT / "ensemble_forecasts.zmetadata"),
            "docs_sha256": sha(docs),
            "ecmwf_table_sha256": sha(table),
            "reference_sha256": sha(REF / "DAILY_REFERENCES.json"),
            "reference_validation_sha256": sha(REF / "VALIDATION.json"),
        },
    )
    save(
        "VALIDATION.json",
        {
            "at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "passed": True,
            "native_six_hour_values": int(maximum.size + minimum.size),
            "native_init_coordinates": 730,
            "native_valid_time_coordinates": int(valid.size),
            "all_native_inits_at_00UTC": True,
            "native_init_plus_step_equals_valid_time": True,
            "native_units_contract": "ECMWF121/122Kelvin plus official EUPPprocessed-last6hdefinition",
            "daily_member_extrema_independent_scalar_checks": 51 * 730 * 5 * 2,
            "future_daily_forecast_rows": len(daily_rows),
            "daily_reference_status": dict(
                Counter(row["reference_status"] for row in daily_rows)
            ),
            "future_duration_event_rows": len(duration_rows),
            "duration_rows_with_reference": sum(
                row["outcome"] is not None for row in duration_rows
            ),
            "unique_positive_target_dates_by_event": {
                key: len(value) for key, value in positive_keys.items()
            },
            "day0_excluded_partial_window_rows": 730,
            "new_model_calls": 0,
            "new_source_requests_in_analysis": 0,
            "independent_confirmation": False,
            "session_runtime_replays": 0,
            "operational_availability_proved": False,
            "documentation_conflict": "Official prose says noon runs;all730native time/valid_time coordinates say00UTC. One original gridded native GRIB sample also hasdataTime0. Use native coordinates,retain this discrepancy;no12hshift or hidden repair.",
            "qualification": "offline_native_product_coordinate_forecast_diagnostic_with_declared_availability",
            "limitations": [
                "Nearest model gridpoint forecasts versus station daily references;representativeness and instrument error remain.",
                "Raw member frequencies are not calibrated probabilities;no parameters were fitted.",
                "Six-hour extrema aggregation uses native product temporal semantics,not four instantaneous samples.",
                "Same-member three-day events preserve within-forecast dependence;overlapping dates/inits are not independent processes.",
                "Daily reference status mature_product refers to acquired archival versions,not historical first publication.",
                "Scalar bounds for missing outcomes are conservative and need not be jointly sharp across shared targets.",
                "This establishes a forecast/data diagnostic,not LLM/adaptive-acquisition/operational heatwave gain or final universal heatwave definition.",
            ],
        },
    )
    print(
        json.dumps(
            {
                "passed": True,
                "future_daily_rows": len(daily_rows),
                "duration_event_rows": len(duration_rows),
                "new_model_calls": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
