"""The installed vLLM wrapper must reconstruct with the CPU tokenizer, without inference."""

from pathlib import Path

from disastertrace.automated.common import fingerprint
from disastertrace.controlled.renderer import render_request
from disastertrace.local_eval.storage import now, read, write
from disastertrace.repeat_eval import protocol
from disastertrace.repeat_live import audit, package

HERE = Path(__file__).resolve().parent


def test_cached_tokenizer_reconstructs_empty_model_prefix(tmp_path, monkeypatch):
    from vllm.transformers_utils.tokenizer import get_cached_tokenizer
    execution = HERE / "execution_live"
    plan = read(execution / "execution.json")
    datasets = read(execution / "parent/datasets.json")
    slots = read(execution / "schedule.json")
    tokenizer = package.tokenizer(execution, plan)
    cached = get_cached_tokenizer(tokenizer)
    assert type(cached).__name__ == "CachedQwen2TokenizerFast"
    assert type(tokenizer).__name__ == "Qwen2TokenizerFast"
    episodes = {(c, e["episode_id"]): e for c, eps in datasets.items() for e in eps}
    for slot in slots[:12]:
        request = render_request(episodes[slot["condition"], slot["episode_id"]],
                                 slot["checkpoint_id"], method=slot["method"])
        assert protocol.prepare_request(request, slot, cached) == protocol.prepare_request(request, slot, tokenizer)
    run = tmp_path / "synthetic-empty-prefix"
    plan = {**plan, "run_path": str(run)}
    monkeypatch.setattr(package, "verify", lambda path: (plan, datasets, slots))
    origin = "local_model_vllm_p6_paired_v1"
    write(run / "claim.json", {"execution_id": plan["execution_id"], "mode": "model", "origin": origin,
          "generation_authorized": True, "additional_model_calls": 0, "grammar_sampling_performed": True,
          "canonical_run_path": str(run), "started_at": now()})
    write(run / "runtime.json", {"execution_id": plan["execution_id"], "origin": origin,
          "tokenizer_class": type(cached).__name__, "chat_template_sha256": fingerprint(cached.chat_template),
          "observation": plan["preflight"]["result"]["runtime_observation"], "ready_at": now()})
    result = audit.reconstruct(execution, run, require_model=True)
    assert result["summary"]["received"] == 0
    assert result["summary"]["additional_model_calls"] == 0
    assert result["summary"]["unsubmitted"] == 2160
