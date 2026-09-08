"""Compare saved program-control prompts; these are not actual model exposures."""

import argparse
from collections import Counter
from pathlib import Path
from statistics import mean

from disastertrace.forecast_task.common import digest, fingerprint, read, write

PROJECT = Path(__file__).resolve().parents[2]
POLICIES = ("latest_explicit", "invalid_even", "missing_even")


def load_rows(run):
    rows, inputs = {}, {}
    for intent_path in sorted(run.glob("worker-*/batches/*/intent.json")):
        intent = read(intent_path)
        if intent["mode"] != "diagnostic":
            raise ValueError("only program diagnostics are allowed")
        inputs[intent_path.relative_to(PROJECT).as_posix()] = digest(intent_path)
        for item in intent["prepared"]:
            if item["slot_id"] in rows:
                raise ValueError("duplicate diagnostic slot")
            rows[item["slot_id"]] = item
    if len(rows) != 2412:
        raise ValueError("complete 2412-slot program control required")
    return rows, inputs


def compare():
    records, inputs, profiles = [], {}, {}
    for profile, role_phase in (("deepseek_r1", "p13"), ("qwen3", "p14")):
        profiles[profile] = {}
        for policy in POLICIES:
            system, left_inputs = load_rows(PROJECT / f"work/p12-compact-{profile}-diagnostics-v1" / policy)
            user, right_inputs = load_rows(PROJECT / f"work/{role_phase}-role-{profile}-diagnostics-v1" / policy)
            if set(system) != set(user):
                raise ValueError("program controls have different slots")
            inputs.update(left_inputs)
            inputs.update(right_inputs)
            differences, equal_prompt_bytes, equal_token_ids = [], 0, 0
            for slot_id in sorted(system):
                left, right = system[slot_id], user[slot_id]
                if left["messages"] != right["messages"] or left["sampling"] != right["sampling"]:
                    raise ValueError("logical message or sampling difference")
                expected = [{"role": "user", "content": left["messages"][0]["content"]
                             + "\n\n" + left["messages"][1]["content"]}]
                if (right["rendered_messages"] != expected
                        or right["rendered_messages_sha256"] != fingerprint(expected)):
                    raise ValueError("rendered messages differ from registered concatenation")
                if left["attempt_id"] == right["attempt_id"]:
                    raise ValueError("the controls must use distinct attempt identities")
                delta = len(right["prompt_token_ids"]) - len(left["prompt_token_ids"])
                differences.append(delta)
                equal_prompt_bytes += left["prompt"] == right["prompt"]
                equal_token_ids += left["prompt_token_ids"] == right["prompt_token_ids"]
                records.append({"profile": profile, "policy": policy, "slot_id": slot_id,
                                "system_prompt_tokens": len(left["prompt_token_ids"]),
                                "user_prompt_tokens": len(right["prompt_token_ids"]),
                                "token_count_delta": delta})
            profiles[profile][policy] = {
                "paired_slots": len(system), "logical_messages_identical": True,
                "sampling_identical": True, "equal_prompt_bytes": equal_prompt_bytes,
                "equal_prompt_token_ids": equal_token_ids,
                "user_minus_system_token_counts": {str(k): v for k, v in sorted(Counter(differences).items())},
                "mean_token_count_delta": mean(differences),
            }
    result = {
        "schema_version": "program_role_prompt_comparison_v1", "profiles": profiles,
        "paired_program_prompts": len(records), "records": records,
        "input_files_sha256": inputs, "script_sha256": digest(__file__),
        "program_histories_not_model_exposures": True, "actual_model_calls": 0,
        "inference_limit": "Logical task content is equal in program controls. Live tracks use their own histories; role placement changes chat serialization and may change token count.",
    }
    result["analysis_id"] = fingerprint(result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    result = compare()
    if args.verify:
        if result != read(args.output):
            raise ValueError("program prompt comparison differs")
    else:
        write(args.output, result)
    print({k: v for k, v in result.items() if k not in {"records", "input_files_sha256"}}, flush=True)
