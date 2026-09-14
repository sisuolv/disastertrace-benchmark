"""Re-tokenize preserved full-day requests after explicit selector role disclosure."""

import copy
import hashlib
import json
from pathlib import Path

from disastertrace.monitoring_v1.selection import SELECTOR_SYSTEM
from transformers import AutoTokenizer

HERE = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def main():
    original = HERE / "gpu/adaptive_context_preflight_02"
    out = HERE / "gpu/adaptive_context_preflight_03"
    out.mkdir(exist_ok=False)
    plan = read(HERE / "gpu/adaptive_large_02/PLAN.json")
    tokenizer = AutoTokenizer.from_pretrained(
        plan["model"]["directory"], local_files_only=True
    )
    prior = read(original / "REPORT.json")
    rows, program_variants = [], []

    def measure(messages):
        return len(
            tokenizer.apply_chat_template(
                messages,
                tokenize=True,
                add_generation_prompt=True,
                enable_thinking=False,
            )
        )

    for old in prior["rows"]:
        path = original / (old["call_id"] + ".json")
        messages = read(path)["messages"]
        assert (
            hashlib.sha256(json.dumps(messages, sort_keys=True).encode()).hexdigest()
            == old["messages_sha256"]
        )
        messages = copy.deepcopy(messages)
        if old["call_id"].startswith("select-"):
            request = json.loads(messages[1]["content"])
            request.update(forecast_executor_kind="llm", forecast_model_call_cost=1)
            messages[0]["content"] = SELECTOR_SYSTEM
            messages[1]["content"] = json.dumps(
                request, sort_keys=True, separators=(",", ":")
            )
            program = copy.deepcopy(messages)
            request.update(forecast_executor_kind="program", forecast_model_call_cost=0)
            request["forecast_call_upper"] = {
                "requests": 0,
                "bytes": 0,
                "tokens": 0,
                "compute_ms": 1,
            }
            program[1]["content"] = json.dumps(
                request, sort_keys=True, separators=(",", ":")
            )
            program_variants.append(
                {"call_id": old["call_id"], "input_tokens": measure(program)}
            )
            save(
                out / (old["call_id"] + ".program.json"),
                {"messages": program, "sizing_only": True},
            )
        tokens = measure(messages)
        if old["call_id"].startswith("forecast-"):
            assert tokens == old["input_tokens"]
        rows.append(
            {
                "call_id": old["call_id"],
                "input_tokens": tokens,
                "original_sha256": sha(path),
            }
        )
        save(
            out / (old["call_id"] + ".json"),
            {"messages": messages, "input_tokens": tokens, "sizing_only": True},
        )
    maximum = max(r["input_tokens"] for r in rows + program_variants)
    assert len(rows) == 240 and len(program_variants) == 24
    assert maximum <= plan["input_token_cap"]
    save(
        out / "REPORT.json",
        {
            "passed": True,
            "rows": rows,
            "program_selector_variants": program_variants,
            "max_input_tokens": maximum,
            "opportunities": prior["opportunities"],
            "actual_model_calls": 0,
            "original_report_sha256": sha(original / "REPORT.json"),
            "current_plan_sha256": sha(HERE / "gpu/adaptive_large_02/PLAN.json"),
            "scope": "Re-tokenization of all240 preserved requests from one full-day engineering trajectory after selector-role disclosure, plus24 program-role selector shape variants. No controller rerun; inherited resource-state fields are for sizing only. Not exhaustive policy-branch sizing; actual requests are independently checked before generation.",
        },
    )
    print(
        json.dumps(
            {
                "max_input_tokens": maximum,
                "requests": len(rows),
                "program_selector_variants": len(program_variants),
                "actual_model_calls": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
