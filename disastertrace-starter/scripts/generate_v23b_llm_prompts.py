#!/usr/bin/env python3
"""Generate frozen, source-only prompts for the v23-B local LLM runs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

YEAR_MONTH = re.compile(r"20\d{2}[-/](?:0[1-9]|1[0-2])(?:\b|$)")


def _age_minutes(available_at_us: int, cutoff_us: int) -> float:
    return max(0.0, (cutoff_us - available_at_us) / 60_000_000)


def _prompt(row: dict) -> str:
    lead_minutes = int(round(row["lead_hours"] * 60))
    target_start = row["physical_start_us"]
    taf = row.get("taf") or {}
    metars = [item for item in row.get("recent_metars", []) if item["observation_time_us"] < target_start]
    lines = [
        "Return exactly one JSON object with one key: {\"p\": number}.",
        "The number p must be between 0 and 1 and is your probability of the event.",
        f"Station ICAO: {row['station']}",
        f"Lead: {lead_minutes} minutes",
        f"Target window: from now in {lead_minutes} minutes, for the next 60 minutes.",
        "Event: the unique routine METAR visibility during that target hour is below 5000 m.",
        "Current authoritative TAF available at cutoff (verbatim):",
        taf.get("raw") or "<none>",
        "At most three METAR/SPECI reports visible at cutoff (verbatim, newest first):",
    ]
    if not metars:
        lines.append("<none>")
    else:
        for item in metars[:3]:
            age = _age_minutes(item["available_at_us"], row["cutoff_us"])
            lines.append(f"age_minutes={age:.3f} report_type={item['report_type']} raw={item['raw']}")
    return "\n".join(lines)


def build(input_path: Path, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    m1 = out_dir / "m1_prompts.jsonl"
    m2 = out_dir / "m2_prompts.jsonl"
    n1 = n2 = 0
    violations = []
    with input_path.open() as source, m1.open("w") as first, m2.open("w") as second:
        for line_no, line in enumerate(source, 1):
            row = json.loads(line)
            if not row.get("source_only") or row.get("features_do_not_include_outcome") is not True:
                raise ValueError(f"row {line_no} is not source-only")
            prompt = _prompt(row)
            for item in row.get("recent_metars", []):
                if item["available_at_us"] > row["cutoff_us"] or item["observation_time_us"] >= row["physical_start_us"]:
                    violations.append({"line": line_no, "target_id": row["target_id"], "kind": "future_or_late_metar"})
            if YEAR_MONTH.search(prompt):
                violations.append({"line": line_no, "target_id": row["target_id"], "kind": "year_month_leak"})
            record = {"target_id": row["target_id"], "checkpoint_id": row["checkpoint_id"], "cutoff_us": row["cutoff_us"], "prompt": prompt}
            first.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
            n1 += 1
            digest = int(hashlib.sha256(row["target_id"].encode()).hexdigest(), 16)
            if digest % 4 == 0:
                second.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
                n2 += 1
    if violations:
        (out_dir / "LEAKAGE_VIOLATIONS.json").write_text(json.dumps(violations, indent=2) + "\n")
        raise RuntimeError(f"prompt leakage assertions failed: {len(violations)}")
    result = {
        "m1_count": n1,
        "m2_count": n2,
        "m2_rule": "int(sha256(target_id),16) % 4 == 0",
        "m1_sha256": hashlib.sha256(m1.read_bytes()).hexdigest(),
        "m2_sha256": hashlib.sha256(m2.read_bytes()).hexdigest(),
        "leakage_assertions": "PASS",
        "outcome_fields_read": False,
    }
    (out_dir / "PROMPT_MANIFEST.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.input, args.out_dir), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
