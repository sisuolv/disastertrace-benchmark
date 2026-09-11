"""Lossless palette rendering of source VIL pixels, without derived answer counts."""

import io
import json
import re

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from common import ROOT
from model_adapter import sha_file
from public_inputs import FONT_PATH


def render(card, episode, manifest):
    frame = int(episode["construction_key"].split(":frame-")[1])
    quadrant = int(card["records"][0]["support"].rsplit("quadrant-", 1)[1])
    matches = [r for r in manifest if r["event_id"] == episode["target"]["entity"] and r["channel"] == "vil"
               and r["array_path"].endswith(card["source"] + ".npy")]
    if len(matches) != 1:
        raise ValueError("native source identity ambiguous")
    source = matches[0]
    path = ROOT / source["array_path"]
    if sha_file(path) != source["file_sha256"]:
        raise ValueError("source NPY file changed")
    cube = np.load(path, allow_pickle=False)
    y, x = divmod(quadrant, 2)
    data = cube[y * 192:(y + 1) * 192, x * 192:(x + 1) * 192, frame]
    counts = {"positive": int(np.sum((data >= 160) & (data != 255))), "negative": int(np.sum(data < 160))}
    if counts != card["records"][0]["value"]:
        raise ValueError("source pixels disagree with frozen product counts")
    palette = np.asarray(json.loads((ROOT / "data/VIL_RENDER_PALETTE.json").read_text())["palette"], dtype=np.uint8)
    if len({tuple(rgb) for rgb in palette}) != 256:
        raise ValueError("palette is not injective")
    pixels = Image.fromarray(palette[data], "RGB").resize((384, 384), Image.Resampling.NEAREST)
    image = Image.new("RGB", (660, 554), "white")
    image.paste(pixels, (16, 136))
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(FONT_PATH, 16)
    headings = ["CARD " + card["id"], "SEVIR " + episode["target"]["entity"] + " / VIL product",
                f"frame={frame}, quadrant={quadrant}; original192x192",
                "2x nearest-neighbor; encoded VIL values0..254",
                "255(gray) is missing. This is not rainfall."]
    for index, line in enumerate(headings):
        draw.text((16, 10 + index * 23), line, font=font, fill="black")
    gradient = np.repeat(np.linspace(254, 0, 384).round().astype(int)[:, None], 30, axis=1)
    image.paste(Image.fromarray(palette[gradient], "RGB"), (430, 136))
    for tick in [0, 64, 128, 160, 192, 254]:
        row = 136 + round((254 - tick) / 254 * 383)
        draw.line((460, row, 470, row), fill="black", width=1)
        draw.text((476, row - 8), str(tick), font=font, fill="black")
    draw.text((16, 530), "Only the left square is source data; right=legend.", font=font, fill="black")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    png = buffer.getvalue()
    restored = np.asarray(Image.open(io.BytesIO(png)))[136:520:2, 16:400:2]
    inverse = {tuple(rgb): index for index, rgb in enumerate(palette)}
    decoded = np.array([inverse[tuple(rgb)] for rgb in restored.reshape(-1, 3)], dtype=np.uint8).reshape(192, 192)
    if not np.array_equal(decoded, data):
        raise ValueError("rendered source values fail exact PNG roundtrip")
    return png, {"source_array_path": source["array_path"], "source_sha256": source["file_sha256"],
        "frame": frame, "quadrant": quadrant, "palette": palette.tolist(),
        "data_box_xywh": [16, 136, 384, 384], "source_shape": [192, 192],
        "png_roundtrip_exact": True, "derived_counts_in_image": False,
        "limit": "Source-product visualization, not original photography/SAR and not an equal-information table rendering; VLM estimates area from pixels."}
