"""Exercise production C2 support on native daily-product disclosure subsets."""

import datetime as dt
import hashlib
import itertools
import json
import math
from collections import Counter
from pathlib import Path

from disastertrace.monitoring_v1.support import (
    EvidenceFact,
    Interval,
    classify,
    public_support,
)

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE / "temperature_daily_reference_01"


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def conjunction(statuses):
    if "inconsistent" in statuses:
        return "inconsistent"
    if "refuted" in statuses:
        return "refuted"
    if "undetermined" in statuses:
        return "undetermined"
    return "supported"


def main():
    output = ROOT / "production_support_01"
    output.mkdir(exist_ok=False)
    records = read(ROOT / "qualification_01/DAILY_REFERENCES.json")
    references = read(ROOT / "qualification_01/DURATION_CANDIDATES.json")
    native = {r["row_sha256"]: r for r in records}
    selected = read(ROOT / "SELECTED.json")["archive"]
    receipt = read(ROOT / (selected + ".receipt.json"))
    at = int(dt.datetime.fromisoformat(receipt["completed_at"]).timestamp() * 1_000_000)
    rows, counts = [], Counter()
    hidden_checks, current_full_checks = 0, 0
    for target in references:
        operator, threshold = (
            ("ge", 30)
            if target["candidate"] == "fixed_threshold_hot_spell_3d"
            else ("lt", 0)
        )
        days = [native[key] for key in target["daily_row_sha256"]]
        for mask in itertools.product((False, True), repeat=3):
            facts, hidden = [], []
            for disclosed, day in zip(mask, days):
                value = day["values_C"]["TXK"]
                interval = (
                    Interval(-math.inf, math.inf)
                    if value is None
                    else Interval(value, value)
                )
                fields = dict(
                    series_id="DWD-00460-TXK-" + day["date"],
                    version=1,
                    released_at=at,
                    field=day["date"],
                    units="C",
                    interval=interval,
                    support_rule_version="dwd_daily_product_exact_v1",
                )
                if disclosed:
                    facts.append(
                        EvidenceFact(
                            **fields,
                            reference_kind="product_label",
                            support_assumption="product_exact",
                            visible_information_scope="policy",
                        )
                    )
                else:
                    hidden.append(
                        EvidenceFact(
                            **fields,
                            reference_kind="evaluator_label",
                            support_assumption="annotation_reference",
                            visible_information_scope="evaluator",
                        )
                    )
            statuses, contaminated = [], []
            for day in days:
                domain = Interval(-math.inf, math.inf)
                statuses.append(
                    classify(
                        public_support(facts, day["date"], "C", domain, at),
                        operator,
                        threshold,
                    )
                )
                contaminated.append(
                    classify(
                        public_support(facts + hidden, day["date"], "C", domain, at),
                        operator,
                        threshold,
                    )
                )
            if statuses != contaminated:
                raise ValueError(
                    "Evaluator-only daily references leaked into public C2 support"
                )
            hidden_checks += 1
            observed = conjunction(statuses)
            raw_states = [
                None
                if not disclosed or day["values_C"]["TXK"] is None
                else day["values_C"]["TXK"] >= threshold
                if operator == "ge"
                else day["values_C"]["TXK"] < threshold
                for disclosed, day in zip(mask, days)
            ]
            expected = (
                "refuted"
                if False in raw_states
                else "undetermined"
                if None in raw_states
                else "supported"
            )
            if observed != expected:
                raise ValueError(
                    "Production interval support disagrees with native-row Boolean reference"
                )
            if all(mask):
                if observed != target["product_reference_state"]:
                    raise ValueError(
                        "Full native-product support differs from independent duration reference"
                    )
                current_full_checks += 1
            counts[(target["candidate"], sum(mask), observed)] += 1
            rows.append(
                {
                    "candidate": target["candidate"],
                    "physical_start": target["physical_start"],
                    "disclosed_dates": [d["date"] for bit, d in zip(mask, days) if bit],
                    "observed_at": at,
                    "production_E_state": observed,
                    "hidden_reference_ignored": True,
                    "day_reference_hashes": target["daily_row_sha256"],
                }
            )
    if len(rows) != 1456 * 8 or current_full_checks != 1456:
        raise ValueError("Lost registered window or disclosure subset")
    summary = {
        "passed": True,
        "native_days": 730,
        "overlapping_duration_windows_per_candidate": 728,
        "candidates": 2,
        "disclosure_subsets_per_window": 8,
        "production_support_states": len(rows),
        "full_product_references_matched": current_full_checks,
        "hidden_evaluator_reference_checks": hidden_checks,
        "state_counts": [
            {"candidate": k[0], "disclosed_days": k[1], "state": k[2], "count": v}
            for k, v in sorted(counts.items())
        ],
        "source_hashes": {
            "daily_reference": sha(ROOT / "qualification_01/DAILY_REFERENCES.json"),
            "duration_reference": sha(
                ROOT / "qualification_01/DURATION_CANDIDATES.json"
            ),
            "script": sha(Path(__file__)),
        },
        "new_model_calls": 0,
        "new_source_requests": 0,
        "session_coordinator_replays": 0,
        "historical_availability_proved": False,
        "C1_acquisition_gain": None,
        "scope": "Real native values through existing EvidenceFact/public_support/classify under explicitly controlled input subsets; outcome/reference-semantic qualification only.",
        "limits": [
            "Observed-at is the actual2026 collector receipt. It is not a claim that this archive edition was available during2017-2018.",
            "Subset masks are diagnostic interventions. The downloaded archive exposes all days together; no artificial per-day query charge or C1 gain is claimed.",
            "Registered windows overlap and use exposed development data; neither state count nor positive-window count is an independent-process count.",
            "This validates product E support, not an end-to-end adaptive temperature session, daily F, model skill or complete heatwave/cold-wave admission.",
        ],
    }
    for name, value in (("SUPPORT_STATES.json", rows), ("VALIDATION.json", summary)):
        with (output / name).open("x") as handle:
            json.dump(value, handle, indent=2, allow_nan=False)
            handle.write("\n")
    (output / "EXECUTED_SOURCE.py").write_bytes(Path(__file__).read_bytes())
    print(
        json.dumps(
            {
                k: summary[k]
                for k in (
                    "passed",
                    "production_support_states",
                    "full_product_references_matched",
                    "hidden_evaluator_reference_checks",
                    "new_model_calls",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
