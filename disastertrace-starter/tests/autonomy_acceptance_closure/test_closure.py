import importlib.util
import os
from pathlib import Path

import pytest

from disastertrace.forecast_task.common import digest, fingerprint, inventory, read, write


def signed(value, key):
    return {**value, key: fingerprint(value)}


@pytest.fixture
def phase(tmp_path):
    project = tmp_path / "project"
    root = project / "artifacts/autonomy_10h_v1"
    root.mkdir(parents=True)
    original = Path(__file__).resolve().parents[2] / "artifacts/autonomy_10h_v1"
    selected = os.environ.get("ACCEPTANCE_CLOSURE_SOURCE", "seal_cohort_evidence_v3.py")
    source = root / selected
    source.write_bytes((original / selected).read_bytes())
    spec = importlib.util.spec_from_file_location("closure_sealer", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    bundle = project / "artifacts/p12_compact_grammar_v1"
    reviews = root / "reviews_continuation_v2"
    final = bundle / "finalization_qwen3_01"
    for directory in (reviews, root / "cohort_reviews_01", root / "cohort_stops_01",
                      project / "src/disastertrace/compact_live", project / "src/disastertrace/cohort_review"):
        directory.mkdir(parents=True)
    for name in ("p12_compact_live", "p12_chain", "autonomy_acceptance", "cohort_review",
                 "autonomy_observer", "autonomy_review_continuation", "autonomy_acceptance_locations",
                 "autonomy_acceptance_closure"):
        (project / "tests" / name).mkdir(parents=True)
    for suffix in ("model-v1", "diagnostics-v1", "portable-v1"):
        (project / ("work/p12-compact-qwen3-" + suffix)).mkdir(parents=True)
    bundle.mkdir(parents=True)
    (bundle / "DESIGN.md").write_text("fixture design\n")
    design = signed({"design_sha256": digest(bundle / "DESIGN.md"), "planned_answers": 6,
                     "model_profiles": ["qwen3"]}, "design_id")
    write(bundle / "PREREGISTRATION.json", design)
    write(bundle / "TEST_GATES.json", {"core_tests_exit_code": 0, "backend_tests_exit_codes": {},
                                       "source_files": {}, "test_files": {}, "logs": {}})
    write(bundle / "CPU_ACCEPTANCE_qwen3.json", {"status": "passed", "design_id": design["design_id"],
                                               "portable_review_exit_code": 0, "source_files": {}})
    write(bundle / "PREFLIGHT_ACCEPTANCE_qwen3.json",
          signed({"validation": {"status": "passed", "model_calls": 0}}, "acceptance_id"))
    report = signed({"execution_id": "fixture", "counts": {"raw_returned": 2},
                     "scores": {"counts": {"planned": 6, "received": 2, "all_correct": 1}},
                     "platform_jobs": [{"worker_id": i, "state": "FAILED", "released": True}
                                       for i in (0, 1)]}, "report_id")
    analysis = signed({"execution_id": report["execution_id"], "report_id": report["report_id"],
                       "counts": report["counts"], "score_counts": report["scores"]["counts"],
                       "single_repeat_only": True, "planned_denominator_is_primary": True,
                       "population_inference": False, "unit_normalization": False,
                       "new_model_calls": 0}, "analysis_id")
    write(final / "global_report.json", report)
    write(final / "token_replay.json", {"fixture": True})
    write(final / "cpu_relocated/receipt.json", {"fixture": True})
    status = signed({"status": "passed", "execution_id": report["execution_id"],
                     "report_id": report["report_id"], "counts": report["counts"],
                     "score_counts": report["scores"]["counts"], "platform_jobs": report["platform_jobs"],
                     "report_sha256": digest(final / "global_report.json"),
                     "token_replay_sha256": digest(final / "token_replay.json"),
                     "cpu_relocation_sha256": digest(final / "cpu_relocated/receipt.json")}, "status_id")
    write(final / "FINAL_STATUS.json", status)
    write(reviews / "p12_qwen3.json", analysis)
    write(reviews / "p12_deepseek_r1.json", {"unrelated_case": True})
    write(reviews / "LOCATION_p12_qwen3.json", {
        "phase": "p12", "model_profile": "qwen3", "finalization": final.relative_to(project).as_posix(),
        "review_directory": reviews.relative_to(project).as_posix(),
        "final_status_sha256": digest(final / "FINAL_STATUS.json"),
        "analysis_sha256": digest(reviews / "p12_qwen3.json"),
        **{key: analysis[key] for key in ("analysis_id", "report_id", "execution_id")}})

    def command(folder, name, extra=None):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / (name + ".log")).write_text("fixture passed\n")
        write(folder / (name + "_intent.json"), {"argv": ["fixture"]})
        write(folder / (name + "_result.json"), {
            "exit_code": 0, "log_sha256": digest(folder / (name + ".log")), **(extra or {})})

    for label in ("report", "verify_report", "token_replay", "cpu_relocation"):
        command(final, label)
    for action in ("analyze", "verify"):
        command(reviews, "p12_qwen3_" + action)
    for name in ("continue_reviews_v2.py", "continue_live_observer_v2.py", "seal_cohort_evidence.py",
                 "REVIEW_CONTINUATION_V2_GATES.json", "PENDING_OBSERVER_V2_GATES.json",
                 "ROLE_REVIEW_RETIREMENT_INTENT.json", "ROLE_REVIEW_RETIREMENT_ACTION.json",
                 "analyze_cohort_stop.py", "watch_cohort_reviews.py"):
        (root / name).write_text("fixture\n")
    if selected != "seal_cohort_evidence_v2.py":
        (root / "seal_cohort_evidence_v2.py").write_bytes((original / "seal_cohort_evidence_v2.py").read_bytes())
    for folder in (reviews, root / "cohort_reviews_01"):
        write(folder / "CLAIM.json", {"fixture": True})
    write(root / "cohort_reviews_01/FINAL_STATUS.json", {"status": "failed"})
    for label, filename in (("autonomy_acceptance_02", "seal_cohort_evidence.py"),
                            ("acceptance_locations_v2_01", "seal_cohort_evidence_v2.py"),
                            ("acceptance_closure_v3_01", selected)):
        command(root / "validation", label, {"script_sha256": digest(root / filename)})
    (project / "README_P12_COMPLETED_V1.md").write_text("fixture findings\n")
    (bundle / "FINDINGS.md").write_text("fixture findings\n")
    seed = project / "seed.json"
    write(seed, {"fixture": True})
    for folder, filename in (("p10_forecast_cohort_v1", "OFFLINE_ACCEPTANCE.json"),
                             ("p11_cohort_live_v1", "COMPLETED_ACCEPTANCE.json")):
        write(project / "artifacts" / folder / filename,
              signed({"evidence_sha256": {"seed.json": digest(seed)}}, "acceptance_id"))
    return module, bundle, reviews


