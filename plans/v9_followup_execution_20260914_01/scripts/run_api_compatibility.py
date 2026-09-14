"""Two original transport/settings checks, separate from benchmark scores."""

import datetime as dt
from pathlib import Path

from disastertrace.monitoring_v1.api_capture import ApiBudget, capture
from disastertrace.monitoring_v1.spool_backend import digest, publish, read

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "api_compatibility_01"


def main():
    OUT.mkdir(exist_ok=False)
    models = ["deepseek-flash", "deepseek-v4-pro"]
    messages = [{"role": "user", "content": 'Return exactly this JSON object: {"ok":true}'}]
    source = ROOT.parents[1] / "disastertrace-starter/src/disastertrace/monitoring_v1/api_capture.py"
    publish(OUT/"FREEZE.json", {"models": models, "messages": messages, "max_tokens": 64,
        "input_cap": 8192, "thinking": "disabled", "retries": 0, "model_calls_ceiling": 2,
        "fee_upper_usd": 0.10, "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_sha256": digest(source),
        "pricing_sha256": digest(ROOT/"model_catalog/probe_01/deepseek_pricing.body"),
        "scope": "API transport and JSON-settings compatibility only; zero benchmark questions"})
    publish(OUT/"BUDGET.json", {"limit_nanodollars": 100_000_000, "max_calls": 2, "calls": {}})
    results = []
    for model in models:
        raw, details = capture(messages, model, "compatibility:"+model, OUT/model,
            ApiBudget(OUT/"BUDGET.json"), max_tokens=64, input_cap=8192)
        import json

        valid = json.loads(raw) == {"ok": True} and details["ended_with_eos"]
        results.append({"model": model, "valid": valid, "details": details})
    publish(OUT/"COMPLETE.json", {"results": results, "compatible": all(r["valid"] for r in results),
        "budget": read(OUT/"BUDGET.json"), "benchmark_calls": 0})
    print({"compatible": all(r["valid"] for r in results), "actual_model_calls": len(results)})


if __name__ == "__main__":
    main()
