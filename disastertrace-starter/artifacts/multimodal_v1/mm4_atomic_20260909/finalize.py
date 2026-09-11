"""One-use reporting and resource accounting after all four jobs are terminal."""

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[2]
sys.path.insert(0, str(ROOT / "source/src"))

from disastertrace.multimodal_atomic_v1.audit import reconstruct
from disastertrace.multimodal_v1.storage import digest, now, read, write


def stamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def main():
    write(ROOT / "FINALIZATION_CLAIM.json", {"at": now()})
    report = reconstruct(ROOT)
    jobs, boundaries, allocations = [], [], []
    for worker in ("0", "1", "2", "3"):
        job = read(ROOT / "acp" / worker / "JOB.json")
        argv = ["/mnt/afs/260010168/bin/sco", "acp", "jobs", "describe",
                "--workspace-name=share-space", "--format=json", job["job_id"]]
        reply = subprocess.run(argv, capture_output=True, text=True, timeout=60, check=True)
        data = json.loads(reply.stdout)
        write(ROOT / "acp" / worker / "FINAL_JOB.json", data)
        if data["state"] not in {"SUCCEEDED", "FAILED", "DELETED"}:
            raise ValueError("job is not terminal")
        count = sum(int(spec["requests"]["nvidia.com/gpu"]) * int(spec["replicas"])
                    for role in data["roles"] for spec in role["resource_spec"])
        if count != 1 or data["resource_pool"]["name"] != "computing-cluster-01g-02":
            raise ValueError("unexpected allocation")
        if data["lme"]["current_retries"] != 0:
            raise ValueError("unexpected platform retry")
        if data["state"] == "SUCCEEDED" and not (ROOT / "gpu_runs" / worker / "DONE.json").exists():
            raise ValueError("successful platform state lacks worker completion")
        start, end = stamp(data["create_time"]), stamp(data["update_time"])
        allocated = stamp(data["start_time"]) if data.get("start_time") else None
        boundaries.extend([(start, 1), (end, -1)])
        if allocated is not None:
            allocations.extend([(allocated, 1), (end, -1)])
        hardware = read(ROOT / "gpu_runs" / worker / "HARDWARE.json")
        if hardware["count"] != 1 or "H100" not in hardware["name"]:
            raise ValueError("actual GPU hardware mismatch")
        jobs.append({"worker": worker, "job_id": job["job_id"], "state": data["state"],
                     "created_at": data["create_time"], "started_at": data.get("start_time"),
                     "terminal_updated_at": data["update_time"],
                     "reservation_seconds": end - start,
                     "allocation_seconds": end - allocated if allocated else None,
                     "nvidia_smi": hardware["nvidia_smi"]})
    def maximum(events):
        active = peak = 0
        for _, delta in sorted(events):
            active += delta
            peak = max(peak, active)
        return peak
    if maximum(boundaries) > 4:
        raise ValueError("H100 global cap exceeded")
    account_argv = ["/mnt/afs/260010168/bin/sco", "acp", "jobs", "list", "--workspace-name=share-space",
                    "--user-name=260010168", "--page-size=500", "--format=json"]
    account = json.loads(subprocess.check_output(account_argv, text=True, timeout=60))
    write(ROOT / "acp/ACCOUNT_FINAL.json", account)
    active = [{"name": j["name"], "state": j["state"]} for j in account
              if j["state"] not in {"SUCCEEDED", "FAILED", "DELETED"}]
    if active or len(account) >= 500:
        raise ValueError("final account reservation check is not clear")
    write(ROOT / "RESOURCE_ACCOUNTING.json", {"at": now(), "jobs": jobs, "active_account_jobs": active,
          "max_reserved_h100": maximum(boundaries), "max_allocated_h100": maximum(allocations),
          "reservation_gpu_hours": sum(j["reservation_seconds"] for j in jobs) / 3600,
          "allocation_gpu_hours": sum(j["allocation_seconds"] or 0 for j in jobs) / 3600,
          "limitation": "platform timestamp intervals, not GPU utilization or billing; no one-GPU speedup comparison"})
    write(ROOT / "REPORT.json", report)
    tasks = {t["task_id"]: t for t in read(ROOT / "REQUEST_PLAN.json")["tasks"]}
    refs = read(ROOT / "references.json")
    groups = {}
    for row in report["rows"]:
        tid, family = row["task_id"], row["family"]
        if family == "spatial":
            condition = "map_present" if tasks[tid]["inputs"]["evidence"] else "map_absent"
        elif family == "watch":
            condition = "site_line_present" if next(iter(refs[tid]["state"].values()))["watched"] is not None else "site_line_absent"
        elif family == "selection":
            condition = "three_queries" if len(tasks[tid]["inputs"]["queries"]) == 3 else "two_queries"
        else:
            condition = "prescribed_logic"
        key = family + "/" + condition
        group = groups.setdefault(key, {"planned": 0, "strict_correct": 0, "task_ids": []})
        group["planned"] += 1
        group["strict_correct"] += row["strict_correct"]
        group["task_ids"].append(tid)
    errors = [r for r in report["rows"] if not r["strict_correct"]]
    write(ROOT / "ERROR_ANALYSIS.json", {"origin": "posthoc_descriptive_analysis", "conditions": groups,
          "field_error_counts": dict(Counter(d["field"] for r in report["rows"] for d in r["differences"])),
          "errors": errors, "revision_gate": report["revision_diagnostic_gate"],
          "causal_internal_model_explanation_established": False})
    previous = read(ROOT / "PRIOR_BINDINGS.json")
    for name, expected in previous.items():
        if digest((PROJECT / name).read_bytes()) != expected:
            raise ValueError("historical evidence changed: " + name)
    write(ROOT / "PRESERVATION_AFTER.json", {"at": now(), "status": "passed", "files": len(previous)})
    replay = read(ROOT / "input_replay_01/VERIFIED.json")
    if len(replay["captures"]) != report["dispatches"] or not all(r["output_decoding_equal"] for r in replay["captures"]):
        raise ValueError("actual processor/token replay incomplete")
    review = PROJECT / "work/mm4-atomic-cpu-review-20260909"
    review.mkdir(parents=True, exist_ok=False)
    shutil.copytree(ROOT, review / "batch", ignore=shutil.ignore_patterns("__pycache__"))
    inventory = {str(p.relative_to(review)): digest(p.read_bytes()) for p in (review / "batch").rglob("*") if p.is_file()}
    denied = [str(ROOT), str(ROOT.parent / "mm0_2_20260909"), str(ROOT.parent / "mm3_20260909"),
              str(ROOT.parent / "mm3_contract_v2_live_20260909"), str(PROJECT / "src"),
              read(ROOT / "EXECUTION.json")["model_directory"]]
    manifest = {"files": inventory, "denied_paths": denied}
    write(review / "REVIEW_MANIFEST.json", manifest)
    argv = ["/mnt/afs/260010168/.venvs/disastertrace-mm-cpu-v1/bin/python", str(review / "batch/review_cpu.py"),
            "--bundle", str(review), "--receipt", str(review / "VERIFIED.json")]
    reply = subprocess.run(argv, capture_output=True, text=True, timeout=300)
    write(ROOT / "CPU_REVIEW_COMMAND.json", {"argv": argv, "returncode": reply.returncode,
          "stdout": reply.stdout, "stderr": reply.stderr})
    if reply.returncode:
        raise RuntimeError("relocated CPU review failed; preserve this attempt")
    shutil.copyfile(review / "VERIFIED.json", ROOT / "CPU_REVIEW_RESULT.json")
    write(ROOT / "FINALIZATION_RESULT.json", {"status": "passed", "at": now(),
          "report_sha256": digest((ROOT / "REPORT.json").read_bytes()),
          "planned": report["planned"], "dispatches": report["dispatches"],
          "cpu_review": str(review), "all_jobs_terminal": True, "active_account_jobs": 0})
    print(json.dumps({"status": "passed", "planned": report["planned"], "by_family": report["by_family"]}))


if __name__ == "__main__":
    main()
