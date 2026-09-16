"""Replay every received final token on CPU; never generate or repair answers."""

import argparse
from collections import Counter
from pathlib import Path

from disastertrace.constrained_eval import contract
from disastertrace.constrained_eval.execution import backend_inventory
from disastertrace.constrained_eval.grammar import GrammarReplay
from disastertrace.local_eval.storage import read, seal, write

from . import audit, package


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execution", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    audited = audit.reconstruct(args.execution, args.run, require_model=True)
    plan = audited["plan"]
    if backend_inventory() != audited["summary"]["runtime"]["observation"]["backend_files"]:
        raise ValueError("installed grammar differs from model runtime")
    tokenizer = package.tokenizer(args.execution, plan)
    vocab = read(args.execution / "parent/model_config/config.json")["vocab_size"]
    grammar = GrammarReplay(tokenizer, vocab)
    counts, rows = Counter(), []
    for path in sorted((args.run / "raw").glob("*.json")):
        for raw in read(path)["results"]:
            value = grammar.check_output(raw["output_token_ids"])
            rows.append({"attempt_id": raw["attempt_id"], "grammar": value})
            counts.update(
                sequences=1,
                reasoning_only=int(value["accepted"] is None),
                constraint_violations=int(value["accepted"] is False),
                terminated=int(value.get("terminated", False)),
                constrained_tokens_checked=value.get("checked", 0),
            )
    result = {
        "schema_version": "p6_actual_grammar_replay_v1",
        "execution_id": plan["execution_id"],
        "audit_id": audited["summary"]["audit_id"],
        "constraint": contract.identity(),
        "counts": dict(counts),
        "planned_slots": len(audited["slots"]),
        "additional_model_calls": 0,
        "mask_replay_is_not_model_sampling": True,
        "status": "passed" if counts["constraint_violations"] == 0 else "failed",
    }
    args.output.mkdir(parents=True, exist_ok=False)
    write(args.output / "rows.json", rows)
    write(args.output / "report.json", result)
    seal(args.output)
    print(result, flush=True)
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
