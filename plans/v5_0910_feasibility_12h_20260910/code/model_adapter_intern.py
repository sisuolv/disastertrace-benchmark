"""Native transformers InternVL adapter; preserve readable dynamic image patches."""

import hashlib
import io
import json

from model_adapter import load_frontend as load_qwen_frontend, prepare as prepare_qwen
from model_adapter import parse_action, save, sha_file, text_file


def load_frontend(spec, settings):
    if spec["kind"] != "internvl":
        return load_qwen_frontend(spec, settings)
    from transformers import AutoProcessor

    frontend = AutoProcessor.from_pretrained(spec["directory"], local_files_only=True, trust_remote_code=False)
    frontend.image_processor.crop_to_patches = True
    frontend.image_processor.min_patches = 1
    frontend.image_processor.max_patches = settings["internvl_max_patches"]
    return frontend


def prepare(frontend, kind, state, batch, settings, slot=None):
    if kind != "internvl":
        return prepare_qwen(frontend, kind, state, batch, settings, slot)
    import torch
    from PIL import Image

    images, assets = [], []
    for asset in state["assets"]:
        path = batch / asset["path"]
        if sha_file(path) != asset["sha256"]:
            raise ValueError("frozen visual asset changed")
        image = Image.open(io.BytesIO(path.read_bytes())).convert("RGB")
        images.append(image)
        assets.append({**asset, "size": list(image.size)})
    public_text = json.dumps(state["public"], ensure_ascii=False, sort_keys=True)
    messages = [{"role": "system", "content": [{"type": "text", "text": state["system"]}]},
                {"role": "user", "content": [{"type": "text", "text": public_text}] +
                 [{"type": "image"} for _ in images]}]
    prompt = frontend.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = frontend(text=[prompt], images=images or None, return_tensors="pt", padding=False)
    ids = inputs["input_ids"][0]
    image_starts = int((ids == frontend.start_image_token_id).sum())
    if image_starts != len(images):
        raise ValueError("InternVL image placeholder mismatch")
    visual_tokens = int((ids == frontend.image_token_id).sum())
    patches = int(inputs["pixel_values"].shape[0]) if "pixel_values" in inputs else 0
    if (images and patches < len(images)) or visual_tokens != patches * frontend.image_seq_length:
        raise ValueError("InternVL actual patch tensor/token mismatch")
    tokens = int(ids.shape[-1])
    if tokens + settings["max_new_tokens"] > settings["context_limit"]:
        raise ValueError("InternVL context reservation exceeded; no truncation")
    tensors = {}
    for name, tensor in inputs.items():
        if isinstance(tensor, torch.Tensor):
            raw = tensor.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes()
            tensors[name] = {"shape": list(tensor.shape), "dtype": str(tensor.dtype),
                             "sha256": hashlib.sha256(raw).hexdigest()}
    record = {"input_tokens": tokens, "visual_tokens": visual_tokens, "image_grid_thw": [],
        "internvl_image_count": image_starts, "internvl_patch_count": patches,
        "internvl_crop_to_patches": True, "assets": assets, "tensors": tensors,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()}
    if slot is not None:
        text_file(slot / "prompt.txt", prompt)
        save(slot / "messages.json", messages)
        save(slot / "processor.json", record)
        save(slot / "input_ids.json", inputs["input_ids"].tolist())
    return inputs, record
