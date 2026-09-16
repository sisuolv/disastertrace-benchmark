"""Public deterministic display of admitted native-sphere polygons."""

import io
import math

from PIL import Image, ImageDraw, ImageFont

INSIDE = (42, 151, 162)
OUTSIDE = (243, 239, 226)


def layout_for(extent):
    return {
        "size": [1024, 1024],
        "plot": [112, 140, 944, 920],
        "extent": list(extent),
        "grid_rows": 8,
        "grid_cols": 8,
        "coordinate_order": "longitude_latitude",
        "coordinate_crs": "NHC native geographic sphere R=6371200m; not WGS84",
        "display_projection": "linear_native_longitude_latitude",
        "palette": {"inside": list(INSIDE), "outside": list(OUTSIDE)},
        "boundary_rule": "ambiguous within the declared pixel tolerance; outside plot is unknown",
    }


def pixel_for(point, layout):
    x, y = point
    x0, y0, x1, y1 = layout["extent"]
    l, t, r, b = layout["plot"]
    return [l + (x - x0) / (x1 - x0) * (r - l), b - (y - y0) / (y1 - y0) * (b - t)]


def grid_for(pixel, layout):
    x, y = pixel
    l, t, r, b = layout["plot"]
    if not l <= x < r or not t <= y < b:
        return None
    return f"r{int((y - t) / (b - t) * layout['grid_rows']) + 1}c{int((x - l) / (r - l) * layout['grid_cols']) + 1}"


def tolerance_for(layout, pixels=16):
    x0, y0, x1, y1 = layout["extent"]
    l, t, r, b = layout["plot"]
    return pixels * math.hypot((x1 - x0) / (r - l), (y1 - y0) / (b - t))


def render(geometry, layout, valid_at, threshold, material="official_data_rendered"):
    if material not in {"official_data_rendered", "controlled_generated"}:
        raise ValueError("renderer material must describe its actual origin")
    image = Image.new("RGB", tuple(layout["size"]), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=20)
    small = ImageFont.load_default(size=17)
    l, t, r, b = layout["plot"]
    draw.rectangle((l, t, r, b), fill=OUTSIDE)
    polygons = list(geometry.geoms) if geometry.geom_type == "MultiPolygon" else [geometry]
    for polygon in polygons:
        draw.polygon(
            [tuple(pixel_for(xy, layout)) for xy in polygon.exterior.coords],
            fill=INSIDE,
            outline=(20, 62, 70),
            width=2,
        )
        for hole in polygon.interiors:
            draw.polygon(
                [tuple(pixel_for(xy, layout)) for xy in hole.coords],
                fill=OUTSIDE,
                outline=(20, 62, 70),
                width=2,
            )
    x0, y0, x1, y1 = layout["extent"]
    for index in range(9):
        x, y = l + (r - l) * index / 8, t + (b - t) * index / 8
        draw.line((x, t, x, b), fill=(150, 155, 150), width=1)
        draw.line((l, y, r, y), fill=(150, 155, 150), width=1)
        if index < 8:
            draw.text((x + 20, t - 26), f"c{index + 1}", fill="black", font=small)
            draw.text((l - 34, y + 22), f"r{index + 1}", fill="black", font=small)
        if index % 2 == 0:
            draw.text(
                (x - 23, b + 8), f"{x0 + (x1 - x0) * index / 8:.2f}", fill="black", font=small
            )
            draw.text((8, y - 8), f"{y1 - (y1 - y0) * index / 8:.2f}", fill="black", font=small)
    source = (
        "NHC official-data rendering"
        if material == "official_data_rendered"
        else "SYNTHETIC TEST FIXTURE"
    )
    draw.text(
        (30, 16), f"{source} | Forecast {threshold} KT radii envelope", fill="black", font=font
    )
    draw.text((30, 46), "Absolute valid time: " + valid_at, fill="black", font=font)
    draw.rectangle((35, 82, 59, 102), fill=INSIDE)
    draw.text((68, 81), "inside envelope", fill="black", font=small)
    draw.rectangle((285, 82, 309, 102), fill=OUTSIDE, outline="black")
    draw.text((318, 81), "outside envelope", fill="black", font=small)
    draw.text((570, 81), "No guarantee of actual wind at a site", fill="black", font=small)
    draw.text(
        (120, 965),
        "Native sphere longitude / latitude; grid is a locator, not a class label.",
        fill="black",
        font=small,
    )
    draw.text(
        (120, 990),
        "Sites are defined by the current query. No future query markers are drawn.",
        fill="black",
        font=small,
    )
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()
