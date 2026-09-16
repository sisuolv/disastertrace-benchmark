"""Check this local planning package without importing benchmark code or running jobs."""

import datetime as dt
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main():
    checks = []

    def check(name, passed, detail=None):
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    work = json.loads((ROOT / "WORK_PACKAGES.json").read_text())
    tasks = {row["id"]: row for row in work["tasks"]}
    check("unique_task_ids", len(tasks) == len(work["tasks"]))
    check("planning_only", work["execution_authorized"] is False
          and work["new_launchers_created"] is False
          and all(value is False for value in work["stage_execution_authorized"].values())
          and all(row["execution_authorized"] is False for row in tasks.values()))
    check("dependencies_do_not_grant_authorization",
          work["dependency_completion_is_execution_authorization"] is False)
    edges = {key: row["requires_verified"] + row["requires_terminal"]
             for key, row in tasks.items()}
    check("known_dependencies", all(dep in tasks for deps in edges.values() for dep in deps))
    ordered = []
    pending = set(tasks)
    while pending:
        ready = sorted(key for key in pending if set(edges[key]) <= set(ordered))
        if not ready:
            break
        ordered.extend(ready)
        pending.difference_update(ready)
    check("acyclic_dependencies", not pending, {"topological_order": ordered})
    check("local_acceptance_independent_of_external_audit",
          "W07.closeout" not in edges["W05.local_acceptance"]
          and tasks["W05.local_acceptance"]["wait_for_original_fullweek_audit"] is False)
    check("batch_closeout_not_blocked_by_full_acceptance",
          "W05.full_acceptance" not in edges["W05.batch_closeout"]
          and tasks["W05.batch_closeout"]["wait_for_external_job"] is False)
    check("full_acceptance_requires_scientific_and_engineering_receipts",
          {"W07.closeout", "W11.branch_engineering", "W01.bank_guard",
           "W06.sample_summary", "W06.inventory"} <= set(edges["W05.full_acceptance"]))
    check("parent_and_formal_fork_gates",
          "parent_day_terminal_and_verified" in tasks["W11.parent_materialization"]["external_gates"]
          and "W11.noop_equivalence" in edges["W11.branch_engineering"]
          and "formal_branch_qualified=true" in tasks["W11.fork_qualification"]["verified_output_requires"])
    caps = work["first_batch_limits"]
    expected = {"wall_hours": 10, "additional_cpu": 16, "additional_ram_GiB": 64,
                "new_gpu": 0, "new_benchmark_model_calls": 0, "new_model_API_calls": 0,
                "new_upstream_source_HTTP": 0, "new_fits": 0, "max_unique_parents": 6,
                "max_parent_reconstruction_attempts": 6,
                "max_original_policy_continuation_attempts": 6,
                "max_treatment_branch_attempts": 24}
    check("stage_A_caps", all(caps.get(key) == value for key, value in expected.items())
          and caps["confirmation_access"] is False)
    check("attempt_caps_separate_and_consistent",
          [tasks[key]["max_attempts"] for key in
           ("W11.parent_materialization", "W11.noop_equivalence", "W11.branch_engineering")]
          == [6, 6, 24])
    check("shutdown_window", caps["first_qualified_parent_gate_hour"] == 4
          and caps["no_new_branch_after_hour"] == 8.5
          and caps["worker_stop_latest_hour"] == 9.5
          and tasks["W05.batch_closeout"]["close_by_hours"] == 10)
    model = tasks["W12.selector"]
    check("deferred_model_caps", model["max_sessions"] * model["max_decisions_per_session"]
          == model["max_formal_requests"] == 288
          and model["max_compatibility_requests"] == 2 and model["max_h100"] == 4
          and model["stage"] == "C")
    check("independent_C2_confirmation_path",
          "W12.selector" not in edges["W13.c2_confirmation"]
          and "W11.branch_science" in edges["W13.c2_confirmation"]
          and "shared_calendar_requires_both_freezes_before_opening_or_disjoint_calendars"
          in tasks["W13.c2_confirmation"]["external_gates"])
    parents = json.loads((ROOT / "PARENT_CANDIDATES.json").read_text())
    check("metadata_parent_roster", len(parents["parents"]) == 6
          and len({(p["region"], p["threshold"]) for p in parents["parents"]}) == 6
          and parents["global_dates"] == 1
          and parents["independent_processes"] is None
          and all(p["reconstructability"] == "not_yet_tested" for p in parents["parents"]))
    inputs = json.loads((ROOT / "REVIEW_INPUTS.json").read_text())
    source_mismatches = []
    for row in inputs["inputs"]:
        if digest(Path(row["input_path"])) != row["sha256"]:
            source_mismatches.append(row["input_path"])
        if "copy" in row and digest(ROOT / row["copy"]) != row["sha256"]:
            source_mismatches.append(row["copy"])
        for member in row["members"]:
            if digest(ROOT / member["path"]) != member["sha256"]:
                source_mismatches.append(member["path"])
    check("review_input_bytes", not source_mismatches, source_mismatches)
    protected = json.loads((ROOT / "PROTECTED_FILES.json").read_text())
    changed = [name for name, sha in protected["files"].items()
               if not Path(name).is_file() or digest(Path(name)) != sha]
    check("protected_files_unchanged", not changed,
          {"count": len(protected["files"]), "changed": changed})
    pointer = Path("/mnt/afs/260010168/extreme_weather_benchmark/plan/plan_v12_0915/"
                   "DisasterTrace_V12_Amended_Plan_10H_CN.md")
    broken = []
    link_count = 0
    for path in [*sorted(ROOT.glob("*.md")), pointer]:
        for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
            target = target.split("#", 1)[0].strip("<>")
            if not target or "://" in target:
                continue
            link_count += 1
            destination = path.parent / target
            if destination == ROOT / "VALIDATION.json":
                continue
            if not destination.exists():
                broken.append({"source": path.name, "target": target})
    check("document_file_links", not broken, {"checked": link_count, "broken": broken})
    state = json.loads((ROOT / "CURRENT_STATE.json").read_text())
    check("evidence_not_mislabeled_as_experiments",
          state["regression_rerun_here"] is False
          and inputs["review_probes_executed_here"] is False
          and state["new_jobs_started"] == 0
          and state["confirmation_opened"] is False)
    result = {"at": dt.datetime.now(dt.timezone.utc).isoformat(),
              "scope": "local planning package structure, caps, links and selected preservation only",
              "passed": all(row["passed"] for row in checks), "checks": checks,
              "production_tests_run": 0, "review_probes_run": 0,
              "weather_replays_run": 0, "model_calls": 0, "source_HTTP_calls": 0,
              "remote_reverified_this_turn": False}
    (ROOT / "VALIDATION.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"passed": result["passed"], "checks": len(checks),
                      "failed": [r["name"] for r in checks if not r["passed"]]}))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
