"""Validate a fixed pre-evaluation climatology without relabeling the pilot."""

from collections import Counter
from datetime import date, timedelta
import json
import math

import numpy as np

from common import ROOT, capture, dump

STATIONS = ["USW00094728", "USW00023183", "USW00024229", "USW00012960"]


def valid_value(row, field):
    flags = row.get(field + "_ATTRIBUTES", "").split(",")
    if len(flags) < 3 or flags[1] or field not in row:
        return None
    value = float(row[field])
    return value if math.isfinite(value) else None


def main():
    rows, failures = [], []
    for station in STATIONS:
        try:
            body, source = capture("ghcnd-baseline-" + station)
            baseline = json.loads(body)
            if len({r["DATE"] for r in baseline}) != len(baseline):
                raise ValueError("duplicate station dates")
            if any(r["STATION"] != station or not "1991-01-01" <= r["DATE"] <= "2020-12-31" for r in baseline):
                raise ValueError("climatology station/time scope mismatch")
            evaluation = json.loads(capture("ghcnd-" + station)[0])
            valid = {v: [r for r in baseline if valid_value(r, v) is not None] for v in ["TMAX", "TMIN", "PRCP"]}
            wet = [valid_value(r, "PRCP") for r in valid["PRCP"] if valid_value(r, "PRCP") >= 1.0]
            q95 = float(np.quantile(wet, 0.95, method="linear")) if len(wet) >= 100 else None
            days = []
            for row in evaluation:
                at = date.fromisoformat(row["DATE"])
                calendar = date(2001, at.month, at.day)
                neighbors = {(calendar + timedelta(days=i)).strftime("%m-%d") for i in [-2, -1, 0, 1, 2]}
                support = [r for r in valid["TMAX"] if r["DATE"][5:] in neighbors]
                years = {r["DATE"][:4] for r in support}
                qualified = len(support) >= 120 and len(years) >= 24
                q90 = float(np.quantile([valid_value(r, "TMAX") for r in support], 0.90, method="linear")) if qualified else None
                tmax, prcp = valid_value(row, "TMAX"), valid_value(row, "PRCP")
                days.append({"date": row["DATE"], "tmax_c": tmax, "q90_tmax_c": q90,
                    "baseline_samples": len(support), "baseline_years": len(years),
                    "hot": tmax >= q90 if tmax is not None and q90 is not None else None,
                    "prcp_mm": prcp, "q95_wetday_prcp_mm": q95,
                    "heavy_precipitation_indicator": prcp >= q95 if prcp is not None and q95 is not None else None})
            spells, current = [], []
            for row in days + [{"hot": False}]:
                consecutive = not current or ("date" in row and
                    (date.fromisoformat(row["date"]) - date.fromisoformat(current[-1]["date"])).days == 1)
                if row["hot"] is True and consecutive:
                    current.append(row)
                else:
                    if len(current) >= 3:
                        spells.append({"start": current[0]["date"], "end": current[-1]["date"], "days": len(current),
                                       "max_tmax_c": max(r["tmax_c"] for r in current)})
                    current = [row] if row["hot"] is True else []
            rows.append({"station": station, "source": source, "baseline_rows": len(baseline),
                "expected_baseline_calendar_days": 10958, "valid_baseline_values": {k: len(v) for k, v in valid.items()},
                "quality_flag_counts": {v: dict(Counter(r.get(v + "_ATTRIBUTES", "").split(",")[1]
                     if len(r.get(v + "_ATTRIBUTES", "").split(",")) >= 3 else "missing_attributes" for r in baseline))
                     for v in ["TMAX", "TMIN", "PRCP"]}, "wet_baseline_days": len(wet), "q95_wetday_prcp_mm": q95,
                "evaluation_days": len(days), "qualified_tmax_days": sum(r["q90_tmax_c"] is not None for r in days),
                "hot_days": sum(r["hot"] is True for r in days), "hot_spells_ge3_days": spells,
                "heavy_precipitation_days": sum(r["heavy_precipitation_indicator"] is True for r in days), "daily": days})
        except Exception as error:
            failures.append({"station": station, "type": type(error).__name__, "error": str(error)})
    dump(ROOT / "analysis/CLIMATOLOGY_FEASIBILITY.json", {"stations": rows, "failures": failures,
        "baseline": "1991-01-01 through2020-12-31; no2021target values used in threshold estimation",
        "heat_indicator": "TMAX>=calendar-centered5day Q90, NumPy linear quantile; >=120samples and24years; runs>=3consecutive station days",
        "rain_indicator": "PRCP>=Q95 of baseline wet days(PRCP>=1mm); NumPy linear quantile, >=100wet days",
        "definition_limit": "Predeclared research indicators, not asserted to be official WMO/ETCCDI heatwave or disaster labels.",
        "day_boundary_limit": "Station observation-day support retained; no conversion to universal UTC day.",
        "frozen_pilot_changed": False, "new_model_calls": 0})
    print(json.dumps({"stations": len(rows), "failures": failures, "results": [
        {k: r[k] for k in ["station", "baseline_rows", "qualified_tmax_days", "hot_days", "hot_spells_ge3_days", "heavy_precipitation_days"]}
        for r in rows]}, indent=2))


if __name__ == "__main__":
    main()
