"""Fixed-opportunity outcome scoring, with separately eligible transition rates."""

from .compiler import transition_obligations
from .types import STATE_FIELDS


def rate(numerator, denominator):
    return {
        "numerator": numerator,
        "denominator": denominator,
        "rate": numerator / denominator if denominator else None,
    }


def field_equal(site, key, actual, expected):
    if key not in actual:
        return False
    if key == "map_locator" and expected[key] is not None and actual[key] == "point:" + site:
        return True
    return actual[key] == expected[key]


def score_trajectory(references, outcomes):
    if len(references) != len(outcomes):
        raise ValueError("every planned checkpoint must have an explicit outcome")
    correct, rows = 0, []
    value_correct, value_total, support_correct, support_total = 0, 0, 0, 0
    change_correct, change_total, refresh_correct, refresh_total = 0, 0, 0, 0
    stable_errors, stable_eligible, assertions, unknowns = 0, 0, 0, 0
    previous_predicted = {}
    for index, (gold, outcome) in enumerate(zip(references, outcomes)):
        predicted = (
            outcome.get("value", {}).get("state", {})
            if outcome["status"] == "received_valid"
            else {}
        )
        strict = (
            set(predicted) == set(gold["state"])
            and outcome["status"] == "received_valid"
            and all(
                set(predicted[site]) == STATE_FIELDS
                and all(field_equal(site, key, predicted[site], row) for key in STATE_FIELDS)
                for site, row in gold["state"].items()
            )
        )
        correct += strict
        mismatch = []
        for site, expected in gold["state"].items():
            actual = predicted.get(site, {})
            for key in sorted(STATE_FIELDS):
                equal = field_equal(site, key, actual, expected)
                if key in {"relation", "watched", "inspection_required"}:
                    value_total += 1
                    value_correct += equal
                    if expected[key] is None or expected[key] == "unknown":
                        unknowns += 1
                        assertions += (
                            key in actual and actual[key] is not None and actual[key] != "unknown"
                        )
                else:
                    support_total += 1
                    support_correct += equal
                if not equal:
                    mismatch.append(site + "." + key)
        obligations = transition_obligations(references[index - 1], gold) if index else {}
        for field in obligations.get("must_change_value", []):
            site, key = field.split(".")
            change_total += 1
            change_correct += predicted.get(site, {}).get(key, object()) == gold["state"][site][key]
        for field in obligations.get("must_change_provenance", []):
            site, key = field.split(".")
            refresh_total += 1
            refresh_correct += field_equal(site, key, predicted.get(site, {}), gold["state"][site])
        for field in obligations.get("must_preserve_value", []):
            site, key = field.split(".")
            if (
                previous_predicted.get(site, {}).get(key, object())
                == references[index - 1]["state"][site][key]
            ):
                stable_eligible += 1
                stable_errors += (
                    predicted.get(site, {}).get(key, object()) != gold["state"][site][key]
                )
        rows.append(
            {
                "checkpoint": index,
                "status": outcome["status"],
                "strict_correct": strict,
                "mismatches": mismatch,
                "extra_sites": sorted(set(predicted) - set(gold["state"])),
                "obligations": obligations,
            }
        )
        previous_predicted = predicted
    errors = [i for i, row in enumerate(rows) if not row["strict_correct"]]
    first_error = errors[0] if errors else None
    recovered = (
        next((i for i in range(first_error + 1, len(rows)) if rows[i]["strict_correct"]), None)
        if first_error is not None
        else None
    )
    return {
        "strict_checkpoints": rate(correct, len(rows)),
        "value_fields": rate(value_correct, value_total),
        "support_fields": rate(support_correct, support_total),
        "required_new_value_correct": rate(change_correct, change_total),
        "required_new_provenance_correct": rate(refresh_correct, refresh_total),
        "conditional_stable_value_degradation": rate(stable_errors, stable_eligible),
        "unsupported_known_assertions": rate(assertions, unknowns),
        "episode_all_correct": correct == len(rows),
        "first_error": first_error,
        "later_checkpoint_available": first_error is not None and first_error < len(rows) - 1,
        "first_subsequent_correct_latency": recovered - first_error
        if recovered is not None
        else None,
        "rows": rows,
    }
