"""Exercise actual engine identity and partial-return handling without a GPU."""

from types import SimpleNamespace

import pytest

from disastertrace.constrained_eval import adapter
from disastertrace.repeat_live.backend import VLLMBackend


class FakeEngine:
    def __init__(self, mode):
        self.mode, self.requests, self.steps = mode, [], 0

    def add_request(self, identity, prompt, sampling):
        self.requests.append((identity, prompt, sampling))

    def has_unfinished_requests(self):
        return bool(self.requests) and self.steps < 2

    def step(self):
        self.steps += 1
        if self.steps == 2:
            if self.mode == "partial_error":
                raise RuntimeError("device failure after a completed answer")
            return []
        rows = self.requests[::-1] if self.mode == "reverse" else self.requests[:1]
        return [
            SimpleNamespace(
                request_id=identity,
                prompt_token_ids=prompt["prompt_token_ids"],
                finished=True,
                outputs=[
                    SimpleNamespace(
                        token_ids=[42, 257],
                        text="raw",
                        finish_reason="stop",
                        stop_reason=None,
                        index=0,
                    )
                ],
            )
            for identity, prompt, _ in rows
        ]


@pytest.mark.parametrize(
    "mode,count,error", [("reverse", 2, None), ("partial_error", 1, "device failure")]
)
def test_engine_preserves_identity_and_returned_answers(monkeypatch, mode, count, error):
    monkeypatch.setattr(adapter, "sampling_params", lambda item: item["sampling"])
    backend = VLLMBackend.__new__(VLLMBackend)
    backend.generation_authorized = True
    engine = FakeEngine(mode)
    backend.engine = SimpleNamespace(llm_engine=engine)
    prepared = [
        {"attempt_id": "a", "prompt_token_ids": [1], "sampling": {"seed": 10}},
        {"attempt_id": "b", "prompt_token_ids": [2], "sampling": {"seed": 20}},
    ]
    results = backend.generate(prepared)
    assert len(results) == count
    assert engine.requests == [
        ("a", {"prompt_token_ids": [1]}, {"seed": 10}),
        ("b", {"prompt_token_ids": [2]}, {"seed": 20}),
    ]
    assert results[0]["attempt_id"] == ("b" if mode == "reverse" else "a")
    assert results[0]["candidates"][0]["output_token_ids"] == [42, 257]
    assert (backend.last_error is None) if error is None else error in backend.last_error


def test_backend_independently_denies_offline_generation():
    backend = VLLMBackend.__new__(VLLMBackend)
    backend.generation_authorized = False
    with pytest.raises(ValueError, match="offline"):
        backend.generate([])


@pytest.mark.parametrize(
    "name,value",
    [
        ("visible_gpu_count", True),
        ("visible_gpu_count", 2),
        ("device_name", "MIG H100"),
        ("total_memory_bytes", 40_000_000_000),
        ("v1_multiprocessing", "1"),
        ("capability", [8, 0]),
    ],
)
def test_reject_incorrect_hardware_and_runtime(name, value):
    from disastertrace.constrained_eval import contract
    from disastertrace.repeat_live.backend import validate_observation
    from disastertrace.stress_eval.runtime import DECODING_OBSERVATION

    observed = {
        "visible_gpu_count": 1,
        "device_name": "NVIDIA H100 80GB HBM3",
        "total_memory_bytes": 80_000_000_000,
        "capability": [9, 0],
        "structured_decoding": DECODING_OBSERVATION,
        "constraint": contract.identity(),
        "settings": adapter.SETTINGS,
        "vllm_use_v1": "1",
        "v1_multiprocessing": "0",
        "request_identity": "attempt_id_direct_engine_add_request",
    }
    validate_observation(observed)
    observed[name] = value
    with pytest.raises(ValueError):
        validate_observation(observed)