def test_full_acceptance_covers_analysis_and_both_command_chains(phase):
    module, bundle, reviews = phase
    module.accept("p12")
    accepted = read(bundle / "COMPLETED_ACCEPTANCE.json")["evidence_sha256"]
    expected = {name: sha for name, sha in inventory(reviews).items() if name.startswith("p12_qwen3")}
    assert len(expected) == 7
    for name, sha in expected.items():
        assert accepted.get((reviews / name).relative_to(module.PROJECT).as_posix()) == sha
    assert (reviews / "p12_deepseek_r1.json").relative_to(module.PROJECT).as_posix() not in accepted
    assert module.verify_record(bundle / "COMPLETED_ACCEPTANCE.json", module.PROJECT)["verified_files"] == len(accepted)


@pytest.mark.parametrize("filename", ["p12_qwen3.json", "p12_qwen3_analyze.log", "p12_qwen3_verify.log"])
def test_analysis_or_command_log_mutation_breaks_accepted_inventory(phase, filename):
    module, bundle, reviews = phase
    module.accept("p12")
    (reviews / filename).write_text("changed after acceptance\n")
    with pytest.raises(ValueError, match="accepted evidence differs"):
        module.verify_record(bundle / "COMPLETED_ACCEPTANCE.json", module.PROJECT)
