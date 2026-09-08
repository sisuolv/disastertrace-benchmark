"""Validate all predefined program controls or actual captured tokens without inference."""

import argparse
from collections import Counter
from pathlib import Path

from disastertrace.automated.common import fingerprint, strict_json
from disastertrace.constrained_eval import adapter, audit, contract, execution, runtime
from disastertrace.constrained_eval.grammar import GrammarReplay
from disastertrace.controlled import compiler, public_oracle
from disastertrace.controlled import runtime as program_runtime
from disastertrace.controlled.schema import METHODS
from disastertrace.local_eval.storage import read, seal, write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execution", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run", type=Path)
    args = parser.parse_args()
    plan, episodes, slots = execution.verify(args.execution)
    if execution.backend_inventory() != plan["backend_files"]:
        raise ValueError("installed backend differs from frozen source")
    tokenizer = runtime.tokenizer_for(args.execution)
    vocab_size = read(args.execution / "model_config/config.json")["vocab_size"]
    grammar = GrammarReplay(tokenizer, vocab_size)
    rows, cache, counters = [], {}, Counter()
    args.output.mkdir(parents=True, exist_ok=False)

    def check(raw, labels):
        digest = fingerprint(raw)
        if digest not in cache:
            cache[digest] = grammar.check_text(raw)
        result = cache[digest]
        valid = contract.inspect(raw)
        expected = valid["structure_valid"]
        if result["accepted"] != expected or expected and not result["terminated"]:
            raise ValueError("program structure/mask compatibility failed: " + str(labels))
        rows.append({**labels, "raw_sha256": digest, "validity": valid, "grammar": result})
        counters["sequences"] += 1
        counters["accepted"] += int(result["accepted"])
        counters["rejected_expected"] += int(not result["accepted"])

    if args.run:
        _, _, _, summary, _, captures = audit.audit(args.execution, args.run)
        for capture in captures:
            result = grammar.check_output(capture["result"]["output_token_ids"])
            rows.append({"slot_index": capture["slot_index"], "grammar": result})
            counters["sequences"] += 1
            counters["reasoning_only"] += int(result["accepted"] is None)
            counters["constraint_violations"] += int(result["accepted"] is False)
            counters["terminated"] += int(result.get("terminated", False))
            counters["constrained_tokens_checked"] += result.get("checked", 0)
        binding = {"audit_id": summary["audit_id"], "origin": summary["origin"]}
        if counters["constraint_violations"]:
            raise ValueError("captured final tokens violate the frozen grammar")
    else:
        for ep in episodes:
            for cp in ep["checkpoints"]:
                check(
                    contract.serialize_fixture(compiler.reference_at(ep, cp["checkpoint_id"])),
                    {
                        "role": "gold",
                        "episode_id": ep["episode_id"],
                        "checkpoint_id": cp["checkpoint_id"],
                    },
                )
        for method in METHODS:
            for backend in (*public_oracle.backends, "invalid-control"):
                traces = program_runtime.rehearse(episodes, method, backend)
                for row in traces:
                    raw = row["raw_response"]
                    if raw:
                        raw = contract.serialize_fixture(strict_json(raw))
                    check(
                        raw,
                        {
                            "role": "control",
                            "method": method,
                            "backend": backend,
                            "episode_id": row["episode_id"],
                            "checkpoint_id": row["checkpoint_id"],
                        },
                    )
        binding = {"origin": "diagnostic_program_controls", "audit_id": None}
    report = {
        "schema_version": "constrained_grammar_acceptance_v1",
        "execution_id": plan["execution_id"],
        "constraint": contract.identity(),
        "backend_files": plan["backend_files"],
        "tokenizer_vocab_size": vocab_size,
        "grammar_stop_token_ids": grammar.info.stop_token_ids,
        "model_eos_token_ids": sorted(adapter.terminal_ids(tokenizer)),
        "counts": dict(counters),
        "unique_texts_checked": len(cache),
        "unique_text_tokens_checked": sum(r["checked"] for r in cache.values()),
        "slots": len(slots),
        "additional_model_calls": 0,
        "mask_replay_is_not_model_sampling": True,
        **binding,
    }
    write(args.output / "rows.json", rows)
    write(args.output / "report.json", report)
    seal(args.output)
    print(report)


if __name__ == "__main__":
    main()
