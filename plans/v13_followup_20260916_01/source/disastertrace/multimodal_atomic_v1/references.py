"""Automatic references and a separately implemented public control."""

import base64
import re
from datetime import datetime

from disastertrace.multimodal_v1.pixel_baseline import pixel_relation
from disastertrace.multimodal_v1.types import select_version, tri_and


def reference(task, geometries):
    inputs, family = task["inputs"], task["family"]
    result = {}
    for query in inputs["queries"]:
        sid = query["site_id"]
        if family == "spatial":
            row = {"relation": "unknown", "map_source": None, "map_locator": None}
            if inputs["evidence"]:
                from shapely.geometry import Point, shape

                item = inputs["evidence"][0]
                aid = item["meta"]["artifact_id"]
                geom = shape(geometries[aid]["geometry"])
                point = Point(query["lon"], query["lat"])
                layout = item["content"]["layout"]
                extent, plot = layout["extent"], layout["plot"]
                tolerance = 3 * max(
                    (extent[2] - extent[0]) / (plot[2] - plot[0]),
                    (extent[3] - extent[1]) / (plot[3] - plot[1]),
                )
                if geom.boundary.distance(point) <= tolerance:
                    raise ValueError("seed anchor too close to boundary")
                row = {
                    "relation": "inside" if geom.covers(point) else "outside",
                    "map_source": aid,
                    "map_locator": query["grid"],
                }
        elif family == "watch":
            row = {"watched": None, "rule_source": None, "rule_locator": None}
            for item in inputs["evidence"]:
                if item["meta"]["target"] != inputs["target"]:
                    continue
                for i, line in enumerate(item["content"]["lines"], 1):
                    match = re.fullmatch(r"WATCH ([A-Za-z0-9_-]+) (true|false)", line)
                    if match and match[1] == sid:
                        if row["rule_source"] is not None:
                            raise ValueError("duplicate watch assertion")
                        row = {
                            "watched": match[2] == "true",
                            "rule_source": item["meta"]["artifact_id"],
                            "rule_locator": "L" + str(i),
                        }
        elif family == "logic":
            facts = inputs["explicit_facts"][sid]
            # An exhaustive table is independent of the control's tri_and implementation.
            table = {
                "inside": (True, False, None),
                "outside": (False, False, False),
                "boundary_ambiguous": (None, False, None),
                "unknown": (None, False, None),
            }
            index = next(i for i, v in enumerate((True, False, None)) if v is facts["watched"])
            row = {"inspection_required": table[facts["relation"]][index]}
        elif family == "selection":
            row = {}
            delivered = {d["artifact_id"] for d in inputs["deliveries"]}
            for field, target, modality in (
                ("map_source", inputs["map_target"], "image"),
                ("rule_source", inputs["watch_target"], "text"),
            ):
                candidates = [
                    m
                    for m in inputs["metadata"]
                    if m["target"] == target
                    and m["modality"] == modality
                    and m["artifact_id"] in delivered
                ]
                candidates.sort(
                    key=lambda m: (datetime.fromisoformat(m["issued_at"]), m["version"])
                )
                row[field] = candidates[-1]["artifact_id"] if candidates else None
        else:
            raise ValueError("unknown task family")
        result[sid] = row
    return {"state": result}


def control(task):
    """Use public pixels/literal tokens and the prior typed version/logic routines."""
    inp, family = task["inputs"], task["family"]
    state = {}
    for q in inp["queries"]:
        sid = q["site_id"]
        if family == "spatial":
            row = {"relation": "unknown", "map_source": None, "map_locator": None}
            if inp["evidence"]:
                e = inp["evidence"][0]
                row = {
                    "relation": pixel_relation(
                        base64.b64decode(e["content"]["image_png_base64"], validate=True),
                        e["content"]["layout"],
                        q["pixel"],
                    ),
                    "map_source": e["meta"]["artifact_id"],
                    "map_locator": q["grid"],
                }
        elif family == "watch":
            row = {"watched": None, "rule_source": None, "rule_locator": None}
            for e in inp["evidence"]:
                if e["meta"]["target"] == inp["target"]:
                    for index, line in enumerate(e["content"]["lines"]):
                        words = line.split()
                        if (
                            len(words) == 3
                            and words[:2] == ["WATCH", sid]
                            and words[2] in {"true", "false"}
                        ):
                            row = {
                                "watched": words[2] == "true",
                                "rule_source": e["meta"]["artifact_id"],
                                "rule_locator": f"L{index + 1}",
                            }
        elif family == "logic":
            facts = inp["explicit_facts"][sid]
            spatial = {
                "inside": True,
                "outside": False,
                "unknown": None,
                "boundary_ambiguous": None,
            }
            row = {"inspection_required": tri_and(facts["watched"], spatial[facts["relation"]])}
        elif family == "selection":
            row = {}
            for field, key, modality in (
                ("map_source", "map_target", "image"),
                ("rule_source", "watch_target", "text"),
            ):
                selected = select_version(
                    inp["metadata"],
                    {d["artifact_id"] for d in inp["deliveries"]},
                    inp[key],
                    modality,
                )
                row[field] = selected["artifact_id"] if selected else None
        else:
            raise ValueError("unknown family")
        state[sid] = row
    return {"state": state}
