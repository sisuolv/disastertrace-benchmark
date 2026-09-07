"""Summarize returned usage and deterministic scores from the bounded live trial."""

import json
from collections import Counter
from pathlib import Path

from disastertrace.automated.common import file_hash, read_jsonl, write_json

root = Path(__file__).resolve().parents[2]
artifact = root / "artifacts/deepseek_probe_v1"
output = root / "work/deepseek-ida-state-v1"
probe_path = root / "work/deepseek-probe-v1/probe.json"
probe = json.loads(probe_path.read_text())
run_result = json.loads((output / "result.json").read_text())
score = json.loads((output / "score.json").read_text())
outcomes = read_jsonl(output / "collection/outcomes.jsonl")
traces = read_jsonl(output / "imported_run/trace.jsonl")
usages = [probe["reported_usage"]] + [row.get("metadata", {}).get("usage") for row in outcomes]
known = [row for row in usages if row is not None]
totals = {name: sum(row[name] for row in known) for name in ("prompt_tokens", "completion_tokens", "total_tokens")}
totals["reasoning_tokens"] = sum((row.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0 for row in known)
has_cache_counts = all(type(row.get("prompt_cache_hit_tokens")) is int and type(row.get("prompt_cache_miss_tokens")) is int and row["prompt_cache_hit_tokens"] + row["prompt_cache_miss_tokens"] == row["prompt_tokens"] for row in known)
estimated_usd = None
if len(known) == len(usages) and has_cache_counts:
    totals["prompt_cache_hit_tokens"] = sum(row["prompt_cache_hit_tokens"] for row in known)
    totals["prompt_cache_miss_tokens"] = sum(row["prompt_cache_miss_tokens"] for row in known)
    estimated_usd = (totals["prompt_cache_hit_tokens"] * 0.007 + totals["prompt_cache_miss_tokens"] * 0.22 + totals["completion_tokens"] * 0.66) / 1_000_000
report = {
    "schema_version": "deepseek_first_trial_v1",
    "sdk_probe": {key: probe[key] for key in ("status", "elapsed_seconds", "response_model", "finish_reason", "reported_usage")},
    "sdk_version": probe["sdk_version"],
    "benchmark_build_id": run_result["build_id"],
    "benchmark_status": run_result["collection"]["status"],
    "provider_attempts_including_probe": 1 + run_result["collection"]["attempts_started"],
    "benchmark_completions": run_result["collection"]["completions_received"],
    "method": run_result["method"],
    "reasoning_effort": "high", "thinking_type": "enabled",
    "event_group": "AL092021", "split": "development",
    "reported_usage_including_probe": totals,
    "responses_missing_usage": len(usages) - len(known),
    "finish_reasons": dict(Counter(row.get("metadata", {}).get("finish_reason", "provider_error") for row in outcomes)),
    "metrics": score["metrics"],
    "per_checkpoint": [{"episode_id": row["episode_id"], "checkpoint_id": row["checkpoint_id"], "status": row["status"], "all_correct": row["all_correct"]} for row in score["per_checkpoint"]],
    "cost_estimate": {
        "usd": estimated_usd, "is_billing_receipt": False,
        "basis": "Returned cache hit/miss and completion counts at documented Sunday off-peak prices; reasoning is already included in completion_tokens.",
        "prices_per_million_tokens": {"cache_hit": 0.007, "cache_miss": 0.22, "completion": 0.66},
        "source": "https://api-docs.deepseek.com/quick_start/pricing/",
        "snapshot_sha256": file_hash(artifact / "docs/pricing.html"),
    },
    "artifact_hashes": {"probe": file_hash(probe_path), "collection_result": file_hash(output / "result.json"), "score": file_hash(output / "score.json")},
    "interpretation": "One public development storm, one model and one method; a live protocol smoke test, not a heldout or cross-model benchmark conclusion.",
}
write_json(artifact / "live_result.json", report)
lines = ["# DeepSeek first live trial", "", report["interpretation"], "",
         f"Model: {probe['response_model']}; reasoning_effort=high; thinking=enabled.",
         f"SDK probe: {probe['status']}, {probe['elapsed_seconds']} seconds; OpenAI SDK {probe['sdk_version']}.",
         f"Benchmark: {report['benchmark_status']}, {report['benchmark_completions']} responses, Ida development, structured_state.",
         "", "| Metric | Correct / opportunities |", "| --- | --- |"]
for name, metric in score["metrics"].items():
    lines.append(f"| {name} | {metric['numerator']}/{metric['denominator']} |")
lines.extend(["", f"Total reported usage including probe: {totals}.",
              f"Estimated cost at documented off-peak prices: USD {estimated_usd}; not a billing receipt.",
              "", "No answer repair, retries, heldout calls or additional model/method runs were performed.",
              "The API key is not stored in project files. Exact benchmark wire requests and response bodies are in the collection journal."])
(artifact / "REPORT.md").write_text("\n".join(lines) + "\n")
print(json.dumps({key: report[key] for key in ("benchmark_status", "provider_attempts_including_probe", "reported_usage_including_probe", "cost_estimate")}, indent=2))
