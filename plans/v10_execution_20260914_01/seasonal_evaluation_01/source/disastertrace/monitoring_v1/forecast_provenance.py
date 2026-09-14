"""Exact value identities and separate numerical sensitivities, without novelty claims."""

import math
import struct


def _probability(value):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("Finite probability required")
    return float(value)


def _ulp(a, b):
    if a == b:
        return 0
    return abs(struct.unpack(">Q", struct.pack(">d", a))[0] -
               struct.unpack(">Q", struct.pack(">d", b))[0])


def value_provenance(proposal, *, current, baseline, other_visible=(), program=None,
                     outcome=None, effective=None):
    p, current, baseline = map(_probability, (proposal, current, baseline))
    values = [("exact_current", current), ("exact_latest_baseline", baseline)]
    values += [("exact_other_visible_value", _probability(v)) for v in other_visible]
    if program is not None:
        values.append(("exact_program_mapping", _probability(program)))
    matches = sorted({kind for kind, v in values if p == v})
    category = next((kind for kind, v in values if p == v), "numerically_distinct")
    distance = min(abs(p-current), abs(p-baseline))
    if outcome is not None and (type(outcome) not in (int, float) or outcome not in (0, 1)):
        raise ValueError("Binary outcome or missing required")
    if effective is not None:
        effective = _probability(effective)
    return {"schema": "forecast_value_provenance.v2", "proposal": p,
            "dispatch_current": current, "dispatch_baseline": baseline,
            "proposal_exact_class": category, "all_exact_matches": matches,
            "absolute_delta_current": abs(p-current), "absolute_delta_baseline": abs(p-baseline),
            "ulp_distance_current": _ulp(p, current), "ulp_distance_baseline": _ulp(p, baseline),
            "within_1e_6": distance <= 1e-6, "within_0_005": distance <= .005,
            "loss_delta_vs_baseline": None if outcome is None else (p-outcome)**2-(baseline-outcome)**2,
            "effective_at_cutoff": effective,
            "effective_delta_loss_vs_baseline": None if outcome is None or effective is None else
                (effective-outcome)**2-(baseline-outcome)**2,
            "new_information_established": False,
            "attribution_limit": "Numeric identity only; causal gain sources require matched trajectory controls"}
