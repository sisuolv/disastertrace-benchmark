"""Public-input pixel diagnostic, independent of GIS and reference compilation.

This intentionally simple baseline applies only to the controlled renderer's
documented palette. It is not an oracle for native NHC maps or satellite images.
"""

import base64
import io
import json
import math
import re
from datetime import datetime

from PIL import Image


def pixel_relation(png, layout, pixel, size=None):
    image = Image.open(io.BytesIO(png)).convert("RGB")
    if list(image.size) != layout["size"]:
        raise ValueError("image and declared dimensions differ")
    if size is not None:
        image = image.resize((size, size), Image.Resampling.LANCZOS)
    sx, sy = image.width / layout["size"][0], image.height / layout["size"][1]
    x, y = pixel
    l, t, r, b = layout["plot"]
    if not l <= x < r or not t <= y < b:
        return "unknown"
    cx, cy = round(x * sx), round(y * sy)
    counts = {"inside": 0, "outside": 0}
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            px, py = cx + dx, cy + dy
            if not 0 <= px < image.width or not 0 <= py < image.height:
                continue
            rgb = image.getpixel((px, py))
            distances = {key: math.dist(rgb, value) for key, value in layout["palette"].items()}
            key = min(distances, key=distances.get)
            if distances[key] < 45:
                counts[key] += 1
    if counts["inside"] and counts["outside"]:
        return "boundary_ambiguous"
    if max(counts.values()) < 4:
        return "unknown"
    return max(counts, key=counts.get)


def _latest(evidence, target, modality, deliveries, policy):
    candidates = [
        item
        for item in evidence
        if item["meta"]["modality"] == modality and item["meta"]["target"] == target
    ]
    if not candidates:
        return None
    if policy == "latest_arrival":

        def key(item):
            return max(
                datetime.fromisoformat(d["delivered_at"])
                for d in deliveries
                if d["artifact_id"] == item["meta"]["artifact_id"]
            )
    else:

        def key(item):
            return (datetime.fromisoformat(item["meta"]["issued_at"]), item["meta"]["version"])

    ranked = sorted(candidates, key=key)
    if len(ranked) > 1 and key(ranked[-1]) == key(ranked[-2]):
        raise ValueError("ambiguous public evidence")
    return ranked[-1]


def answer(request, policy="public_pixel"):
    target = request["target"]
    mapping = _latest(request["evidence"], target, "image", request["deliveries"], policy)
    rule_key = dict(target, product="benchmark_watch_list", variable="watched")
    rules = _latest(request["evidence"], rule_key, "text", request["deliveries"], policy)
    watch, locators = {}, {}
    if rules is not None:
        for number, text in enumerate(rules["content"]["lines"], 1):
            match = re.fullmatch(r"WATCH ([A-Za-z0-9_-]+) (true|false)", text)
            if match:
                watch[match[1]] = match[2] == "true"
                locators[match[1]] = "L" + str(number)
    state = {}
    for site in request["queries"]:
        sid = site["site_id"]
        value = (
            "unknown"
            if mapping is None
            else pixel_relation(
                base64.b64decode(mapping["content"]["image_png_base64"], validate=True),
                mapping["content"]["layout"],
                site["pixel"],
            )
        )
        watched = watch.get(sid)
        spatial = {"inside": True, "outside": False, "unknown": None, "boundary_ambiguous": None}[
            value
        ]
        required = (
            False
            if watched is False or spatial is False
            else (True if watched is True and spatial is True else None)
        )
        state[sid] = {
            "relation": value,
            "watched": watched,
            "inspection_required": required,
            "map_source": mapping["meta"]["artifact_id"] if mapping else None,
            "map_locator": site["grid"] if mapping else None,
            "rule_source": rules["meta"]["artifact_id"] if rules and sid in watch else None,
            "rule_locator": locators.get(sid),
        }
    previous = None
    carrier = request.get("carrier")
    if carrier and not carrier["invalid"]:
        previous = json.loads(carrier["raw"])["state"]
    if policy == "never_update" and previous:
        state = {sid: previous.get(sid, row) for sid, row in state.items()}
    elif policy == "value_only" and previous:
        for sid, row in state.items():
            if sid in previous:
                for key in ("map_source", "map_locator", "rule_source", "rule_locator"):
                    row[key] = previous[sid][key]
    elif policy == "global_update" and previous:
        changed = any(
            sid in previous and previous[sid]["relation"] != row["relation"]
            for sid, row in state.items()
        )
        if changed:
            for sid, row in state.items():
                if sid in previous and previous[sid]["relation"] == row["relation"]:
                    row["relation"] = "outside" if row["relation"] == "inside" else "inside"
    elif policy == "center_text_changes_space" and request["checkpoint"] == "c1":
        for row in state.values():
            if row["relation"] in {"inside", "outside"}:
                row["relation"] = "outside" if row["relation"] == "inside" else "inside"
    elif policy == "missing_as_false":
        for row in state.values():
            if row["relation"] == "unknown":
                row["relation"] = "outside"
            for key in ("watched", "inspection_required"):
                if row[key] is None:
                    row[key] = False
    return json.dumps({"state": state}, separators=(",", ":"), sort_keys=True)
