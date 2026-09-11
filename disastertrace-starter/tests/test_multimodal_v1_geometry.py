import io
import zipfile

import pytest
import shapefile

from disastertrace.multimodal_v1.geometry_reference import load_forecasts
from disastertrace.multimodal_v1.source_audit import geometry_inside

WKT = 'GEOGCS["GCS_Sphere",DATUM["D_Sphere",SPHEROID["Sphere",6371200.0,0.0]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]'


def test_zip(
    properties=None,
    coordinates=None,
    crs=WKT,
    name="al062024_2024090921_forecastradii",
    duplicate=False,
):
    # Helper is excluded from pytest collection below.
    fields = [
        ("RADII", "N"),
        ("STORMID", "C"),
        ("ADVNUM", "C"),
        ("VALIDTIME", "C"),
        ("SYNOPTIME", "C"),
        ("TIMEZONE", "C"),
        ("TAU", "N"),
    ]
    props = dict(
        RADII=34,
        STORMID="al062024",
        ADVNUM="5",
        VALIDTIME="2024091018",
        SYNOPTIME="2024090918",
        TIMEZONE="UTC",
        TAU=24,
    )
    props.update(properties or {})
    shp, shx, dbf = io.BytesIO(), io.BytesIO(), io.BytesIO()
    writer = shapefile.Writer(shp=shp, shx=shx, dbf=dbf, shapeType=shapefile.POLYGON)
    for key, kind in fields:
        writer.field(key, kind, size=20, decimal=0)
    for _ in range(2 if duplicate else 1):
        writer.poly([coordinates or [(0, 0), (0, 1), (1, 1), (1, 0), (0, 0)]])
        writer.record(*[props[key] for key, kind in fields])
    writer.close()
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        for suffix, data in (
            ("shp", shp.getvalue()),
            ("shx", shx.getvalue()),
            ("dbf", dbf.getvalue()),
            ("prj", crs.encode()),
        ):
            z.writestr(name + "." + suffix, data)
    return out.getvalue()


test_zip.__test__ = False


def load(data):
    return load_forecasts(data, "AL062024", 5, "2024-09-09T21:00:00+00:00")


def test_native_sphere_and_absolute_time_preserved():
    rows = load(test_zip())
    assert len(rows) == 1 and rows[0]["valid_at"] == "2024-09-10T18:00:00+00:00"
    assert rows[0]["threshold_kt"] == 34 and rows[0]["properties"]["TAU"] == 24
    assert "6371200" in rows[0]["crs_wkt"]


@pytest.mark.parametrize(
    "properties",
    [
        {"VALIDTIME": "2024091118"},
        {"TIMEZONE": "PST"},
        {"ADVNUM": "7"},
        {"STORMID": "al092021"},
        {"RADII": 70},
    ],
)
def test_mismatched_source_metadata_rejected(properties):
    with pytest.raises(ValueError):
        load(test_zip(properties=properties))


def test_initial_layer_is_not_forecast_and_no_duplicate_target():
    assert load(test_zip(properties={"TAU": 0})) == []
    with pytest.raises(ValueError):
        load(test_zip(name="al062024_2024090921_initialradii"))
    with pytest.raises(ValueError):
        load(test_zip(duplicate=True))


@pytest.mark.parametrize(
    "coordinates",
    [
        [(0, 0), (1, 1), (1, 0), (0, 1), (0, 0)],
        [(-179, 0), (-179, 1), (179, 1), (179, 0), (-179, 0)],
        [(0, 99), (0, 100), (1, 100), (1, 99), (0, 99)],
    ],
)
def test_invalid_dateline_and_axis_geometry_fail_closed(coordinates):
    with pytest.raises(ValueError):
        load(test_zip(coordinates=coordinates))


def test_wrong_crs_or_filename_identity_rejected():
    with pytest.raises(ValueError):
        load(test_zip(crs=WKT.replace("6371200.0,0.0", "6378137.0,298.257223563")))
    with pytest.raises(ValueError):
        load(test_zip(name="al092021_2024090921_forecastradii"))


def test_independent_ray_crossing_holes_and_multipolygons():
    a = [[(0, 0), (3, 0), (3, 3), (0, 3), (0, 0)], [(1, 1), (2, 1), (2, 2), (1, 2), (1, 1)]]
    b = [[(5, 5), (6, 5), (6, 6), (5, 6), (5, 5)]]
    geometry = {"type": "MultiPolygon", "coordinates": [a, b]}
    assert geometry_inside((0.5, 0.5), geometry)
    assert not geometry_inside((1.5, 1.5), geometry)
    assert geometry_inside((5.5, 5.5), geometry)
    assert not geometry_inside((4, 4), geometry)
