"""Explicit backend identity, resource binding and one-use submission regressions."""

from copy import deepcopy
from types import SimpleNamespace

import pytest

from disastertrace.qwen_role_live import launch, profiles
from disastertrace.qwen_role_live.backend import VLLMBackend, validate_observation


class Engine:
    def __init__(self, fail=False):
        self.items, self.steps, self.fail = [], 0, fail

    def has_unfinished_requests(self):
        return bool(self.items) and self.steps < 2

    def add_request(self, identity, prompt, params):
        self.items.append((identity, prompt, params))

    def step(self):
        self.steps += 1
        if self.steps == 2:
            if self.fail:
                raise RuntimeError("device lost after returned output")
            return []
        items = self.items[:1] if self.fail else self.items[::-1]
        return [
            SimpleNamespace(
                request_id=identity,
                prompt_token_ids=prompt["prompt_token_ids"],
                finished=True,
                outputs=[
                    SimpleNamespace(
                        token_ids=[1, 2], text="x", finish_reason="stop", stop_reason=None, index=0
                    )
                ],
            )
            for identity, prompt, _ in items
        ]


@pytest.mark.parametrize("fail", [False, True])
def test_engine_returns_explicit_ids_and_keeps_completed_output(monkeypatch, fail, model_adapter):
    _, adapter = model_adapter
    monkeypatch.setattr(adapter, "sampling_params", lambda p: p["sampling"])
    backend = VLLMBackend.__new__(VLLMBackend)
    engine = Engine(fail)
    backend.engine = SimpleNamespace(llm_engine=engine)
    backend.adapter = adapter
    backend.generation_authorized = True
    backend.plan = {"deadline_utc": None}
    prepared = [
        {"attempt_id": i, "prompt_token_ids": [n], "sampling": {"seed": n}}
        for n, i in enumerate(("a", "b"))
    ]
    result = backend.generate(prepared)
    assert result[0]["attempt_id"] == ("a" if fail else "b")
    assert len(result) == (1 if fail else 2)
    assert (backend.last_error is not None) == fail
    assert engine.items == [
        ("a", {"prompt_token_ids": [0]}, {"seed": 0}),
        ("b", {"prompt_token_ids": [1]}, {"seed": 1}),
    ]
    backend.generation_authorized = False
    with pytest.raises(ValueError, match="offline"):
        backend.generate(prepared)


def observation(model_adapter):
    name, adapter = model_adapter
    plan = {
        "model_profile": name,
        "settings": adapter.SETTINGS,
        "backend_files": {},
        "model_identity": "m",
        "environment_sha256": "e",
    }
    expected = {
        k: adapter.SETTINGS[k]
        for k in (
            "max_model_len",
            "tensor_parallel_size",
            "enable_prefix_caching",
            "max_num_seqs",
            "max_num_batched_tokens",
            "enforce_eager",
            "seed",
        )
    }
    expected["dtype"] = "torch.bfloat16"
    obs = {
        "visible_gpu_count": 1,
        "device_name": "NVIDIA H100 80GB HBM3",
        "total_memory_bytes": 80_000_000_000,
        "capability": [9, 0],
        "structured_decoding": profiles.decoder_for(plan),
        "actual_engine": expected,
        "settings": adapter.SETTINGS,
        "vllm_use_v1": "1",
        "v1_multiprocessing": "0",
        "request_identity": "attempt_id_direct_engine_add_request",
        **plan,
    }
    return plan, deepcopy(obs)


@pytest.mark.parametrize(
    "key,value",
    [
        ("visible_gpu_count", True),
        ("visible_gpu_count", 4),
        ("device_name", "MIG H100"),
        ("total_memory_bytes", 40000000000),
        ("capability", [8, 0]),
        ("v1_multiprocessing", "1"),
        ("model_identity", "other-model"),
        ("environment_sha256", "changed"),
    ],
)
def test_observed_runtime_mismatch_rejected(key, value, model_adapter):
    plan, obs = observation(model_adapter)
    validate_observation(obs, plan)
    obs[key] = value
    with pytest.raises(ValueError):
        validate_observation(obs, plan)


def test_uncertain_worker_does_not_repeat_and_phase_cannot_relaunch(bundle, monkeypatch, tmp_path):
    root, _, plan, _, _, _, _ = bundle
    plan.update(
        kind="model",
        generation_authorized=True,
        run_root=str(tmp_path / "live"),
        launch_registry=str(tmp_path / "claims"),
        source_files={},
    )
    from disastertrace.qwen_role_live.storage import write

    write(root / "validation.json", {})
    monkeypatch.setattr(launch, "validate_cpu", lambda *a: None)
    monkeypatch.setattr(
        launch.capacity, "ensure", lambda count: {"reserved_gpu_before": 0, "additional_gpu": count}
    )
    calls = []

    def submit(directory, request):
        directory.mkdir()
        calls.append(request["worker_id"])
        if request["worker_id"] == 1:
            raise TimeoutError("uncertain submit")
        return {"job_id": f"pt-test{request['worker_id']}"}

    monkeypatch.setattr(launch.acp, "submit", submit)
    results = launch.submit_phase(root, tmp_path / "submissions")
    assert calls == [0, 1]
    assert results[1]["status"] == "submission_failed_or_unknown"
    with pytest.raises(FileExistsError):
        launch.submit_phase(root, tmp_path / "different-path")
    assert calls == [0, 1]


def test_diagnostic_package_cannot_submit(bundle, tmp_path):
    with pytest.raises(ValueError, match="no ACP dispatch"):
        launch.submit_phase(bundle[0], tmp_path / "submissions")


def test_expired_phase_never_reaches_backend(monkeypatch):
    backend = VLLMBackend.__new__(VLLMBackend)
    backend.generation_authorized = True
    backend.plan = {"deadline_utc": "2000-01-01T00:00:00+00:00"}
    engine = Engine()
    backend.engine = SimpleNamespace(llm_engine=engine)
    assert backend.generate([{"attempt_id": "expired"}]) == []
    assert engine.items == []
    assert "deadline" in backend.last_error


def test_atomic_write_never_replaces_existing_claim(tmp_path):
    from disastertrace.qwen_role_live.storage import read, write

    path = tmp_path / "claim.json"
    write(path, {"attempt": 1})
    with pytest.raises(FileExistsError):
        write(path, {"attempt": 2})
    assert read(path) == {"attempt": 1}
    assert len(list(tmp_path.iterdir())) == 1
