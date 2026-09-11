"""Real-source semantic checks and fixed-target outcome joins; no model input."""

import csv
import io
import json
import re
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

import numpy as np
from bs4 import BeautifulSoup

from common import ROOT, capture, dump

sys.path[:0] = [
    "/mnt/afs/260010168/.venvs/disastertrace-source-probe-libs-20260910",
    "/mnt/afs/260010168/.venvs/disastertrace-feasibility-libs-20260910",
]

STORMS = ["AL042024", "AL062024", "AL092024", "AL142024"]


def resolve_valid(issue, day, hhmm):
    candidates = []
    for shift in range(7):
        date = issue.date() + timedelta(days=shift)
        if date.day == int(day):
            at = datetime(date.year, date.month, date.day,
                          int(hhmm[:2]), int(hhmm[2:]), tzinfo=timezone.utc)
            if at > issue:
                candidates.append(at)
    if len(candidates) != 1:
        raise ValueError("ambiguous or non-future forecast valid time")
    return candidates[0].isoformat()


def parse_nhc(body):
    pre = BeautifulSoup(body, "html.parser").find_all("pre")
    if len(pre) != 1:
        raise ValueError("missing/ambiguous advisory text")
    text = pre[0].get_text().strip()
    match = re.search(r"^(\d{4} UTC [A-Z]{3} [A-Z]{3} \d{2} \d{4})$", text, re.M)
    issue = datetime.strptime(match[1], "%H%M UTC %a %b %d %Y").replace(tzinfo=timezone.utc)
    storm = re.search(r"\b(AL\d{6})\b", text)[1]
    number = int(re.search(r"FORECAST/ADVISORY NUMBER\s+(\d+)", text)[1])
    current = int(re.search(r"MAX SUSTAINED WINDS\s+(\d+) KT", text)[1])
    rows = []
    pattern = (r"^(FORECAST|OUTLOOK) VALID (\d{2})/(\d{4})Z\s+"
               r"([\d.]+)([NS])\s+([\d.]+)([EW])[^\n]*\nMAX WIND\s+(\d+) KT")
    for found in re.finditer(pattern, text, re.M):
        kind, day, hhmm, lat, ns, lon, ew, wind = found.groups()
        rows.append({"valid_time": resolve_valid(issue, day, hhmm),
                     "wind_kt": int(wind), "latitude": float(lat) * (1 if ns == "N" else -1),
                     "longitude": float(lon) * (1 if ew == "E" else -1),
                     "row_kind": kind, "locator": f"{kind} VALID {day}/{hhmm}Z/MAX WIND"})
    # A line-state parser checks row count, values and target labels independently.
    checked = []
    lines = [line.strip() for line in text.splitlines()]
    for index, line in enumerate(lines):
        tokens = line.split()
        if len(tokens) >= 3 and tokens[:2] in (["FORECAST", "VALID"], ["OUTLOOK", "VALID"]):
            if index + 1 < len(lines) and lines[index + 1].startswith("MAX WIND "):
                wind_tokens = lines[index + 1].split()
                day, hhmm = tokens[2].rstrip("Z").split("/")
                checked.append((resolve_valid(issue, day, hhmm), int(wind_tokens[2])))
    if checked != [(x["valid_time"], x["wind_kt"]) for x in rows] or not rows:
        raise ValueError("independent forecast parser disagreement")
    if len({x["valid_time"] for x in rows}) != len(rows):
        raise ValueError("duplicated forecast target")
    return {"storm_id": storm, "advisory_number": number,
            "original_product_title": lines[3] if len(lines) > 3 else None,
            "issue_time": issue.isoformat(), "proved_historical_available_at": None,
            "current_wind_kt": current, "forecasts": rows, "raw_text": text}


def parse_hurdat(body):
    reader = iter(csv.reader(io.StringIO(body.decode())))
    selected = []
    for header in reader:
        if not header or not re.fullmatch(r"AL\d{6}", header[0].strip()):
            raise ValueError("expected storm header")
        storm, count = header[0].strip(), int(header[2])
        for _ in range(count):
            row = [x.strip() for x in next(reader)]
            if storm not in STORMS:
                continue
            at = datetime.strptime(row[0] + row[1], "%Y%m%d%H%M").replace(tzinfo=timezone.utc)
            selected.append({"storm_id": storm, "time": at.isoformat(),
                             "record_id": row[2], "status": row[3],
                             "wind_kt": int(row[6]), "latitude": row[4], "longitude": row[5]})
    return selected


