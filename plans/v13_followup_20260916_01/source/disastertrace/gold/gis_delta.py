from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GeometryDelta:
    added_wkt: str
    removed_wkt: str
    stable_wkt: str
    port_relation_before: str
    port_relation_after: str


def build_polygon_delta(previous_path: Path, current_path: Path, port_lon: float, port_lat: float) -> GeometryDelta:
    """Build deterministic hidden Gold from vector products, not rendered PNGs."""
    try:
        import geopandas as gpd
        from shapely.geometry import Point
        from shapely.ops import unary_union
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("install disastertrace[geo]") from exc

    previous = gpd.read_file(previous_path).to_crs("EPSG:4326")
    current = gpd.read_file(current_path).to_crs("EPSG:4326")
    old_geom = unary_union([geom for geom in previous.geometry if geom is not None]).buffer(0)
    new_geom = unary_union([geom for geom in current.geometry if geom is not None]).buffer(0)
    port = Point(port_lon, port_lat)
    return GeometryDelta(
        added_wkt=new_geom.difference(old_geom).wkt,
        removed_wkt=old_geom.difference(new_geom).wkt,
        stable_wkt=old_geom.intersection(new_geom).wkt,
        port_relation_before="inside" if old_geom.covers(port) else "outside",
        port_relation_after="inside" if new_geom.covers(port) else "outside",
    )
