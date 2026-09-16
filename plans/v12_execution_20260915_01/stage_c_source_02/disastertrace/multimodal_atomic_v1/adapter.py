"""Atomic task messages with unchanged PNG/tensor capture and greedy generation."""

import json

from disastertrace.multimodal_live_v1.adapter import QwenBackend, decode_public, tensor_record
from disastertrace.multimodal_live_v1.preflight import check_readability
from disastertrace.multimodal_v1.storage import canonical, digest, publish_bytes, write

from .tasks import contract

SYSTEM = (
    "Complete the one independent diagnostic task from its supplied public inputs. "
    "Follow output_contract exactly. State must be an object keyed by current site_id. "
    "Images are real attachments labeled by artifact_id. Return only the final JSON."
)


def bridge(request):
    inp = request["inputs"]
    return {
        "access_track": "full_evidence",
        "checkpoint": "static",
        "deliveries": [],
        "evidence": inp["evidence"],
        "queries": inp["queries"],
        "target": {},
        "rule": {},
        "output_contract": request["output_contract"],
    }


def decode_atomic(request):
    if set(request) != {"task_id", "family", "track", "inputs", "output_contract"}:
        raise ValueError("unexpected atomic request fields")
    allowed = {
        "target",
        "queries",
        "evidence",
        "explicit_facts",
        "fact_origin",
        "map_target",
        "watch_target",
        "metadata",
        "deliveries",
        "source_checkpoint",
    }
    if set(request["inputs"]) - allowed:
        raise ValueError("non-public input field")
    if request["output_contract"] != contract(request["family"]):
        raise ValueError("atomic output contract changed")
    if (request["family"] == "logic") != (request["track"] == "privileged_logic_facts"):
        raise ValueError("privileged track mismatch")
    public = decode_public(bridge(request))
    transformed = json.loads(canonical(request))
    transformed["inputs"]["evidence"] = json.loads(public.public_text)["evidence"]
    public.public_text = canonical(transformed)
    public.messages[0]["content"][0]["text"] = SYSTEM
    public.messages[1]["content"][0]["text"] = public.public_text
    return public


def readability(request, inputs, processor, slot):
    return check_readability(bridge(request), inputs, processor, slot)


class AtomicBackend(QwenBackend):
    def __init__(self, processor, model, settings):
        self.processor, self.model, self.settings = processor, model, settings

    def prepare(self, request, slot):
        import torch

        public = decode_atomic(request)
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