def nhc():
    products, failures = [], []
    for storm in STORMS:
        for number in range(1, 17):
            key = f"nhc-{storm}-{number:03d}"
            try:
                body, source = capture(key)
                product = parse_nhc(body)
                assert product["storm_id"] == storm and product["advisory_number"] == number
                product["source"] = source
                products.append(product)
            except Exception as error:
                failures.append({"capture_id": key, "error": str(error)})
    body, provenance = capture("hurdat2-atlantic-20260227")
    outcomes = parse_hurdat(body)
    index = defaultdict(list)
    for item in outcomes:
        index[item["storm_id"], item["time"]].append(item)
    joined, unmatched = [], []
    by_target = defaultdict(list)
    for product in products:
        for row in product["forecasts"]:
            item = {"storm_id": product["storm_id"], "advisory_number": product["advisory_number"],
                    "issue_time": product["issue_time"], "target_time": row["valid_time"],
                    "forecast_wind_kt": row["wind_kt"], "persistence_wind_kt": product["current_wind_kt"],
                    "lead_hours": (datetime.fromisoformat(row["valid_time"]) -
                                   datetime.fromisoformat(product["issue_time"])).total_seconds() / 3600}
            by_target[item["storm_id"], item["target_time"]].append(item)
            candidates = index.get((item["storm_id"], item["target_time"]), [])
            if candidates and len({x["wind_kt"] for x in candidates}) == 1:
                item = {**item, "best_track_wind_kt": candidates[0]["wind_kt"],
                        "best_track_status": candidates[0]["status"]}
                joined.append(item)
            else:
                unmatched.append({**item, "reason": "no_exact_best_track_time" if not candidates else "conflict"})
    revisions = []
    for (storm, target), rows in sorted(by_target.items()):
        rows.sort(key=lambda x: x["issue_time"])
        if len(rows) >= 2:
            revisions.append({"storm_id": storm, "target_time": target,
                              "revisions": rows,
                              "distinct_values": len({x["forecast_wind_kt"] for x in rows}),
                              "value_changes": sum(a["forecast_wind_kt"] != b["forecast_wind_kt"]
                                                   for a, b in zip(rows, rows[1:])),
                              "source_refresh_only": sum(a["forecast_wind_kt"] == b["forecast_wind_kt"]
                                                          for a, b in zip(rows, rows[1:]))})
    scores = {}
    for storm in STORMS:
        rows = [x for x in joined if x["storm_id"] == storm]
        scores[storm] = {"matched_forecast_rows": len(rows),
                         "forecast_mae_kt": float(np.mean([abs(x["forecast_wind_kt"] - x["best_track_wind_kt"]) for x in rows])),
                         "persistence_mae_kt": float(np.mean([abs(x["persistence_wind_kt"] - x["best_track_wind_kt"]) for x in rows]))}
    report = {"planned_products": 64, "decoded_products": len(products), "failures": failures,
              "forecast_rows": sum(len(x["forecasts"]) for x in products),
              "exact_outcome_matches": len(joined), "unmatched_rows": len(unmatched),
              "same_target_revision_chains": len(revisions), "storm_count": len(STORMS),
              "value_changes": sum(x["value_changes"] for x in revisions),
              "source_refresh_only": sum(x["source_refresh_only"] for x in revisions),
              "product_baselines": scores,
              "limits": ["Purposeful development storms, correlated targets/leads; not a general forecast score.",
                         "HURDAT2 is retrospective best-track analysis, not independent raw observations.",
                         "Archived issue time does not establish exact historical public availability."]}
    dump(ROOT / "data/NHC_PRODUCTS.json", products)
    dump(ROOT / "data/NHC_REVISION_CHAINS.json", revisions)
    dump(ROOT / "data/NHC_OUTCOME_JOINS_PRIVATE.json", {"source": provenance, "joined": joined, "unmatched": unmatched})
    dump(ROOT / "analysis/NHC_FEASIBILITY.json", report)
    return report


