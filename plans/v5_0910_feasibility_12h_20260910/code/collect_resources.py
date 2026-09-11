"""Reconcile actual job intervals, request intents, captured bytes and failures."""

from collections import Counter
from datetime import datetime, timezone
import json

from common import ROOT, dump
from launch_gpu import own_jobs, requested_gpus, TERMINAL


def dt(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def peak(intervals):
    events = sorted([(dt(start), count) for start, _, count in intervals] +
                    [(dt(end), -count) for _, end, count in intervals])
    current = maximum = 0
    for _, delta in events:
        current += delta
        maximum = max(maximum, current)
    if current:
        raise ValueError("resource interval accounting is unbalanced")
    return maximum


def main():
    scope = json.loads((ROOT / "SCOPE.json").read_text())
    jobs, reservations, allocations, worker_intervals, model_intervals = [], [], [], [], []
    total_calls, tokens_in, tokens_out, generate_seconds = 0, 0, 0, 0
    for batch in sorted((ROOT / "gpu").glob("wave*")):
        if not (batch / "submissions").exists():
            continue
        data = json.loads((batch / "ACP_TERMINAL.json").read_text())
        for job in data["jobs"]:
            if job["state"] != "SUCCEEDED":
                raise ValueError("GPU job is not successfully terminal")
            count = requested_gpus(job)
            reservations.append((job["create_time"], job["complete_time"], count))
            allocations.append((job["start_time"], job["complete_time"], count))
            jobs.append({"wave": batch.name, "id": job["name"], "state": job["state"],
                "requested_gpus": count, "cluster": job["resource_pool"]["name"],
                "create_time": job["create_time"], "start_time": job["start_time"], "complete_time": job["complete_time"]})
        for worker in (batch / "runs").iterdir():
            hardware = json.loads((worker / "HARDWARE.json").read_text())
            loaded = json.loads((worker / "LOADED.json").read_text())
            done = json.loads((worker / "DONE.json").read_text())
            worker_intervals.append((hardware["at"], done["at"], hardware["count"]))
            model_intervals.append((loaded["at"], done["at"], hardware["count"]))
    for i in range(1, 8):
        audit = json.loads((ROOT / ("analysis/WAVE%d_AUDIT.json" % i)).read_text())
        total_calls += audit.get("captured_model_calls", audit.get("captured_calls", 0))
        calls = audit["calls"] if i == 5 else [c for row in audit["rows"] for c in row["calls"]]
        tokens_in += sum(c["input_tokens"] for c in calls)
        tokens_out += sum(c["output_tokens"] for c in calls)
        generate_seconds += sum(c["seconds"] for c in calls)
    attempts = [json.loads(p.read_text()) for p in (ROOT / "attempts").glob("*/response.json")]
    source_bytes = sum(a["captured_bytes"] for a in attempts)
    files, weight_bytes = [], 0
    for directory in ["model32_acquisition", "model32_resume_01", "internvl_acquisition"]:
        for path in (ROOT / "gpu" / directory).glob("*.result.json"):
            row = json.loads(path.read_text())
            weight_bytes += row.get("received_bytes", row.get("actual_bytes", 0))
            files.append({"run": directory, "path": row["path"], "status": row["status"]})
    active = [job for job in own_jobs() if job["state"] not in TERMINAL]
    if active:
        raise ValueError("account still has active requested GPU slots")
    reservation_hours = sum((dt(end) - dt(start)).total_seconds() * count for start, end, count in reservations) / 3600
    allocation_hours = sum((dt(end) - dt(start)).total_seconds() * count for start, end, count in allocations) / 3600
    if peak(reservations) > 4 or reservation_hours > scope["max_gpu_hours"] or total_calls > 3600:
        raise ValueError("resource cap exceeded")
    if source_bytes > scope["max_captured_response_body_bytes"] or weight_bytes > scope["max_additional_weight_bytes"]:
        raise ValueError("download byte cap exceeded")
    report = {"created_at": datetime.now(timezone.utc).isoformat(), "jobs": jobs, "terminal_jobs": len(jobs),
        "all_jobs_succeeded": True, "active_account_jobs": [], "captured_model_calls": total_calls,
        "input_tokens": tokens_in, "output_tokens": tokens_out,
        "sum_response_generation_seconds": generate_seconds,
        "create_to_terminal_gpu_hours": reservation_hours, "start_to_terminal_gpu_hours": allocation_hours,
        "peak_requested_gpus": peak(reservations), "peak_started_job_gpus": peak(allocations),
        "peak_overlapping_H100_hardware_receipts": peak(worker_intervals),
        "peak_overlapping_model_loaded_intervals": peak(model_intervals),
        "source_recorded_HTTP_attempts": len(attempts), "source_captured_body_bytes": source_bytes,
        "source_HTTP_statuses": dict(Counter(str(a["http_status"]) for a in attempts)),
        "source_incomplete_attempts": sum(not a["complete"] for a in attempts),
        "weight_file_request_intents": len(files), "weight_received_bytes": weight_bytes,
        "weight_initial_failed_requests": [f for f in files if f["status"] != "verified"],
        "weight_redirect_HTTP_hops": None,
        "accounting_limits": ["GPU intervals are reservation/allocation proxies, not invoices or utilization.",
            "Generation wall time excludes some setup and is not GPU kernel time.",
            "Tokenizer counts differ across architectures.",
            "Weight downloader records file attempts/bytes, but did not retain every automatic HTTP redirect hop; exact weight HTTP transaction cap cannot be retrospectively certified."],
        "paid_API_calls": 0, "training_jobs": 0, "heldout_inference": 0}
    dump(ROOT / "RESOURCE_ACCOUNTING.json", report)
    print(json.dumps({k: v for k, v in report.items() if k not in {"jobs", "weight_initial_failed_requests"}}, indent=2))


if __name__ == "__main__":
    main()
