"""Answer-free public projection and task-equivalent raster table rendering."""

import io
import json
import textwrap

from PIL import Image, ImageDraw, ImageFont

from evidence_core import legal_cards
from common import ROOT

FONT_PATH = str(ROOT / "data/font/DejaVuSansMono.ttf")
SYSTEM = (
    "Answer the fixed weather-product question using only the supplied evidence and catalog. "
    "Do not replace its entity, units, valid dates, versions, threshold or denominator. "
    "Unobserved or invalid values are unknown, never zero or negative. "
    "A decision of yes or no requires supporting acquired evidence. "
    "Use unknown when the acquired evidence cannot determine yes or no. "
    "Cite acquired card IDs sufficient to establish the decision. "
    "Your objective is to establish the complete-pool answer within the read budget. "
    "If further reading could resolve uncertainty and budget remains, acquire evidence before stopping. "
    "An unknown answer can be locally appropriate yet incomplete: certifying that the whole pool "
    "is insufficient may require inspecting available values or quality. "
    "All cards are archived products in a controlled evidence pool; this is not real-time forecasting. "
    "Return exactly the requested JSON object, with no prose or Markdown."
)


def catalog_card(card):
    return {"id": card["id"], "cost": card["cost"], "issued_at": card["issued_at"],
            "title": card["title"], "record_index": [
                {k: row[k] for k in ["entity", "variable", "unit", "support", "version"]}
                for row in card["records"]]}


def body_card(card):
    return {"id": card["id"], "issued_at": card["issued_at"], "records": card["records"]}


def table_lines(card):
    rows = card["records"]
    lines = ["CARD " + card["id"]]
    common = {}
    for field in ["entity", "variable", "unit", "version"]:
        values = {row[field] for row in rows}
        if len(values) == 1:
            common[field] = next(iter(values))
            lines.extend(textwrap.wrap(field + ": " + common[field], width=86, break_long_words=True))
    lines.append("support | value | quality")
    for row in rows:
        value = row["value"]
        if isinstance(value, dict):
            value = "positive=" + str(value["positive"]) + ", negative=" + str(value["negative"])
        elif value is None:
            value = "unknown"
        line = f'{row["support"]} | {value} | {row["quality"]}'
        for field in ["entity", "variable", "unit", "version"]:
            if field not in common:
                line += " | " + field + "=" + row[field]
        lines.extend(textwrap.wrap(line, width=86, break_long_words=True))
    return lines


def render_card(card):
    font = ImageFont.truetype(FONT_PATH, 18)
    lines = table_lines(card)
    width, height = 1072, 28 + 26 * len(lines)
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    boxes = []
    for index, line in enumerate(lines):
        at = (16, 12 + index * 26)
        box = draw.textbbox(at, line, font=font)
        if box[0] < 0 or box[1] < 0 or box[2] > width - 10 or box[3] > height - 5:
            raise ValueError("raster table text clipped")
        draw.text(at, line, fill="black", font=font)
        boxes.append(list(box))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue(), {"size": [width, height], "lines": lines, "text_boxes": boxes,
                               "font": FONT_PATH, "font_size": 18}


def request(episode, read_ids, representation, mode, budget, final_only=False):
    if representation not in {"text", "image"} or mode not in {"full", "active", "none"}:
        raise ValueError("invalid public input profile")
    cards = legal_cards(episode)
    by_id = {x["id"]: x for x in cards}
    if not set(read_ids).issubset(by_id):
        raise ValueError("unavailable public evidence")
    spent = sum(by_id[x]["cost"] for x in set(read_ids))
    public = {"question": episode["question"], "target": episode["target"],
              "catalog": [catalog_card(x) for x in cards],
              "catalog_semantics": "Complete eligible pool for this exercise. The record index gives scope, never values or quality.",
              "read_ids": sorted(set(read_ids)), "remaining_budget": budget - spent,
              "rules": [
                  "For count_threshold, a yes needs enough observed valid exceedances; a no needs enough observed valid non-exceedances.",
                  "For area_threshold, lower = observed positive / total; upper = 1 - observed negative / total. yes if lower >= threshold; no if upper < threshold; otherwise unknown.",
                  "For revision_delta, compare the exact two requested versions at the exact valid time; both values must be valid.",
                  "Citation IDs must refer to cards already read. Catalog metadata can itself show a structurally absent required source."]}
    can_read = mode == "active" and not final_only and spent < budget
    public["output_contract"] = (
        {"read": "one unread catalog card ID"} if can_read else None)
    public["final_contract"] = {"decision": "yes|no|unknown", "citations": ["read card IDs"]}
    public["instruction"] = ("Choose exactly one action: return a read object, OR finalize using final_contract."
                             if can_read else "Finalize now using final_contract. No further reads are allowed.")
    assets = []
    if representation == "text":
        public["evidence"] = [body_card(by_id[x]) for x in sorted(set(read_ids))]
    else:
        public["evidence"] = []
        for index, ident in enumerate(sorted(set(read_ids))):
            body, manifest = render_card(by_id[ident])
            assets.append({"id": ident, "png": body, "manifest": manifest})
            public["evidence"].append({"id": ident, "image_attachment_index": index})
    # The model receives only this whitelist projection and actual image pixels.
    return public, assets
