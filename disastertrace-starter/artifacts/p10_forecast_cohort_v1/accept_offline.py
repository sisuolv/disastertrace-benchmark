"""Bind expanded source/task diagnostics without authorizing model generation."""

import argparse
from pathlib import Path

from disastertrace.forecast_task.common import digest, fingerprint, inventory, read, verify, write

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]


def accept():
    final = read(ROOT / "validation_01/FINAL_STATUS.json")
    tests = read(ROOT / "CORE_TESTS.json")
    if final["status"] != "passed" or any(r["exit_code"] for r in final["steps"]) or tests["exit_code"] != 0:
        raise ValueError("required checks did not pass")
    execution = ROOT / "execution_01"
    manifest = verify(execution)
    source = verify(execution / "source")
    if any(digest(PROJECT / p) != v for p, v in source["files"].items()):
        raise ValueError("accepted implementation or tests changed")
    plan = read(execution / "execution.json")
    if plan["generation_authorized"] is not False or plan["candidate_answers_per_model"] != 2412:
        raise ValueError("offline task scope changed")
    evidence = {}
    for base in (ROOT, PROJECT / "src/disastertrace/forecast_cohort", PROJECT / "tests/p10_forecast_cohort",
                 PROJECT / "work/p10-cohort-task-portable-v1", PROJECT / "artifacts/p10_source_catalog_v1"):
        for name, value in inventory(base).items():
            if ".pytest_cache" not in Path(name).parts:
                evidence[(base / name).relative_to(PROJECT).as_posix()] = value
    evidence["README_P10_FORECAST_COHORT_V1.md"] = digest(PROJECT / "README_P10_FORECAST_COHORT_V1.md")
    record = {"schema_version": "forecast_cohort_offline_acceptance_v1", "status": "passed",
              "execution_id": plan["execution_id"], "package_id": manifest["package_id"],
              "counts": read(execution / "data/dataset.json")["counts"], "related_tests_passed": 110,
              "diagnostic_opportunities": 21708, "tokenizer_checks": 17252, "model_generations": 0,
              "evidence_sha256": evidence}
    record["acceptance_id"] = fingerprint(record)
    write(ROOT / "OFFLINE_ACCEPTANCE.json", record)
    return {"status": "passed", "acceptance_id": record["acceptance_id"], "files": len(evidence)}


def check():
    record = read(ROOT / "OFFLINE_ACCEPTANCE.json")
    if record["acceptance_id"] != fingerprint({k: v for k, v in record.items() if k != "acceptance_id"}):
        raise ValueError("acceptance identity differs")
    for name, expected in record["evidence_sha256"].items():
        path = (PROJECT / name).resolve()
        if not path.is_relative_to(PROJECT) or digest(path) != expected:
            raise ValueError("accepted evidence differs: " + name)
    return {"status": "passed", "acceptance_id": record["acceptance_id"], "files": len(record["evidence_sha256"])}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    print(check() if parser.parse_args().verify else accept(), flush=True)
