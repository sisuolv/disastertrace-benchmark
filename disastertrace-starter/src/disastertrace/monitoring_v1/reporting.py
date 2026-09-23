"""Derived evidence accounting with a fixed roster, independent of future outcomes."""

from collections import Counter


REPORT_SUPPORT_STATES = ("supported", "refuted", "undetermined", "inconsistent")


def e_status_summary(states, roster):
    roster = list(roster)
    if len(set(roster)) != len(roster) or not set(states) <= set(roster):
        raise ValueError("Evidence states require the unique registered roster")
    counts = Counter()
    missing = 0
    for key in roster:
        state = states.get(key)
        if state is None:
            missing += 1
        elif state not in REPORT_SUPPORT_STATES:
            raise ValueError("Unknown report support state: " + str(state))
        else:
            counts[state] += 1
    return {
        "registered": len(roster),
        "states": {name: counts[name] for name in REPORT_SUPPORT_STATES},
        "missing_frame": missing,
        "determined": counts["supported"] + counts["refuted"],
        "outcome_mask_used": False,
    }
