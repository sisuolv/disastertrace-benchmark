"""Decode public PNG attachments and bind the actual processor inputs."""

import base64
import io
import json
from dataclasses import dataclass

from PIL import Image

from disastertrace.multimodal_v1.storage import canonical, digest, publish_bytes, write

SYSTEM = (
    "Maintain the requested disaster exercise state from the supplied public evidence. "
    "Follow output_contract exactly. Images are attached with artifact_id labels. "
    "The carrier is your own previous raw answer and can be wrong. "
    "Return only the final JSON object, without markdown or explanation."
)


@dataclass
class PublicInput:
    messages: list
    images: list
    assets: list
    public_text: str


def decode_public(request):
    public = json.loads(canonical(request))
    allowed = {
        "access_track",
        "checkpoint",
        "deliveries",
        "evidence",
        "output_contract",
        "queries",
        "rule",
        "target",
        "carrier",
    }
    if set(public) - allowed or not (allowed - {"carrier"}) <= set(public):
        raise ValueError("unexpected public request fields")
    if public["access_track"] != "full_evidence":
        raise ValueError("this adapter version only supports full evidence")
    images, assets, ids = [], [], set()
    for item in public["evidence"]:
        aid = item["meta"]["artifact_id"]
        if aid in ids:
            raise ValueError("duplicate public artifact identity")
        ids.add(aid)
        if item["meta"]["modality"] != "image":
            continue
        content = item["content"]
        encoded = content.pop("image_png_base64")
        if not isinstance(encoded, str) or len(encoded) > 12 * 1024**2:
            raise ValueError("image byte cap")
        png = base64.b64decode(encoded, validate=True)
        with Image.open(io.BytesIO(png)) as source:
            if source.format != "PNG" or list(source.size) != content["layout"]["size"]:
                raise ValueError("image bytes and declared PNG dimensions differ")
            if source.width * source.height > 4 * 1024**2:
                raise ValueError("decoded pixel cap")
            image = source.convert("RGB")
            image.load()
        index = len(images)
        images.append(image)
        assets.append(
            {
                "index": index,
                "artifact_id": aid,
                "sha256": digest(png),
                "bytes": len(png),
                "size": list(image.size),
                "png": png,
            }
        )
        content["image_attachment"] = {"index": index, "artifact_id": aid, "sha256": digest(png)}
    if len(images) > 2:
        raise ValueError("first-stage two-image cap")
    public_text = canonical(public)
    # No encoded payload or local path is used as a substitute for image exposure.
    if "image_png_base64" in public_text:
        raise ValueError("unexpected encoded payload in text")
    parts = [{"type": "text", "text": public_text}]
    for asset, image in zip(assets, images):
        parts.extend(
            [
                {
                    "type": "text",
                    "text": "Image attachment "
                    + str(asset["index"])
                    + ": artifact_id="
                    + asset["artifact_id"],
                },
                {"type": "image", "image": image},
            ]
        )
    return PublicInput(
        [
            {"role": "system", "content": [{"type": "text", "text": SYSTEM}]},
            {"role": "user", "content": parts},
        ],
        images,
        assets,
        public_text,
    )


def tensor_record(tensor):
    import torch

    cpu = tensor.detach().cpu().contiguous()
    data = cpu.view(torch.uint8).numpy().tobytes()
    return {
        "shape": list(cpu.shape),
        "dtype": str(cpu.dtype),
        "bytes": len(data),
        "sha256": digest(data),
    }


class QwenBackend:
    def __init__(self, processor, model, settings):
        self.processor, self.model, self.settings = processor, model, settings

    def prepare(self, request, slot):
        import torch

        public = decode_public(request)
        prompt = self.processor.apply_chat_template(
            public.messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self.processor(
            text=[prompt], images=public.images or None, return_tensors="pt", padding=False
        )
        n = int(inputs["input_ids"].shape[-1])
        if n + self.settings["max_new_tokens"] > self.settings["context_limit"]:
            raise ValueError("context reservation exceeds fixed limit")
        grids = inputs.get("image_grid_thw")
        grid_rows = grids.tolist() if grids is not None else []
        if len(grid_rows) != len(public.images):
            raise ValueError("processor image count mismatch")
        if public.images and ("pixel_values" not in inputs or inputs["pixel_values"].numel() == 0):
            raise ValueError("missing visual tensor")
        token_id = self.processor.tokenizer.convert_tokens_to_ids("<|image_pad|>")
        visual_tokens = int((inputs["input_ids"] == token_id).sum())
        expected = sum(
            t * h * w // self.processor.image_processor.merge_size**2 for t, h, w in grid_rows
        )
        if visual_tokens != expected:
            raise ValueError("image token/grid mismatch")
        manifest = {
            "request_sha256": digest(canonical(request).encode()),
            "prompt_sha256": digest(prompt.encode()),
            "input_tokens": n,
            "visual_tokens": visual_tokens,
            "image_grid_thw": grid_rows,
            "tensors": {
                k: tensor_record(v) for k, v in inputs.items() if isinstance(v, torch.Tensor)
            },
            "assets": [{k: v for k, v in a.items() if k != "png"} for a in public.assets],
        }
        publish_bytes(slot / "prompt.txt", prompt.encode())
        publish_bytes(slot / "public_text.json", public.public_text.encode())
        for asset in public.assets:
            publish_bytes(slot / ("image-" + str(asset["index"]) + ".png"), asset["png"])
        write(slot / "input_ids.json", inputs["input_ids"].tolist())
        write(slot / "processor.json", manifest)
        return inputs

    def generate(self, inputs):
        import time

        import torch
        from transformers import StoppingCriteria, StoppingCriteriaList

        deadline = time.monotonic() + self.settings["max_generation_seconds"]

        class Deadline(StoppingCriteria):
            def __call__(self, input_ids, scores, **kwargs):
                return time.monotonic() >= deadline

        device = next(self.model.parameters()).device
        inputs = {k: v.to(device) for k, v in inputs.items()}
        torch.cuda.synchronize()
        start = time.monotonic()
        with torch.inference_mode():
            result = self.model.generate(
                **inputs,
                max_new_tokens=self.settings["max_new_tokens"],
                do_sample=False,
                use_cache=True,
                stopping_criteria=StoppingCriteriaList([Deadline()]),
                return_dict_in_generate=True,
                output_scores=False,
            )
        torch.cuda.synchronize()
        tokens = result.sequences[0, inputs["input_ids"].shape[-1] :].tolist()
        eos = self.model.generation_config.eos_token_id
        eos_ids = eos if isinstance(eos, list) else [eos]
        finish = (
            "eos"
            if tokens and tokens[-1] in eos_ids
            else "length"
            if len(tokens) >= self.settings["max_new_tokens"]
            else "time_limit"
        )
        raw = self.processor.tokenizer.decode(
            tokens, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )
        return raw, {
            "output_ids": tokens,
            "output_tokens": len(tokens),
            "finish_reason": finish,
            "seconds": time.monotonic() - start,
            "cuda_peak_allocated_bytes": torch.cuda.max_memory_allocated(),
            "cuda_peak_reserved_bytes": torch.cuda.max_memory_reserved(),
        }
