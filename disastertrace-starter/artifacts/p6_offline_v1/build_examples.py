"""Select the first real example per error class using a declared, deterministic ordering."""

import argparse
from pathlib import Path

from disastertrace.automated.common import canonical, fingerprint, read_jsonl
from disastertrace.local_eval.storage import read, seal, verify_seal, write
from disastertrace.post_p5.report import FACTORS, load_run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    project = root.parents[1]
    baseline = read(root / "baseline/repo_baseline.json")
    verify_seal(root / "posthoc_final")
    fields = read_jsonl(root / "posthoc_final/field_diagnostics.jsonl")
    order = ("factor", "method", "base_episode_id", "checkpoint_id", "field")
    selected = {}
    for field in sorted(fields, key=lambda row: tuple(row[key] for key in order)):
        if field["primary_error"] is not None:
            selected.setdefault(field["primary_error"], field)
    runs = {factor: load_run(project, factor, baseline) for factor in FACTORS}
    examples, provenance = [], []
    for field in fields:
        plan, _, rows = runs[field["factor"]]
        row = rows[field["base_episode_id"], field["method"], field["checkpoint_id"]]
        provenance.append(
            {
                **{k: field[k] for k in order},
                "source_commit": baseline["head"],
                "execution_id": plan["execution_id"],
                "audit_id": baseline["reports"][field["factor"]]["audit_id"],
                "root_id": row["episode"]["root_id"],
                "model_id": plan["settings"]["model_id"],
                "repeat_label": "legacy_single_run",
                "sampling_seed": row["prepared"]["sampling"]["seed"],
                "prompt_token_sha256": fingerprint(row["prepared"]["prompt_token_ids"]),
                "prompt_tokens": row["capture"]["prompt_tokens"],
                "capture_file_sha256": row["capture_file_sha256"],
            }
        )
    for label, field in sorted(selected.items()):
        row = runs[field["factor"]][2][
            field["base_episode_id"], field["method"], field["checkpoint_id"]
        ]
        wanted = {
            r["record_id"] for r in field["expected"]["evidence"] + field["submitted"]["evidence"]
        }
        examples.append(
            {
                "primary_error": label,
                "identity": {k: field[k] for k in order},
                "request_sha256": fingerprint(row["request"]),
                "raw_model_answer": row["capture"]["extracted"]["content"],
                "submitted_field": field["submitted"],
                "expected_field": field["expected"],
                "citation_details": field["citation_details"],
                "public_evidence_excerpts": [
                    r for r in row["request"]["evidence"] if r["record_id"] in wanted
                ],
                "capture_file_sha256": row["capture_file_sha256"],
                "interpretation": "Observed mismatch; no claim about the model's internal cause.",
            }
        )
    args.output.mkdir(parents=True, exist_ok=False)
    for name, rows in (("examples", examples), ("field_provenance", provenance)):
        with (args.output / (name + ".jsonl")).open("x") as stream:
            for row in rows:
                stream.write(canonical(row) + "\n")
    result = {
        "status": "passed",
        "selection_order": list(order),
        "policy": "first_actual_error_per_primary_class",
        "examples": len(examples),
        "provenance_rows": len(provenance),
        "additional_model_calls": 0,
        "human_selected_examples": False,
    }
    write(args.output / "selection.json", result)
    lines = [
        "# Deterministically selected P5 error examples",
        "",
        "First actual row in each error class, sorted by factor, method, base episode, checkpoint, field.",
        "",
    ]
    for example in examples:
        lines.extend(
            [
                "## " + example["primary_error"],
                "",
                "```json",
                canonical(example["identity"]),
                "```",
                "",
                "Submitted field:",
                "```json",
                canonical(example["submitted_field"]),
                "```",
                "",
                "Expected current field:",
                "```json",
                canonical(example["expected_field"]),
                "```",
                "",
            ]
        )
    (args.output / "EXAMPLES.md").write_text("\n".join(lines))
    seal(args.output)
    print(result, flush=True)


if __name__ == "__main__":
    main()
