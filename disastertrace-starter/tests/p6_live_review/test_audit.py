from copy import deepcopy

from disastertrace.controlled.generator import micro_episodes
from disastertrace.repeat_eval import package as parent
from disastertrace.repeat_live import audit as original_audit
from disastertrace.repeat_live import package, runtime, statistics
from disastertrace.repeat_live_review import audit


def test_diagnostic_traces_and_primary_scores_do_not_change(tmp_path):
    episode = micro_episodes()[0]
    parent.freeze(
        {"base": [episode], "irrelevant_scope": [deepcopy(episode)]},
        tmp_path / "parent",
        tmp_path / "parent_registry",
        fixture=True,
    )
    execution = tmp_path / "execution"
    package.freeze(tmp_path / "parent", execution, tmp_path / "registry")
    run = tmp_path / "run"
    runtime.collect(execution, run, mode="invalid-control")
    original = original_audit.reconstruct(execution, run)
    rebuilt = audit.reconstruct(execution, run)
    assert original["traces"] == rebuilt["traces"]
    assert original["summary"]["run_files"] == rebuilt["summary"]["run_files"]
    assert statistics.summarize(original)["counts"] == statistics.summarize(rebuilt)["counts"]
    assert rebuilt["summary"]["review_version"] == "p6_cpu_runtime_text_review_v2"
    assert rebuilt["summary"]["audit_id"] != original["summary"]["audit_id"]
    assert rebuilt["summary"]["additional_model_calls"] == 0
