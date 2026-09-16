"""Private, strictly selected NHC geometry; no union across products or times."""

import io
import math
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import shapefile
from pyproj import CRS
from shapely.geometry import Point, box, shape

from .acquire import zip_members
from .storage import digest


def timestamp(value):
    return datetime.strptime(value, "%Y%m%d%H").replace(tzinfo=timezone.utc).isoformat()


def catalogue(data):
    members = zip_members(data)
    layers = []
    for name in sorted(members):
        if not name.endswith(".shp"):
            continue
        stem = name[:-4]
        reader = shapefile.Reader(
            shp=io.BytesIO(members[name]),
            dbf=io.BytesIO(members[stem + ".dbf"]),
            shx=io.BytesIO(members[stem + ".shx"]),
        )
        wkt = members[stem + ".prj"].decode("ascii")
        xml = members.get(name + ".xml")
        abstract = ET.fromstring(xml).findtext("idinfo/descript/abstract") if xml else None
        layers.append(
            {
                "name": name,
                "shape_type": reader.shapeTypeName,
                "feature_count": len(reader),
                "fields": [field[0] for field in reader.fields[1:]],
                "crs_wkt": wkt,
                "bbox": list(reader.bbox),
                "records": [r.as_dict() for r in reader.records()],
                "metadata_abstract": abstract,
                "members_sha256": {k: digest(v) for k, v in members.items() if k.startswith(stem)},
            }
        )
    return layers


def load_forecasts(data, storm_id, advisory, issued_at):
    members = zip_members(data)
    layers = [name for name in members if name.endswith("_forecastradii.shp")]
    if len(layers) != 1:
        raise ValueError("exactly one forecast-radii layer required")
    name, results = layers[0], []
    issue_token = re.fullmatch(re.escape(storm_id.lower()) + r"_(\d{10})_forecastradii.shp", name)
    if issue_token is None or timestamp(issue_token[1]) != issued_at:
        raise ValueError("GIS issue and official text issue disagree")
    stem = name[:-4]
    crs = CRS.from_wkt(members[stem + ".prj"].decode("ascii"))
    if (
        not crs.is_geographic
        or abs(crs.ellipsoid.semi_major_metre - 6371200) > 0.001
        or crs.ellipsoid.inverse_flattening != 0
    ):
        raise ValueError("unvalidated CRS; do not silently relabel as WGS84")
    reader = shapefile.Reader(
        shp=io.BytesIO(members[name]),
        dbf=io.BytesIO(members[stem + ".dbf"]),
        shx=io.BytesIO(members[stem + ".shx"]),
    )
    seen = set()
    for feature_index, feature in enumerate(reader.iterShapeRecords()):
        row = feature.record.as_dict()
        if (
            row["STORMID"].upper() != storm_id
            or int(row["ADVNUM"]) != advisory
            or row["TIMEZONE"] != "UTC"
        ):
            raise ValueError("source identity or timezone mismatch")
        if row["RADII"] not in {34, 50, 64}:
            raise ValueError("unsupported wind threshold")
        if row["TAU"] <= 0:
            continue
        valid = timestamp(row["VALIDTIME"])
        calculated = datetime.fromisoformat(timestamp(row["SYNOPTIME"])) + timedelta(
            hours=row["TAU"]
        )
        if calculated.isoformat() != valid:
            raise ValueError("explicit valid time and synoptic lead disagree")
        if datetime.fromisoformat(valid) <= datetime.fromisoformat(issued_at):
            raise ValueError("forecast valid time must follow issue")
        geometry = shape(feature.shape.__geo_interface__)
        if (
            geometry.is_empty
            or not geometry.is_valid
            or geometry.geom_type not in {"Polygon", "MultiPolygon"}
        ):
            raise ValueError("invalid polygon; no automatic buffer repair")
        minx, miny, maxx, maxy = geometry.bounds
        if not (-180 <= minx <= maxx <= 180 and -90 <= miny <= maxy <= 90) or maxx - minx > 180:
            raise ValueError("unsupported axes or dateline-crossing geometry")
        key = (row["RADII"], valid)
        if key in seen:
            raise ValueError("duplicate threshold/valid-time feature")
        seen.add(key)
        results.append(
            {
                "threshold_kt": row["RADII"],
                "valid_at": valid,
                "properties": row,
                "geometry": geometry,
                "layer": name,
                "feature_index": feature_index,
                "crs_wkt": crs.to_wkt(),
            }
        )
    return results


def relation(geometry, point, extent, tolerance):
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("invalid boundary tolerance")
    point = Point(point)
    if not box(*extent).covers(point):
        return "unknown"
    if geometry.boundary.distance(point) <= tolerance:
        return "boundary_ambiguous"
    return "inside" if geometry.covers(point) else "outside"
