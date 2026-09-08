"""CPU XGrammar replay of all saved model final tokens; no model/weight loading."""

import argparse
from collections import Counter
import os
from pathlib import Path

from disastertrace.qwen_role_live import package
from disastertrace.qwen_role_live.grammar import GrammarReplay
from disastertrace.qwen_role_live.storage import write
from disastertrace.forecast_task.common import fingerprint, read


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execution", required=True, type=Path)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "":
        raise ValueError("token replay requires CUDA hidden")
    plan, _, slots = package.verify(args.execution, code=True)
    allowed = {s["attempt_id"] for s in slots}
    tokenizer = package.tokenizer_for(args.execution)
    grammar = GrammarReplay(tokenizer, read(args.execution / "resources/tokenizer/config.json")["vocab_size"])
    seen, results, unique = set(), [], {}
    for path in sorted(args.run_root.glob("worker-*/batches/*/raw.json")):
        for item in read(path)["results"]:
            identity = item["attempt_id"]
            if identity not in allowed or identity in seen or len(item["candidates"]) != 1:
                raise ValueError("unexpected attempt during token replay")
            seen.add(identity)
            ids = item["candidates"][0]["output_token_ids"]
            key = fingerprint(ids)
            if key not in unique:
                unique[key] = grammar.check_output(ids)
            result = unique[key]
            results.append({"attempt_id": identity, "tokens_sha256": key, **result})
    failures = [r for r in results if r["accepted"] is False]
    record = {"status": "passed" if not failures else "failed", "execution_id": plan["execution_id"],
              "planned": len(slots), "captured": len(seen), "missing": len(slots) - len(seen),
              "unique_sequences": len(unique), "constrained_tokens": sum(r["constrained_tokens"] for r in results),
              "phases": dict(Counter(r["phase"] for r in results)), "violations": len(failures),
              "model_calls": 0, "records": results}
    write(args.output, record)
    print({k: v for k, v in record.items() if k != "records"}, flush=True)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
