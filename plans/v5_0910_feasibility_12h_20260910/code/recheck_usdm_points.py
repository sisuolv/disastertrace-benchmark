"""Check fixed point labels despite invalid components in some source polygons."""

from collections import defaultdict
import io
import json
import sys
import zipfile

sys.path[:0] = [
    "/mnt/afs/260010168/.venvs/disastertrace-source-probe-libs-20260910",
    "/mnt/afs/260010168/.venvs/disastertrace-feasibility-libs-20260910",
]

import numpy as np
import shapefile
from shapely.geometry import Point, shape
from shapely.validation import explain_validity, make_valid

from common import ROOT, capture, dump


def ring_parity(raw_shape, point):
    x, y = point
    count = 0
    parts = list(raw_shape.parts) + [len(raw_shape.points)]
    for start, end in zip(parts, parts[1:]):
        vertices = np.asarray(raw_shape.points[start:end], dtype=float)
        a, b = vertices, np.roll(vertices, -1, axis=0)
        crossing = (a[:, 1] > y) != (b[:, 1] > y)
        a, b = a[crossing], b[crossing]
        at_x = a[:, 0] + (y - a[:, 1]) * (b[:, 0] - a[:, 0]) / (b[:, 1] - a[:, 1])
        count += int(np.sum(at_x > x))
    return bool(count % 2)


def main():
    points = json.loads((ROOT / "data/USDM_POINTS.json").read_text())
    dates = defaultdict(list)
    for point in points:
        dates[point["map_date"]].append(point)
    rows, sources, invalid = [], [], []
    for date, group in sorted(dates.items()):
        key = "usdm-shapefile-20240910" if date == "20240910" else "usdm-" + date
        body, source = capture(key, old=date == "20240910")
        sources.append(source)
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            def part(suffix):
                names = [name for name in archive.namelist() if name.endswith(suffix)]
                if len(names) != 1:
                    raise ValueError("ambiguous shapefile member")
                return io.BytesIO(archive.read(names[0]))
            reader = shapefile.Reader(shp=part(".shp"), shx=part(".shx"), dbf=part(".dbf"))
            features = []
            for record in reader.shapeRecords():
                dm = int(record.record.as_dict()["DM"])
                geometry = shape(record.shape.__geo_interface__)
                repaired = make_valid(geometry)
                if not repaired.is_valid:
                    raise ValueError("geometry cannot be made valid")
                if not geometry.is_valid:
                    invalid.append({"date": date, "dm": dm, "reason": explain_validity(geometry)})
                features.append((dm, record.shape, geometry, repaired))
            for point in group:
                xy = (point["longitude"], point["latitude"])
                location = Point(xy)
                raw_levels = [dm for dm, raw, _, _ in features if ring_parity(raw, xy)]
                geos_levels = [dm for dm, _, geometry, _ in features if geometry.covers(location)]
                fixed_levels = [dm for dm, _, _, repaired in features if repaired.covers(location)]
                margin = min(geometry.boundary.distance(location) for _, _, geometry, _ in features)
                decisions = [max(levels, default=-1) for levels in [raw_levels, geos_levels, fixed_levels]]
                rows.append({"date": date, "location": point["location"], "expected_dm": point["dm"],
                    "ring_parity_dm": decisions[0], "raw_geos_dm": decisions[1], "make_valid_dm": decisions[2],
                    "minimum_boundary_distance_degrees": margin,
                    "agrees": all(dm == point["dm"] for dm in decisions),
                    "away_from_boundary": margin > 1e-6})
    passed = all(row["agrees"] and row["away_from_boundary"] for row in rows)
    report = {"status": "passed" if passed else "failed", "point_weeks": len(rows), "rows": rows,
        "invalid_source_features": invalid, "sources": sources,
        "minimum_boundary_distance_degrees": min(row["minimum_boundary_distance_degrees"] for row in rows),
        "independence": "Raw shapefile ring crossing implemented without GEOS; compare original and GEOS make_valid point predicates.",
        "limits": ["Only verifies these fixed points, not all repaired geometry or an area statistic.",
                   "Distances are coordinate-space diagnostics in degrees, not geodesic physical distances.",
                   "No source geometry or frozen pilot label is replaced."]}
    dump(ROOT / "analysis/USDM_POINT_REFERENCE_RECHECK.json", report)
    if not passed:
        raise ValueError("USDM point reference discrepancy; retain and invalidate affected claims")
    print(json.dumps({k: report[k] for k in ["status", "point_weeks", "invalid_source_features", "minimum_boundary_distance_degrees"]}))


if __name__ == "__main__":
    main()
