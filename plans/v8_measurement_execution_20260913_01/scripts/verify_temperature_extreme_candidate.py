"""Independently reconstruct candidate probabilities and native daily labels."""

import csv
import datetime as dt
import hashlib
import io
import json
import math
import shutil
import statistics
import zipfile
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE / "temperature_daily_forecast_01"
ANALYSIS = ROOT / "analysis_01"
OUT = ROOT / "independent_audit_01"


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    OUT.mkdir(exist_ok=False)
    shutil.copyfile(Path(__file__), OUT / "EXECUTED_SOURCE.py")
    refroot = HERE / "temperature_daily_reference_01"
    qualification = read(refroot / "qualification_01/VALIDATION.json")
    archive = refroot / read(refroot / "SELECTED.json")["archive"]
    assert digest(archive) == qualification["archive_sha256"]
    refs = {}
    with zipfile.ZipFile(archive) as handle:
        raw = handle.read(qualification["product_member"])
    assert hashlib.sha256(raw).hexdigest() == qualification["product_member_sha256"]
    for unclean in csv.DictReader(io.StringIO(raw.decode("latin1")), delimiter=";"):
        row = {key.strip(): value.strip() for key, value in unclean.items()}
        if "20170101" <= row["MESS_DATUM"] <= "20181231":
            date = (
                dt.datetime.strptime(row["MESS_DATUM"], "%Y%m%d")
                .replace(tzinfo=dt.timezone.utc)
                .date()
                .isoformat()
            )
            assert (
                row["STATIONS_ID"] == "460"
                and row["TXK"] != "-999"
                and row["TNK"] != "-999"
            )
            refs[date] = {
                "hot_day": float(row["TXK"]) >= 30,
                "frost_day": float(row["TNK"]) < 0,
                "ice_day": float(row["TXK"]) < 0,
            }
    assert len(refs) == 730
    rows = read(ANALYSIS / "DAILY_FORECASTS.json")
    indexed = {(r["initialization_index"], r["day_index"]): r for r in rows}
    assert len(rows) == len(indexed) == 2920
    groups = defaultdict(list)
    for row in rows:
        start = dt.datetime.fromisoformat(row["target_date"] + "T00:00:00+00:00")
        initialization = dt.datetime.fromisoformat(row["initialization"])
        assert start == initialization + dt.timedelta(days=row["day_index"])
        assert dt.datetime.fromisoformat(row["cutoff"]) < start
        maximum, minimum = row["forecast_max_members_C"], row["forecast_min_members_C"]
        assert len(maximum) == len(minimum) == 51
        assert all(math.isfinite(x) for x in maximum + minimum)
        for event, predicate, values in (
            ("hot_day", lambda x: x >= 30, maximum),
            ("frost_day", lambda x: x < 0, minimum),
            ("ice_day", lambda x: x < 0, maximum),
        ):
            p = sum(predicate(x) for x in values) / 51
            assert abs(p - row["probabilities"][event]) < 1e-14
            y = (
                int(refs[row["target_date"]][event])
                if row["target_date"] in refs
                else None
            )
            if row["reference"] is None:
                assert y is None
            else:
                assert y == row["reference"]["daily_predicates"][event]
            groups[(event, row["day_index"])].append((p, y))
    durations = read(ANALYSIS / "DURATION_FORECASTS.json")
    for row in durations:
        event = (
            "hot_day" if row["event"] == "fixed_threshold_hot_spell_3d" else "ice_day"
        )
        days = [
            indexed[(row["initialization_index"], row["start_day_index"] + j)]
            for j in range(3)
        ]
        assert row["target_dates"] == [day["target_date"] for day in days]
        positive_members = 0
        for member in range(51):
            values = [day["forecast_max_members_C"][member] for day in days]
            positive_members += (
                all(x >= 30 for x in values)
                if event == "hot_day"
                else all(x < 0 for x in values)
            )
        p = positive_members / 51
        assert (
            row["member_positive_count"] == positive_members and row["probability"] == p
        )
        y = (
            int(all(refs[date][event] for date in row["target_dates"]))
            if all(date in refs for date in row["target_dates"])
            else None
        )
        assert y == row["outcome"]
        groups[(row["event"], row["start_day_index"])].append((p, y))
    scores = read(ANALYSIS / "SCORES.json")
    assert len(scores) == len(groups) == 16
    for score in scores:
        group = groups[(score["event"], score["start_day_index"])]
        observed = [(p - y) ** 2 for p, y in group if y is not None]
        assert score["registered"] == len(group) and score["settled"] == len(observed)
        assert score["missing"] == sum(y is None for _, y in group)
        assert score["positive_forecast_rows"] == sum(y == 1 for _, y in group)
        assert abs(score["raw_ensemble_brier"] - statistics.fmean(observed)) < 1e-14
        bounds = [
            statistics.fmean(
                (p - y) ** 2 if y is not None else operation(p * p, (p - 1) ** 2)
                for p, y in group
            )
            for operation in (min, max)
        ]
        assert all(
            abs(a - b) < 1e-14
            for a, b in zip(bounds, score["full_denominator_loss_bounds"])
        )
    result = {
        "at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "passed": True,
        "daily_probability_positions_checked": len(rows) * 3,
        "duration_probability_positions_checked": len(durations),
        "score_groups_checked": len(scores),
        "all_probabilities_labels_scores_and_missing_bounds_reconstructed": True,
        "native_daily_reference_archive_sha256": digest(archive),
        "analysis_files": {
            name: digest(ANALYSIS / name)
            for name in (
                "DAILY_FORECASTS.json",
                "DURATION_FORECASTS.json",
                "SCORES.json",
                "TASK_SPEC.json",
                "VALIDATION.json",
            )
        },
        "new_model_calls": 0,
        "new_source_requests": 0,
        "independent_weather_confirmation": False,
        "scope": "Independent output/probability/native-label/scoring audit;array decode and time-support qualification remain in original analysis. Not a new model experiment.",
    }
    with (OUT / "VALIDATION.json").open("x") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write("\n")
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "passed",
                    "daily_probability_positions_checked",
                    "duration_probability_positions_checked",
                    "score_groups_checked",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
