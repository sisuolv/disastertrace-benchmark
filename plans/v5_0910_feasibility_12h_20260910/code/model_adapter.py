"""Local pinned transformers adapter; persist actual prompts and visual tensors."""

import hashlib
import io
import json
from pathlib import Path


def sha_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b""):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def text_file(path, value):
    with path.open("x") as stream:
        stream.write(value)


def load_frontend(model_spec, settings):
    from transformers import AutoProcessor, AutoTokenizer

    if model_spec["kind"] == "vl":
        frontend = AutoProcessor.from_pretrained(
            model_spec["directory"], local_files_only=True, trust_remote_code=False)
        frontend.image_processor.size = {"shortest_edge": settings["min_pixels"],
                                         "longest_edge": settings["max_pixels"]}
        return frontend
    return AutoTokenizer.from_pretrained(
        model_spec["directory"], local_files_only=True, trust_remote_code=False)


def prepare(frontend, kind, state, batch, settings, slot=None):
    import torch
    from PIL import Image

    public_text = json.dumps(state["public"], ensure_ascii=False, sort_keys=True)
    images, assets = [], []
    for asset in state["assets"]:
        path = batch / asset["path"]
        if sha_file(path) != asset["sha256"]:
            raise ValueError("frozen visual asset changed")
        image = Image.open(io.BytesIO(path.read_bytes())).convert("RGB")
        images.append(image)
        assets.append({**asset, "size": list(image.size)})
    if kind == "vl":
        messages = [{"role": "system", "content": [{"type": "text", "text": state["system"]}]},
                    {"role": "user", "content": [{"type": "text", "text": public_text}] +
                     [{"type": "image"} for _ in images]}]
        prompt = frontend.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = frontend(text=[prompt], images=images or None, return_tensors="pt", padding=False)
        grids = inputs.get("image_grid_thw")
        grid_rows = grids.tolist() if grids is not None else []
        if len(grid_rows) != len(images):
            raise ValueError("processor image count differs from attached images")
        if images and ("pixel_values" not in inputs or inputs["pixel_values"].numel() == 0):
            raise ValueError("missing actual visual tensors")
        image_token = frontend.tokenizer.convert_tokens_to_ids("<|image_pad|>")
        visual_tokens = int((inputs["input_ids"] == image_token).sum())
        if visual_tokens != sum(t * h * w // frontend.image_processor.merge_size**2 for t, h, w in grid_rows):
            raise ValueError("image placeholder/grid mismatch")
    else:
        if images:
            raise ValueError("text-only model cannot receive images")
        messages = [{"role": "system", "content": state["system"]},
                    {"role": "user", "content": public_text}]
        prompt = frontend.apply_chat_template(messages, tokenize=False, add_generation_prompt=True,
                                              enable_thinking=False)
        inputs = frontend(prompt, return_tensors="pt", padding=False)
        grid_rows, visual_tokens = [], 0
    n = inputs["input_ids"].shape[-1]
    if n + settings["max_new_tokens"] > settings["context_limit"]:
        raise ValueError("context reservation exceeded; no truncation allowed")
    tensors = {}
    for name, tensor in inputs.items():
        if isinstance(tensor, torch.Tensor):
            raw = tensor.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes()
            tensors[name] = {"shape": list(tensor.shape), "dtype": str(tensor.dtype),
                             "sha256": hashlib.sha256(raw).hexdigest()}
    record = {"input_tokens": n, "visual_tokens": visual_tokens, "image_grid_thw": grid_rows,
              "assets": assets, "tensors": tensors,
              "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()}
    if slot is not None:
        text_file(slot / "prompt.txt", prompt)
        save(slot / "messages.json", messages)
        save(slot / "processor.json", record)
        save(slot / "input_ids.json", inputs["input_ids"].tolist())
    return inputs, record


def parse_action(raw):
    try:
        def reject_duplicates(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("duplicate JSON key")
                result[key] = value
            return result
        value = json.loads(raw.strip(), object_pairs_hook=reject_duplicates)
    except (ValueError, TypeError):
        return None, "invalid_json"
    if not isinstance(value, dict):
        return None, "non_object"
    if set(value) == {"read"} and isinstance(value["read"], str):
        return value, "read"
    if (set(value) == {"decision", "citations"} and isinstance(value["decision"], str)
            and value["decision"] in {"yes", "no", "unknown"}
            and isinstance(value["citations"], list)
            and all(isinstance(x, str) for x in value["citations"])):
        return value, "final"
    return None, "invalid_schema"
