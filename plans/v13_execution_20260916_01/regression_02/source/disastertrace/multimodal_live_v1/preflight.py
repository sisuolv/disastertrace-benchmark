"""Check public image readability after the real Qwen processor transformation."""

import io

import numpy as np
from PIL import Image

from disastertrace.multimodal_v1.pixel_baseline import pixel_relation
from disastertrace.multimodal_v1.storage import digest, publish_bytes

from .adapter import decode_public


def reconstructed_images(inputs, processor):
    image_processor = processor.image_processor
    p, m, temporal = (
        image_processor.patch_size,
        image_processor.merge_size,
        image_processor.temporal_patch_size,
    )
    offset, result = 0, []
    for t, h, w in inputs.get("image_grid_thw", []).tolist() if "image_grid_thw" in inputs else []:
        count = t * h * w
        patches = inputs["pixel_values"][offset : offset + count].detach().cpu().numpy()
        offset += count
        frames = patches.reshape(t, h // m, w // m, m, m, 3, temporal, p, p)
        frames = frames.transpose(0, 6, 5, 1, 3, 7, 2, 4, 8).reshape(t * temporal, 3, h * p, w * p)
        normalized = frames[0].transpose(1, 2, 0)
        rgb = normalized * np.array(image_processor.image_std) + np.array(
            image_processor.image_mean
        )
        rgb = np.clip(np.rint(rgb / image_processor.rescale_factor), 0, 255).astype(np.uint8)
        if not np.allclose(frames, frames[0:1]):
            raise ValueError("still-image temporal patches unexpectedly differ")
        result.append(Image.fromarray(rgb))
    return result


def check_readability(request, inputs, processor, slot):
    public = decode_public(request)
    restored = reconstructed_images(inputs, processor)
    rows = []
    for asset, image in zip(public.assets, restored):
        item = next(
            x for x in request["evidence"] if x["meta"]["artifact_id"] == asset["artifact_id"]
        )
        layout = item["content"]["layout"]
        source = Image.open(io.BytesIO(asset["png"])).convert("RGB")
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        png = buffer.getvalue()
        publish_bytes(slot / ("processor-image-" + str(asset["index"]) + ".png"), png)
        if image.size != source.size:
            raise ValueError("first-stage image must retain the frozen source resolution")
        exact_rgb = image.tobytes() == source.tobytes()
        if not exact_rgb:
            raise ValueError("processor reconstruction changed source RGB values")
        for query in request["queries"]:
            before = pixel_relation(asset["png"], layout, query["pixel"])
            after = pixel_relation(png, layout, query["pixel"])
            if before != after or after in {"unknown", "boundary_ambiguous"}:
                raise ValueError("selected point is not clearly readable after processing")
            rows.append(
                {
                    "artifact_id": asset["artifact_id"],
                    "site_id": query["site_id"],
                    "size": list(image.size),
                    "source_rgb_equal": exact_rgb,
                    "before": before,
                    "after": after,
                    "reconstructed_png_sha256": digest(png),
                }
            )
    return rows
