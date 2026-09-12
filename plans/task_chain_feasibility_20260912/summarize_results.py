"""Summarize retained downloads and descriptive scores without network access."""

import argparse
import csv
import hashlib
import json
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def aggregate(scores, outcomes):
    groups = defaultdict(list)
    for score in scores:
        groups[outcomes[score["target_id"]]["family"], score["method"]].append(score)
    result = []
    for (family, method), records in sorted(groups.items()):
        entry = {"family": family, "method": method, "opportunities": len(records)}
        if "absolute_error" in records[0]:
            values = [
                r["absolute_error"] for r in records if r["absolute_error"] is not None
            ]
            entry.update(
                settled=len(values),
                unit=records[0]["unit"],
                mae=statistics.fmean(values) if values else None,
            )
        else:
            values = [r for r in records if r["correct"] is not None]
            entry.update(
                settled=len(values),
                correct=sum(r["correct"] for r in values),
                true_positive=sum(
                    r["predicted_below_1000m"] and r["actual_below_1000m"]
                    for r in values
                ),
                false_negative=sum(
                    not r["predicted_below_1000m"] and r["actual_below_1000m"]
                    for r in values
                ),
                false_positive=sum(
                    r["predicted_below_1000m"] and not r["actual_below_1000m"]
                    for r in values
                ),
                true_negative=sum(
                    not r["predicted_below_1000m"] and not r["actual_below_1000m"]
                    for r in values
                ),
            )
        result.append(entry)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Preserve the previous summary")

    receipts, batches = [], []
    for path in sorted(ROOT.glob("captures_*/MANIFEST.json")):
        batch = json.loads(path.read_text())
        if batch["requests"] != len(batch["rows"]):
            raise ValueError("Manifest count mismatch")
        for row in batch["rows"]:
            body = path.parent / row["body_file"]
            raw = body.read_bytes() if body.exists() else b""
            if (
                len(raw) != row["bytes"]
                or hashlib.sha256(raw).hexdigest() != row["sha256"]
            ):
                raise ValueError("Capture bytes changed: " + row["id"])
            receipts.append(row)
        batches.append(
            {
                "directory": path.parent.name,
                "requests": batch["requests"],
                "bytes": batch["bytes"],
            }
        )

    def complete(row):
        return row["http_status"] in (200, 206) and row["curl_exit"] == 0

    outcomes = {
        r["target_id"]: r for r in read_jsonl(args.data / "private/outcomes.jsonl")
    }
    checkpoints = read_jsonl(args.data / "public/checkpoints.jsonl")
    scores = read_jsonl(args.data / "baselines.jsonl")
    final = {}
    for row in checkpoints:
        old = final.get(row["target_id"])
        if old is None or old["clock"] < row["clock"]:
            final[row["target_id"]] = row
    final_ids = {r["checkpoint_id"] for r in final.values()}
    last_scores = [r for r in scores if r["checkpoint_id"] in final_ids]

    path = ROOT / "captures_03/metar-serial-egkk.body"
    native_low, rounded_low, exact_boundary, discrepancies = 0, 0, 0, []
    records = list(csv.DictReader(path.read_text().splitlines()))
    for line, row in enumerate(records, 2):
        text = row["metar"].split(" RMK ")[0].split(" TEMPO ")[0]
        match = re.search(
            r"(?:KT|MPS)\s+(?:\d{3}V\d{3}\s+)?(\d{4})(?:NDV)?(?:\s|$)", text
        )
        if not match:
            raise ValueError("Unexpected UK visibility encoding in the fixed sample")
        raw_value = int(match[1])
        is_low = raw_value < 1000
        rounded_is_low = float(row["vsby"]) * 1609.344 < 1000
        native_low += is_low
        rounded_low += rounded_is_low
        exact_boundary += raw_value == 1000
        if is_low != rounded_is_low:
            discrepancies.append(
                {
                    "source_line": line,
                    "time": row["valid"],
                    "raw_token_m": raw_value,
                    "rounded_miles": row["vsby"],
                    "raw_metar": row["metar"],
                }
            )

    result = {
        "schema": "disastertrace.task_chain_metrics.v1",
        "data_directory": str(args.data),
        "acquisition": {
            "batches": batches,
            "requests": len(receipts),
            "stored_body_bytes": sum(r["bytes"] for r in receipts),
            "complete_http_responses": sum(complete(r) for r in receipts),
            "complete_response_bytes": sum(r["bytes"] for r in receipts if complete(r)),
            "http_and_curl": [
                {"http": http, "curl_exit": curl_exit, "count": count}
                for (http, curl_exit), count in sorted(
                    Counter(
                        (r["http_status"], r["curl_exit"]) for r in receipts
                    ).items()
                )
            ],
            "failures": [
                {k: r[k] for k in ("id", "http_status", "curl_exit", "bytes")}
                for r in receipts
                if not complete(r)
            ],
            "first_started_at": min(r["started_at"] for r in receipts),
            "last_finished_at": max(r["finished_at"] for r in receipts),
            "transport_success_is_not_scientific_admission": True,
        },
        "all_checkpoint_descriptive_scores": aggregate(scores, outcomes),
        "last_checkpoint_descriptive_scores": aggregate(last_scores, outcomes),
        "exact_visibility_positive_targets": [
            r for r in outcomes.values() if r.get("below_1000m") is True
        ],
        "uk_native_rounding_diagnostic": {
            "source": str(path),
            "records": len(records),
            "native_below_1000m": native_low,
            "rounded_mile_column_below_1000m": rounded_low,
            "native_exactly_1000m": exact_boundary,
            "discrepancies": discrepancies,
        },
        "limits": [
            "Repeated checkpoints and shared weather processes are correlated.",
            "Point comparisons are descriptive, not event-level model rankings.",
            "No new LLM, GPU, acquisition-policy or real-arrival experiment.",
        ],
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "requests": len(receipts),
                "raw_bytes_checked": True,
                "uk_native_low": native_low,
            }
        )
    )


if __name__ == "__main__":
    main()