def ghcnd():
    rows, sources = [], []
    for station in ["USW00094728", "USW00023183", "USW00024229", "USW00012960"]:
        body, source = capture("ghcnd-" + station)
        records = json.loads(body)
        assert len(records) == 92 and len({x["DATE"] for x in records}) == 92
        sources.append(source)
        for item in records:
            assert item["STATION"] == station
            for variable in ["TMAX", "TMIN", "PRCP"]:
                attributes = item.get(variable + "_ATTRIBUTES", "").split(",")
                rows.append({"station": station, "date": item["DATE"], "variable": variable,
                             "value": float(item[variable]) if variable in item else None,
                             "unit": "degC" if variable.startswith("T") else "mm",
                             "measurement_flag": attributes[0] if attributes else None,
                             "quality_flag": attributes[1] if len(attributes) > 1 else None,
                             "source_flag": attributes[2] if len(attributes) > 2 else None,
                             "observation_time": attributes[3] if len(attributes) > 3 else None,
                             "station_date_not_utc_interval": True})
    report = {"stations": 4, "station_days": len(rows) // 3,
              "scalar_records": len(rows), "missing_values": sum(x["value"] is None for x in rows),
              "quality_flag_counts": dict(Counter(str(x["quality_flag"]) for x in rows)),
              "extreme_qualification": "No climatological threshold verified; fixed 35C stress test is not a global heat-wave definition.",
              "limits": ["Retrospective daily summaries; no proved real-time availability.",
                         "DATE is station daily support, not an asserted 00-24 UTC interval."]}
    dump(ROOT / "data/GHCND_RECORDS.json", {"sources": sources, "records": rows})
    dump(ROOT / "analysis/GHCND_FEASIBILITY.json", report)
    return report


def usdm():
    import shapefile
    from shapely.geometry import Point, shape

    points = {"Phoenix": (-112.07, 33.45), "Portland": (-122.68, 45.52),
              "Columbus": (-82.99, 39.96), "CharlestonWV": (-81.63, 38.35),
              "Austin": (-97.74, 30.27), "LasVegas": (-115.14, 36.17),
              "Denver": (-104.99, 39.74), "NewYork": (-73.97, 40.78)}
    rows, checks = [], []
    for date in ["20240827", "20240903", "20240910", "20240917"]:
        body, source = capture("usdm-shapefile-20240910" if date == "20240910" else "usdm-" + date,
                               old=date == "20240910")
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            assert archive.testzip() is None
            def part(suffix):
                names = [x for x in archive.namelist() if x.endswith(suffix)]
                assert len(names) == 1
                return archive.read(names[0])
            reader = shapefile.Reader(shp=io.BytesIO(part(".shp")),
                                      shx=io.BytesIO(part(".shx")), dbf=io.BytesIO(part(".dbf")))
            crs = part(".prj").decode()
            assert "WGS_1984" in crs or "WGS 84" in crs
            features = [(int(x.record.as_dict()["DM"]), shape(x.shape.__geo_interface__))
                        for x in reader.shapeRecords()]
            checks.append({"date": date, "source": source, "features": len(features),
                           "levels": sorted(x[0] for x in features),
                           "all_geometries_valid": all(x[1].is_valid for x in features), "crs": crs})
            for name, coordinate in points.items():
                matched = [level for level, geometry in features if geometry.covers(Point(coordinate))]
                rows.append({"location": name, "longitude": coordinate[0], "latitude": coordinate[1],
                             "map_date": date, "dm": max(matched) if matched else -1,
                             "meaning": "-1 means outside D0-D4 polygons at these CONUS test points, not global no drought",
                             "source_capture": source["capture_id"]})
    report = {"weeks": 4, "fixed_CONUS_points": len(points), "point_weeks": len(rows),
              "checks": checks, "category_counts": dict(Counter(x["dm"] for x in rows)),
              "temporal_profile": "different weekly valid states; not revisions of one fixed week's product"}
    dump(ROOT / "data/USDM_POINTS.json", rows)
    dump(ROOT / "analysis/USDM_FEASIBILITY.json", report)
    return report


if __name__ == "__main__":
    reports = {"nhc": nhc(), "ghcnd": ghcnd(), "usdm": usdm()}
    dump(ROOT / "analysis/INITIAL_SEMANTIC_FEASIBILITY.json", reports)
    print(json.dumps({k: {x: y for x, y in v.items() if x not in {"checks", "product_baselines"}}
                      for k, v in reports.items()}, indent=2))
