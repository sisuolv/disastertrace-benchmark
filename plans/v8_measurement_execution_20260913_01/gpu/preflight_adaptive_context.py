"""Measure full-day native request sizes without loading or calling a model."""

import hashlib
import json
import sys
from pathlib import Path

from disastertrace.monitoring_fixed_v1.aviation import (
    TRUTH_TO_SUPPORT,
    FrozenFrequencyPredictor,
    visible_e_status,
)
from disastertrace.monitoring_fixed_v1.contracts import EvidenceBundle
from disastertrace.monitoring_v1.dataset import load_session
from disastertrace.monitoring_v1.policies import run_session
from disastertrace.monitoring_v1.spool_backend import publish, read
from transformers import AutoTokenizer

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "scripts"))
from run_program_calendar import configs


def main():
    output = HERE / "gpu/adaptive_context_preflight_02"
    output.mkdir(exist_ok=False)
    plan = read(HERE / "gpu/large_diagnostic_02/PLAN.json")
    tokenizer = AutoTokenizer.from_pretrained(
        plan["models"]["qwen235b_fp8"]["directory"], local_files_only=True
    )
    bank = read(HERE / "contracts/BANK.json")
    data = load_session(
        HERE / "development_dataset_v2",
        stations=["KSFO", "KOAK", "KSJC"],
        hours=24,
        threshold=5000,
    )
    config = configs(24, "base_bound_override")["P04_risk_shared"]
    config.pop("execution_contract")
    config.update(
        request_budget=48,
        model_call_budget=240,
        input_token_cap=131072,
        output_token_cap=512,
        token_cap=240 * 131584,
        selector_kind="llm",
        predictor_kind="llm",
        isolation_mode="actual_cost_clock",
    )
    rows = []

    def program(system, request, call_id):
        messages = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": json.dumps(request, sort_keys=True, separators=(",", ":")),
            },
        ]
        ids = tokenizer.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True, enable_thinking=False
        )
        if call_id.startswith("select-"):
            answer = {
                "query_order": sorted(request["queries"]),
                "forecast_handles": sorted(request["targets"])[
                    : request["per_tick_forecast_cap"]
                ],
            }
        else:
            bundle = EvidenceBundle.freeze(request)
            answer = {
                "fact_truth": {v: k for k, v in TRUTH_TO_SUPPORT.items()}[
                    visible_e_status(bundle)
                ],
                "probability": FrozenFrequencyPredictor(bank).predict(bundle).value,
            }
        rows.append(
            {
                "call_id": call_id,
                "input_tokens": len(ids),
                "clock": request.get("clock", request.get("cutoff")),
                "messages_sha256": hashlib.sha256(
                    json.dumps(messages, sort_keys=True).encode()
                ).hexdigest(),
            }
        )
        publish(
            output / (call_id + ".json"),
            {
                "messages": messages,
                "input_tokens": len(ids),
                "engineering_response": answer,
            },
        )
        return json.dumps(answer, separators=(",", ":")), {
            "input_tokens": len(ids),
            "output_tokens": 20,
            "seconds": 0.001,
            "ended_with_eos": True,
        }

    program.execution_contract = {
        "model": "engineering_program_no_model",
        "weights": "none",
        "tokenizer": "frozen235b_tokenizer_only",
        "adapter": "context_size_program",
        "generation": {"actual_model_calls": 0},
        "runtime": {"timing": "declared1ms"},
    }
    report = run_session(data, bank, config, backend=program)
    publish(
        output / "REPORT.json",
        {
            "rows": rows,
            "max_input_tokens": max(r["input_tokens"] for r in rows),
            "max_selector_tokens": max(
                r["input_tokens"] for r in rows if r["call_id"].startswith("select-")
            ),
            "max_forecast_tokens": max(
                r["input_tokens"] for r in rows if r["call_id"].startswith("forecast-")
            ),
            "opportunities": len(report["snapshots"]),
            "actual_model_calls": 0,
            "scope": "One maximum-count legal program path; input sizing only, not a model or forecast score.",
        },
    )
    print(
        json.dumps(
            {
                "maximum": max(r["input_tokens"] for r in rows),
                "processor_callbacks": len(rows),
                "actual_model_calls": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
