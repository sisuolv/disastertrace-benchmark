"""Same-source sensor representations; no weather labels or future outcomes."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy

from PIL import Image

EXTRA_SYSTEM = """ Satellite inputs are calibrated thermal sensor context, not a fog mask or surface visibility truth. The formal E predicate still concerns the registered native neighbor reports only. Missing reports remain unknown even when an image looks clear. Numeric features and fixed-scale panels are different, lossy same-source representations. Do not add satellite IDs to the report-citation list."""


def tensor_record(tensor):
    import torch

    cpu = tensor.detach().cpu().contiguous()
    raw = cpu.view(torch.uint8).numpy().tobytes()
    return {
        "shape": list(cpu.shape),
        "dtype": str(cpu.dtype),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def prepare_inputs(processor, system, request, representation, scene, batch):
    if representation not in {"text_only", "image", "numeric", "image_numeric"}:
        raise ValueError("Unknown frozen sensor representation")
    if request["clock"] < scene["available_at"]:
        raise ValueError("Sensor product not available at the model start")
    prompt = deepcopy(request)
    prompt["sensor_representation"] = representation
    image_enabled = representation in {"image", "image_numeric"}
    numeric_enabled = representation in {"numeric", "image_numeric"}
    if image_enabled or numeric_enabled:
        prompt["satellite_context"] = scene["public_metadata"]
    if numeric_enabled:
        prompt["satellite_numeric_features"] = scene["numeric_features"]
    content = [{"type": "text", "text": json.dumps(prompt, separators=(",", ":"))}]
    images = []
    if image_enabled:
        path = batch / scene["image_file"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != scene["image_sha256"]:
            raise ValueError("Frozen image changed")
        content.append({"type": "image"})
        with Image.open(path) as image:
            images.append(image.convert("RGB"))
    messages = [
        {"role": "system", "content": system + EXTRA_SYSTEM},
        {"role": "user", "content": content},
    ]
    rendered = processor.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    inputs = processor(
        text=[rendered], images=images or None, return_tensors="pt", padding=False
    )
    grids = inputs.get("image_grid_thw")
    grid_rows = [] if grids is None else grids.tolist()
    if len(grid_rows) != len(images):
        raise ValueError("Processor image count differs from declared inputs")
    image_token = processor.tokenizer.convert_tokens_to_ids("<|image_pad|>")
    visual_tokens = int((inputs["input_ids"] == image_token).sum())
    expected = sum(
        t * h * w // processor.image_processor.merge_size**2 for t, h, w in grid_rows
    )
    if visual_tokens != expected or (image_enabled and visual_tokens == 0):
        raise ValueError("Actual image token/grid mismatch")
    if image_enabled and (
        "pixel_values" not in inputs or inputs["pixel_values"].numel() == 0
    ):
        raise ValueError("Missing native VLM pixel tensor")
    manifest = {
        "representation": representation,
        "scene_id": scene["scene_id"],
        "input_tokens": int(inputs["input_ids"].shape[-1]),
        "visual_tokens": visual_tokens,
        "image_grid_thw": grid_rows,
        "tensors": {key: tensor_record(value) for key, value in inputs.items()},
        "rendered_sha256": hashlib.sha256(rendered.encode()).hexdigest(),
        "input_ids": inputs["input_ids"][0].tolist(),
        "messages": messages,
        "base_request": request,
        "image_sha256": scene["image_sha256"] if image_enabled else None,
        "strict_information_equivalence_claimed": False,
        "hidden_labels_used": False,
    }
    return inputs, manifest
