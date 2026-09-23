import base64
import io
import json
from copy import deepcopy

import pytest
from PIL import Image

from disastertrace.multimodal_live_v1.adapter import decode_public
from disastertrace.multimodal_live_v1.runner import collect
from disastertrace.multimodal_v1.storage import canonical, digest, publish_bytes, read, write


def template(checkpoint="c0"):
    image = Image.new("RGB", (64, 64), (42, 151, 162))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return {
        "access_track": "full_evidence",
        "checkpoint": checkpoint,
        "queries": [{"site_id": "A"}],
        "target": {},
        "rule": {},
        "output_contract": {},
        "deliveries": [{"artifact_id": "map-01"}],
        "evidence": [
            {
                "meta": {"artifact_id": "map-01", "modality": "image"},
                "content": {
                    "image_png_base64": base64.b64encode(buffer.getvalue()).decode(),
                    "layout": {"size": [64, 64]},
                },
            }
        ],
    }


def test_pixels_reach_image_part_and_payload_does_not_reach_text():
    request = template()
    before = deepcopy(request)
    result = decode_public(request)
    assert request == before
    assert "image_png_base64" not in result.public_text
    assert request["evidence"][0]["content"]["image_png_base64"] not in result.public_text
    part = result.messages[1]["content"][-1]
    assert part["type"] == "image"
    assert part["image"].getpixel((20, 20)) == (42, 151, 162)
    assert result.assets[0]["artifact_id"] == "map-01"


@pytest.mark.parametrize("defect", ["dimensions", "base64", "private", "duplicate", "track"])
def test_rejects_invalid_or_undeclared_input(defect):
    request = template()
    if defect == "dimensions":
        request["evidence"][0]["content"]["layout"]["size"] = [12, 12]
    elif defect == "base64":
        request["evidence"][0]["content"]["image_png_base64"] = "not an image!"
    elif defect == "private":
        request["gold"] = "leaked"
    elif defect == "duplicate":
        request["evidence"] *= 2
    elif defect == "track":
        request["access_track"] = "streaming"
    with pytest.raises(ValueError):
        decode_public(request)


def test_no_image_condition_has_no_visual_part():
    request = template()
    request["evidence"] = []
    result = decode_public(request)
    assert result.images == []
    assert all(p["type"] == "text" for p in result.messages[1]["content"])


class Backend:
    def __init__(self, values):
        self.values = iter(values)
        self.seen = []

    def prepare(self, request, slot):
        self.seen.append(request)
        write(slot / "processor.json", {"test_fixture": True})
        return request

    def generate(self, inputs):
        result = next(self.values)
        if isinstance(result, Exception):
            raise result
        return result, {"test_fixture": True, "output_ids": []}


def test_invalid_self_history_stays_raw_and_trajectory_reset_is_independent(tmp_path):
    plan = {
        "trajectories": [
            {"id": "base", "requests": [template(), template("c1")]},
            {"id": "other", "requests": [template()]},
        ]
    }
    backend = Backend(["```json\n{}\n```", '{"state":{}}', '{"state":{}}'])
    report = collect(tmp_path, plan, backend)
    assert backend.seen[1]["carrier"] == {
        "raw": "```json\n{}\n```",
        "invalid": True,
        "missing": False,
    }
    assert backend.seen[2]["carrier"] is None
    assert report["counts"] == {"received_invalid": 1, "received_valid": 2}
    assert not report["eligible_for_llm_leaderboard"]
    with pytest.raises(FileExistsError):
        collect(tmp_path, plan, backend)
    assert len(backend.seen) == 3


def test_unknown_stops_descendants_without_retry_and_other_trajectory_runs(tmp_path):
    plan = {
        "trajectories": [
            {"id": "base", "requests": [template(), template("c1")]},
            {"id": "other", "requests": [template()]},
        ]
    }
    backend = Backend([RuntimeError("lost"), '{"state":{}}'])
    report = collect(tmp_path, plan, backend)
    assert report["counts"] == {"unknown": 1, "unattempted": 1, "received_valid": 1}
    assert not (tmp_path / "base/0001/intent.json").exists()
    assert len(backend.seen) == 2


def test_preflight_failure_never_creates_dispatch_intent(tmp_path):
    class Broken(Backend):
        def prepare(self, request, slot):
            raise ValueError("context cap")

    report = collect(
        tmp_path, {"trajectories": [{"id": "x", "requests": [template()]}]}, Broken([])
    )
    assert report["counts"] == {"failed_preflight": 1}
    assert not (tmp_path / "x/0000/intent.json").exists()


def test_raw_is_preserved_before_parser_and_duplicate_keys_are_invalid(tmp_path):
    raw = '{"state":{},"state":{}}'
    report = collect(
        tmp_path, {"trajectories": [{"id": "x", "requests": [template()]}]}, Backend([raw])
    )
    assert report["counts"] == {"received_invalid": 1}
    assert (tmp_path / "x/0000/raw.txt").read_text() == raw
    assert read(tmp_path / "x/0000/intent.json")["origin"] == "local_vlm_development"


@pytest.mark.parametrize("tamper", [None, "prompt", "carrier", "outcome", "plan"])
def test_independent_reconstruction_detects_capture_tampering(tmp_path, tamper):
    from disastertrace.multimodal_live_v1.audit import reconstruct

    class Auditable(Backend):
        def prepare(self, request, slot):
            publish_bytes(slot / "prompt.txt", b"fixture prompt")
            write(
                slot / "processor.json",
                {
                    "request_sha256": digest(canonical(request).encode()),
                    "prompt_sha256": digest(b"fixture prompt"),
                    "assets": [],
                    "input_tokens": 4,
                    "visual_tokens": 0,
                },
            )
            return request

        def generate(self, inputs):
            return '{"state":{}}', {
                "output_tokens": 1,
                "output_ids": [42],
                "finish_reason": "eos",
                "seconds": 0.1,
            }

    plan = {
        "trajectories": [
            {
                "id": "base",
                "branch": "base",
                "requests": [template("c" + str(i)) for i in range(12)],
            }
        ]
    }
    write(tmp_path / "REQUEST_PLAN.json", plan)
    write(
        tmp_path / "EXECUTION.json",
        {
            "plan_sha256": digest((tmp_path / "REQUEST_PLAN.json").read_bytes()),
            "settings": {"max_new_tokens": 2048},
        },
    )
    collect(tmp_path / "gpu_run/live", plan, Auditable([]))
    if tamper == "prompt":
        (tmp_path / "gpu_run/live/base/0000/prompt.txt").write_text("altered")
    elif tamper == "carrier":
        path = tmp_path / "gpu_run/live/base/0001/request.json"
        request = read(path)
        request["carrier"]["raw"] = "repaired"
        path.write_text(json.dumps(request))
    elif tamper == "outcome":
        path = tmp_path / "gpu_run/live/base/0000/outcome.json"
        outcome = read(path)
        outcome["value"]["state"]["future"] = {}
        path.write_text(json.dumps(outcome))
    elif tamper == "plan":
        (tmp_path / "REQUEST_PLAN.json").write_text("{}")
    refs = {"base": [{"state": {}}] * 12}
    if tamper:
        with pytest.raises(ValueError):
            reconstruct(tmp_path, refs)
    else:
        result = reconstruct(tmp_path, refs)
        assert result["counts"] == {"received_valid": 12}
        assert result["generation_intents"] == 12
        assert result["strict_correct"] == 12
