"""Outcome-blind adoption rules for already computed binary forecasts."""

import math


def validate(policy):
    fields = {
        "always": {"kind"},
        "never": {"kind"},
        "first_target_only": {"kind"},
        "change_epsilon": {"kind", "epsilon"},
        "brier_harm_limit": {"kind", "max_pointwise_harm"},
    }
    if (
        not isinstance(policy, dict)
        or policy.get("kind") not in fields
        or set(policy) != fields[policy["kind"]]
    ):
        raise ValueError("Registered adoption policy and exact fields required")
    for name in set(policy) - {"kind"}:
        value = policy[name]
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError("Adoption threshold must lie in [0,1]")


def decide(policy, *, current, candidate, previously_adopted):
    validate(policy)
    if any(
        type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1
        for p in (current, candidate)
    ):
        raise ValueError("Adoption rules require binary event probabilities")
    if type(previously_adopted) is not bool:
        raise ValueError("Explicit target admission history required")
    kind = policy["kind"]
    change = abs(candidate - current)
    harm = max((candidate - y) ** 2 - (current - y) ** 2 for y in (0, 1))
    adopt = {
        "always": True,
        "never": False,
        "first_target_only": not previously_adopted,
        "change_epsilon": change >= policy.get("epsilon", 0),
        "brier_harm_limit": harm <= policy.get("max_pointwise_harm", 0),
    }[kind]
    return {
        "policy": policy,
        "adopt": adopt,
        "current_probability": current,
        "candidate_probability": candidate,
        "absolute_change": change,
        "max_pointwise_harm": harm,
        "previously_adopted": previously_adopted,
        "reference": "current effective probability at completion",
        "scope": "one binary loss comparison at adoption; no future baseline or calibration guarantee",
        "calibration_guarantee": False,
    }
