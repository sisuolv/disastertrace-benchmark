"""Independent raw-feature selection and ray-crossing geometry audit.

No Shapely membership, task compiler, renderer or Gold resolver is imported here.
The public pixel diagnostic is a further, separate check on the displayed asset.
"""

import io
from datetime import datetime
from pathlib import Path

import shapefile

from .acquire import zip_members
from .storage import digest, read


def ring_inside(point, ring):
    x, y = point
    inside = False
    previous = ring[-1]
    for current in ring:
        ax, ay = previous[:2]
        bx, by = current[:2]
        if (ay > y) != (by > y) and x < ax + (y - ay) * (bx - ax) / (by - ay):
            inside = not inside
        previous = current
    return inside


def geometry_inside(point, geometry):
    polygons = (
        [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
    )
    if geometry["type"] not in {"Polygon", "MultiPolygon"}:
        raise ValueError("polygonal geometry required")
    return any(
        ring_inside(point, polygon[0]) and not any(ring_inside(point, hole) for hole in polygon[1:])
        for polygon in polygons
    )


def verify_sources(build):
    build = Path(build)
    episode = read(build / "private/episode.json")
    inventory = read(build / "inputs/sources.json")
    maps = [a for a in episode["artifacts"] if a["meta"]["modality"] == "image"]
    checks = []
    for artifact in maps:
        meta = artifact["meta"]
        target = meta["target"]
        source = next(
            row
            for row in inventory["records"]
            if row["role"] == "wind_radii" and row["advisory"] == meta["version"]
        )
        data = (build / "inputs" / source["path"]).read_bytes()
        if digest(data) != source["sha256"]:
            raise ValueError("source ZIP differs")
        members = zip_members(data)
        name = next(n for n in members if n.endswith("_forecastradii.shp"))
        reader = shapefile.Reader(
            shp=io.BytesIO(members[name]),
            dbf=io.BytesIO(members[name[:-4] + ".dbf"]),
            shx=io.BytesIO(members[name[:-4] + ".shx"]),
        )
        valid_token = datetime.fromisoformat(target["valid_at"]).strftime("%Y%m%d%H")
        found = [
            s
            for s in reader.iterShapeRecords()
            if s.record["RADII"] == target["threshold_kt"]
            and s.record["VALIDTIME"] == valid_token
            and s.record["TAU"] > 0
            and s.record["STORMID"].upper() == target["event_id"]
            and int(s.record["ADVNUM"]) == meta["version"]
        ]
        if len(found) != 1:
            raise ValueError("independent raw-feature selection ambiguous")
        geometry = found[0].shape.__geo_interface__
        for query in episode["queries"]:
            expected = (
                "inside" if geometry_inside((query["lon"], query["lat"]), geometry) else "outside"
            )
            if expected != episode["private_facts"][meta["artifact_id"]][query["site_id"]]:
                raise ValueError("independent raw geometry disagrees with reference")
            checks.append(
                {
                    "artifact_id": meta["artifact_id"],
                    "site_id": query["site_id"],
                    "relation": expected,
                }
            )
    return {
        "status": "passed",
        "algorithm": "independent raw DBF selection and ring ray crossing",
        "checks": checks,
        "boundary_points_admitted": False,
        "shapely_membership_used": False,
    }
