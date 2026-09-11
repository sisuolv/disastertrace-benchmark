import importlib.util
from pathlib import Path

import pytest

from disastertrace.forecast_task.common import digest, write


@pytest.fixture
def state(monkeypatch, tmp_path):
    source = Path(__file__).resolve().parents[2] / "artifacts/autonomy_10h_v1/seal_cohort_evidence_v2.py"
    spec = importlib.util.spec_from_file_location("acceptance_locations", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    project = tmp_path / "project"
    root = project / "artifacts/autonomy_10h_v1"
    bundle = project / "artifacts/p12_compact_grammar_v1"
    final = bundle / "finalization_qwen3_01"
    reviews = root / "reviews_continuation_v2"
    write(final / "FINAL_STATUS.json", {"status": "passed"})
    write(reviews / "p12_qwen3.json", {"analysis_id": "fixture"})
    record = {"phase": "p12", "model_profile": "qwen3",
              "finalization": final.relative_to(project).as_posix(),
              "review_directory": reviews.relative_to(project).as_posix(),
              "final_status_sha256": digest(final / "FINAL_STATUS.json"),
              "analysis_sha256": digest(reviews / "p12_qwen3.json")}
    monkeypatch.setattr(module, "ROOT", root)
    monkeypatch.setattr(module, "PROJECT", project)
    return module, bundle, reviews, record


def save(state):
    module, _, reviews, record = state
    write(reviews / "LOCATION_p12_qwen3.json", record)


def test_declared_location_resolves_exact_existing_bytes(state):
    module, bundle, reviews, record = state
    save(state)
    final, actual_reviews, actual = module.locate("p12", "qwen3", bundle)
    assert final == bundle / "finalization_qwen3_01"
    assert actual_reviews == reviews
    assert actual == record


@pytest.mark.parametrize("field,value", [("phase", "p13"), ("model_profile", "deepseek_r1"),
                                        ("finalization", "../../outside"), ("review_directory", "../../outside"),
                                        ("analysis_sha256", "changed"), ("final_status_sha256", "changed")])
def test_other_models_paths_or_changed_evidence_cannot_be_substituted(state, field, value):
    module, bundle, _, record = state
    record[field] = value
    save(state)
    with pytest.raises(ValueError):
        module.locate("p12", "qwen3", bundle)


def test_second_finalization_requires_the_preserved_cpu_continuation_record(state):
    module, bundle, _, record = state
    second = bundle / "finalization_qwen3_02"
    write(second / "FINAL_STATUS.json", {"status": "passed"})
    record["finalization"] = second.relative_to(module.PROJECT).as_posix()
    record["final_status_sha256"] = digest(second / "FINAL_STATUS.json")
    save(state)
    with pytest.raises(FileNotFoundError):
        module.locate("p12", "qwen3", bundle)
