"""Seal completed P7 evidence and verify accepted ancestors without model execution."""

import argparse
from pathlib import Path

from disastertrace.forecast_task.common import digest, fingerprint, inventory, read
from disastertrace.forecast_live.storage import now, write

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]


def check_record(path):
    record = read(path)
    if record["acceptance_id"] != fingerprint({k: v for k, v in record.items() if k != "acceptance_id"}):
        raise ValueError("acceptance identity differs")
    files = record["evidence_sha256"] if "evidence_sha256" in record else record["files"]
    for name, expected in files.items():
        target = (PROJECT / name).resolve()
        if not target.is_relative_to(PROJECT.parent) or digest(target) != expected:
            raise ValueError("accepted evidence changed: " + name)
    return {"acceptance_id": record["acceptance_id"], "verified_files": len(files)}


def accept():
    status = read(ROOT / "finalization_01/FINAL_STATUS.json")
    if status["status_id"] != fingerprint({k: v for k, v in status.items() if k != "status_id"}):
        raise ValueError("final status identity differs")
    if (status["status"] != "passed" or status["counts"]["raw_returned"] != 1542
            or status["score_counts"]["all_correct"] != 527
            or any(j["state"] != "SUCCEEDED" or not j["released"] for j in status["platform_jobs"])):
        raise ValueError("completed results differ")
    for name in ("report", "verify_report", "token_replay", "cpu_relocation"):
        if read(ROOT / "finalization_01" / (name + "_result.json"))["exit_code"] != 0:
            raise ValueError("required independent check failed: " + name)
    ancestors = {}
    for name in ("p7_forecast_task_v1/OFFLINE_ACCEPTANCE.json", "p6_live_v1/COMPLETED_ACCEPTANCE.json",
                 "p6_offline_v1/OFFLINE_ACCEPTANCE.json"):
        ancestors[name] = check_record(PROJECT / "artifacts" / name)
    write(ROOT / "PRESERVATION.json", {"at": now(), "status": "passed", "ancestors": ancestors})
    files = {}
    for base in (ROOT, PROJECT / "src/disastertrace/forecast_live", PROJECT / "tests/p7_forecast_live",
                 PROJECT / "work/p7-native-qwen3-v1"):
        for name, value in inventory(base).items():
            if ".pytest_cache" not in Path(name).parts:
                files[(base / name).relative_to(PROJECT).as_posix()] = value
    files["README_P7_FORECAST_LIVE_V1.md"] = digest(PROJECT / "README_P7_FORECAST_LIVE_V1.md")
    record = {"schema_version": "forecast_live_completed_acceptance_v1", "status": "passed", "at": now(),
              "execution_id": status["execution_id"], "report_id": status["report_id"],
              "counts": status["counts"], "score_counts": status["score_counts"],
              "all_gpu_jobs_released": True, "ancestors": ancestors, "evidence_sha256": files}
    record["acceptance_id"] = fingerprint(record)
    write(ROOT / "COMPLETED_ACCEPTANCE.json", record)
    return {"acceptance_id": record["acceptance_id"], "verified_files": len(files), "status": "passed"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    print(check_record(ROOT / "COMPLETED_ACCEPTANCE.json") if parser.parse_args().verify else accept(), flush=True)
