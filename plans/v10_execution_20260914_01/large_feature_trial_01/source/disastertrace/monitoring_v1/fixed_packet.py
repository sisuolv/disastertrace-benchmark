"""Paired E/F responses for registered, identical-information packet studies."""

import math

from ..forecast_task.common import strict_json
from .audit_contracts import require_exact_ids
from .e_composition import TRUTHS, aggregate
from .targets import canonical_hash


def messages(view, reasoning):
    if reasoning not in {"direct", "slotwise"}:
        raise ValueError("Registered E/F response format required")
    system = (
        "Use only the disclosed frozen packet. E_question asks whether ANY registered PAST "
        "neighbor report slot has visibility strictly below threshold_m. A TAF is a forecast, "
        "not a neighbor observation. For each slot, unread, missing, or unresolved means unknown. "
        "A native report interval proves true only when every value is below the threshold; "
        "it proves false when every value is at least the threshold. Respect open endpoints "
        "and +inf. Parsed intervals describe product facts, not error-free physical weather. "
        "Use current versions. Aggregate ALL registered slots: conflict if any conflicts; "
        "otherwise true if any is true; otherwise false only if all are false; else unknown. "
        "fact_truth must be a JSON string: true, false, unknown, or conflict, never a boolean. "
        "Separately forecast the FUTURE native routine report target in target: probability "
        "must be a finite number from 0 to 1. Use the complete common TAF and disclosed past "
        "observations. The visible probability is a frozen prior-month research calibration, "
        "not an official TAF event probability or a known future answer; you may retain it. "
        "TEMPO is not a calibrated probability. Unknown E does not force probability 0.5; "
        "known E does not determine F. Do not retrieve external sources or use memorized "
        "weather outcomes. Times are UTC microseconds. Return only one JSON object, no prose. "
    )
    system += ("Use exactly fact_truth and probability." if reasoning == "direct" else
               "Use exactly slots, fact_truth, and probability. slots maps EVERY registered "
               "query_id exactly once to its truth string, including unknown for unread slots. "
               "fact_truth is their aggregate.")
    import json

    return [{"role": "system", "content": system},
            {"role": "user", "content": json.dumps(view, sort_keys=True, separators=(",", ":"), allow_nan=False)}]


def parse(raw, query_ids, acquired_ids, reasoning):
    if reasoning not in {"direct", "slotwise"}:
        raise ValueError("Unregistered response format")
    answer = strict_json(raw)
    fields = {"fact_truth", "probability"} | ({"slots"} if reasoning == "slotwise" else set())
    if not isinstance(answer, dict) or set(answer) != fields:
        raise ValueError("Invalid E/F fields")
    if type(answer["fact_truth"]) is not str or answer["fact_truth"] not in TRUTHS:
        raise ValueError("Invalid reported E truth")
    p = answer["probability"]
    if type(p) not in {float, int} or not math.isfinite(p) or not 0 <= p <= 1:
        raise ValueError("Invalid F probability")
    if reasoning == "slotwise":
        if not isinstance(answer["slots"], dict):
            raise ValueError("Slot mapping required")
        require_exact_ids(query_ids, answer["slots"], "E/F model slots")
        composed = aggregate(answer["slots"].values())
        if not set(acquired_ids) <= set(query_ids):
            raise ValueError("Unregistered evidence")
        # This is a separately reported grounding violation, not a schema repair.
        violations = [q for q in query_ids if q not in acquired_ids and answer["slots"][q] != "unknown"]
        answer = {**answer, "composed_aggregate": composed, "unread_slot_claims": violations}
    return answer


def information_id(view):
    content = view["baseline"]["content"]
    return canonical_hash({"station": view["target"]["entity"], "cutoff": view["cutoff"],
        "physical_start": view["target"]["physical_start"], "physical_end": view["target"]["physical_end"],
        "native_taf": content["native_taf"]["raw"],
        "query_ids": content["E_question"]["query_ids"],
        "assets": [{"id": a["asset_id"], "revision": a["source_revision"], "content": a["content"]}
                   for a in sorted(view["assets"], key=lambda a: a["asset_id"])],
        "bank": content["calibration_bank_sha256"]})
