"""Fixed-disclosure E diagnostic, separate from F or active-policy scoring."""

import json
import math
from dataclasses import asdict

from disastertrace.monitoring_v1.policies import parse_answer
from disastertrace.monitoring_v1.resources import BudgetLedger, Cost

E_SYSTEM = """Determine the truth status of the stated current-evidence proposition, using only the shown legally read report products. The proposition is EXISTS a registered neighbor slot whose native report visibility is strictly below the stated threshold. 'supported' means this proposition is definitely true; 'refuted' means it is definitely false; an unread/missing/straddling slot leaves 'undetermined' unless another read slot proves the proposition. Use 'inconsistent' only for conflicting certified facts. This is not a request to decide whether the data source is trustworthy or whether some unrelated forecast is supported. Return only JSON with exactly one key: {"e_status":"supported/refuted/undetermined/inconsistent"}. Select one status, not the slash-separated list."""
EXAMPLES = """ Examples of the logical rule: with two registered slots and threshold 1000m, one read report of 12000m and one unread slot gives undetermined; two read reports of 12000m give refuted; one read report of 400m proves supported even if the second slot is unread. These examples describe the rule, not the answer to your case."""


def parse_status(raw, condition):
    if condition == "joint_F_E":
        return parse_answer(raw)["e_status"]
    text = raw.strip()
    if text.startswith("```json\n") and text.endswith("```"):
        text = text[8:-3].strip()
    value = json.loads(text)
    if (
        not isinstance(value, dict)
        or set(value) != {"e_status"}
        or value["e_status"]
        not in {"supported", "refuted", "undetermined", "inconsistent"}
    ):
        raise ValueError("Invalid E-only response schema")
    return value["e_status"]


def run_session(data, bank, config, backend, journal, resource_journal):
    condition = config["condition"]
    ledger = BudgetLedger(
        {"tokens": config["token_cap"], "compute_ms": config["compute_ms_cap"]},
        journal=resource_journal,
    )
    calls = []
    for number, case in enumerate(data["cases"]):
        call_id = f"probe-{number:03d}"
        request = case["requests"][condition]
        journal.append(
            call_id + ":disclosure",
            {
                "case_id": case["case_id"],
                "condition": condition,
                "read_query_ids": case["read_query_ids"],
            },
        )
        ledger.reserve(
            call_id,
            Cost(
                tokens=config["input_token_cap"] + config["output_token_cap"],
                compute_ms=config["call_compute_cap_ms"],
            ),
            "fixed_diagnostic",
        )
        raw, details = backend(data["systems"][condition], request, call_id)
        try:
            status = parse_status(raw, condition)
            if not details["ended_with_eos"]:
                raise ValueError("Output did not terminate with EOS")
            error = None
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            status, error = None, str(exc)
        ledger.settle(
            call_id,
            Cost(
                tokens=details["input_tokens"] + details["output_tokens"],
                compute_ms=math.ceil(details["seconds"] * 1000),
            ),
            outcome="completed" if error is None else "invalid_response",
        )
        calls.append(
            {
                "call_id": call_id,
                "case_id": case["case_id"],
                "condition": condition,
                "raw": raw,
                "reported_e": status,
                "error": error,
                "details": details,
            }
        )
    return {
        "calls": calls,
        "actual_model_calls": len(calls),
        "resource_spent": asdict(ledger.spent),
        "resource_reserved": asdict(ledger.reserved),
        "resource_events": ledger.events,
        "interpretation": "Real fixed read-product cases, balanced on evaluator E status. No F outcomes or adaptive acquisition experiment; transform and rule examples are explicitly assisted diagnostics.",
    }
