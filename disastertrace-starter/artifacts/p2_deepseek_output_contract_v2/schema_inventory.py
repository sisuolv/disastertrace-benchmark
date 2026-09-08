"""Describe schema failures without repairing or rescoring any captured answer."""

import argparse
import json
from collections import Counter
from pathlib import Path

import runner


def inventory(audit):
    from disastertrace.controlled.schema import parse_decision

    failures = []
    for row in audit["records"]:
        if row["status"] != "invalid":
            continue
        raw = row["raw_response"]
        detail = {
            "slot_index": row["slot_index"],
            **{
                key: row["slot"][key] for key in ("method", "episode_id", "family", "checkpoint_id")
            },
            "finish_reason": row["completion"]["metadata"]["finish_reason"],
            "completion_tokens": row["completion"]["metadata"]["usage"]["completion_tokens"],
            "raw_response_bytes": len(raw.encode()),
            "empty_content": not bool(raw),
            "starts_with_code_fence": raw.lstrip().startswith("```"),
            "original_score_changed": False,
        }
        try:
            parse_decision(raw)
        except (ValueError, TypeError, KeyError, RecursionError) as exc:
            detail["parser_error_type"] = type(exc).__name__
            detail["parser_error"] = str(exc)[:200]
        else:
            raise ValueError("audited schema failure unexpectedly accepted")
        try:
            value = json.loads(raw)
        except (ValueError, TypeError, RecursionError):
            detail["json_decodes"] = False
        else:
            detail["json_decodes"] = True
            detail["root_type"] = type(value).__name__
            if isinstance(value, dict):
                detail["root_keys"] = sorted(value)
                detail["missing_root_keys"] = sorted({"state", "action"} - value.keys())
                detail["extra_root_keys"] = sorted(value.keys() - {"state", "action"})
                detail["action_present"] = "action" in value
                detail["action_type"] = type(value.get("action")).__name__
        failures.append(detail)
    return {
        "schema_version": "p2_captured_schema_inventory_v1",
        "execution_id": audit["execution_id"],
        "audit_id": audit["audit_id"],
        "mode": audit["mode"],
        "schema_invalid": len(failures),
        "parser_error_counts": dict(Counter(row["parser_error"] for row in failures)),
        "failures": failures,
        "additional_model_calls": 0,
        "repaired_answers": 0,
        "score_changes": 0,
        "interpretation": (
            "JSON decoding is descriptive only; the frozen strict parser determines acceptance. "
            "Structural errors are not automatically output-length failures."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    runner.verify()
    _, _, reporter, _ = runner.frozen_modules()
    reporter.verify_report(runner.HERE / "execution", args.run, args.report)
    audit = runner.read(args.report / "audit.json")
    if (audit["mode"] != "model_http") != args.diagnostic:
        raise ValueError("schema inventory origin mismatch")
    result = inventory(audit)
    result["analysis_script_sha256"] = runner.sha(Path(__file__))
    if args.verify:
        if runner.read(args.output) != result:
            raise ValueError("schema inventory differs from captured reconstruction")
    else:
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "status": "verified" if args.verify else "generated",
                "schema_invalid": result["schema_invalid"],
                "additional_model_calls": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
