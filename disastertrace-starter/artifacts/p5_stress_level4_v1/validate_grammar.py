"""Replay every actual P5 final token against frozen XGrammar without inference."""

import argparse
from collections import Counter
from pathlib import Path

from disastertrace.constrained_eval import adapter, contract
from disastertrace.constrained_eval.grammar import GrammarReplay
from disastertrace.local_eval.storage import read, seal, write
from disastertrace.stress_eval import audit, execution, runtime


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execution", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan, _, slots = execution.verify(args.execution)
    if execution.backend_inventory() != plan["backend_files"]:
        raise ValueError("installed XGrammar/backend differs from frozen source")
    _, _, _, summary, _, captures = audit.audit(args.execution, args.run, require_model=True)
    tokenizer = runtime.tokenizer_for(args.execution)
    vocab = read(args.execution / "model_config/config.json")["vocab_size"]
    grammar = GrammarReplay(tokenizer, vocab)
    counts, rows = Counter(), []
    for capture in captures:
        result = grammar.check_output(capture["result"]["output_token_ids"])
        rows.append({"slot_index": capture["slot_index"], "grammar": result})
        counts.update(
            sequences=1,
            reasoning_only=int(result["accepted"] is None),
            constraint_violations=int(result["accepted"] is False),
            terminated=int(result.get("terminated", False)),
            constrained_tokens_checked=result.get("checked", 0),
        )
    args.output.mkdir(parents=True, exist_ok=False)
    result = {
        "schema_version": "p5_actual_grammar_replay_v1",
        "execution_id": plan["execution_id"],
        "audit_id": summary["audit_id"],
        "origin": summary["origin"],
        "constraint": contract.identity(),
        "backend_files": plan["backend_files"],
        "grammar_stop_token_ids": grammar.info.stop_token_ids,
        "model_eos_token_ids": sorted(adapter.terminal_ids(tokenizer)),
        "counts": dict(counts),
        "planned_slots": len(slots),
        "additional_model_calls": 0,
        "mask_replay_is_not_model_sampling": True,
        "status": "passed" if counts["constraint_violations"] == 0 else "failed",
    }
    write(args.output / "rows.json", rows)
    write(args.output / "report.json", result)
    seal(args.output)
    print(result)
    if result["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
