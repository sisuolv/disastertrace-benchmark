"""Public-only simple strategies; no Gold compiler or hidden catalogue is imported."""

from collections import Counter

from disastertrace.controlled.public_oracle import answer, parse_evidence
from disastertrace.controlled.schema import FIELDS, UNITS, action_for, aware, empty_decision

POLICIES = (
    "initial_only",
    "last_delivered",
    "most_frequent_value",
    "most_frequent_unique_assertion",
    "latest_issued_per_key",
    "scope_blind_last_delivered",
    "public_oracle",
)


def solve(request, policy="latest_issued_per_key"):
    if policy not in POLICIES:
        raise ValueError("unknown public policy")
    entries = parse_evidence(request)
    if policy == "public_oracle":
        return answer(request)
    result = empty_decision()
    for field in FIELDS:
        candidates = [
            e
            for e in entries
            if e["assertion"]["variable"] == field
            and e["assertion"]["unit"] == UNITS[field]
            and (
                policy == "scope_blind_last_delivered"
                or all(e["assertion"][k] == v for k, v in request["target"].items())
            )
        ]
        if not candidates:
            continue
        if policy == "initial_only":
            selected = candidates[0]
        elif policy == "latest_issued_per_key":
            selected = max(
                candidates, key=lambda e: (aware(e["issued_at"]), e["delivery_index"], e["line"])
            )
        elif policy.startswith("most_frequent"):
            counted = (
                list({e["assertion"]["revision_id"]: e for e in candidates}.values())
                if policy == "most_frequent_unique_assertion"
                else candidates
            )
            counts = Counter(e["assertion"]["value"] for e in counted)
            selected = max(
                candidates,
                key=lambda e: (counts[e["assertion"]["value"]], e["delivery_index"], e["line"]),
            )
        else:
            selected = candidates[-1]
        result["state"][field] = {
            "status": "known",
            "value": selected["assertion"]["value"],
            "evidence": [{"record_id": selected["record_id"], "line": selected["line"]}],
        }
    result["action"] = action_for(result["state"])
    return result
