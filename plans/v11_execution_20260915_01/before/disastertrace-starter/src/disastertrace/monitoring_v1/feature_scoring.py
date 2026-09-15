"""Separate native extraction, missingness, and numerical forecast effects."""

import math

from .evidence import interval_from_dict
from .native_feature_forecast import feature_vector, native_claims, predict_features
from .regional_calibration import apply_monotone
from .regional_calibration_v2 import coherent_cdf
from .support import classify
from .targets import canonical_hash


def field_agreement(value, reference, *, visibility=False):
    def close(a, b):
        return a == b or (
            type(a) in (float, int)
            and type(b) in (float, int)
            and math.isclose(a, b, rel_tol=0, abs_tol=1e-6)
        )

    if value is None or reference is None or not visibility:
        return {
            "literal_exact": value == reference,
            "semantic_exact": value == reference,
            "numeric_tolerance": close(value, reference),
        }
    exact = tolerance = True
    for bound in ("lower", "upper"):
        exact &= value[bound] == reference[bound]
        tolerance &= close(value[bound], reference[bound])
        if reference[bound] != "+inf":
            exact &= value[bound + "_closed"] == reference[bound + "_closed"]
            tolerance &= value[bound + "_closed"] == reference[bound + "_closed"]
    return {
        "literal_exact": value == reference,
        "semantic_exact": bool(exact),
        "numeric_tolerance": bool(tolerance),
    }


def claimed_support(claim, threshold):
    visibility = claim["visibility"]
    return (
        "undetermined"
        if visibility is None
        else classify(interval_from_dict(visibility), "lt", threshold)
    )


def forecast_controls(bundle, banks, model_claims):
    """The model path consumes its actual claims; native repairs are diagnostics."""
    target, candidate = bundle["target"], bundle["candidate"]
    qids, disclosed, at = bundle["query_ids"], bundle["disclosed"], bundle["at"]
    native = native_claims(qids, disclosed, at=at)
    available = model_claims is not None
    missing_mask = (
        None
        if not available
        else {
            q: {
                field: None if value is None else native[q][field]
                for field, value in fields.items()
            }
            for q, fields in model_claims.items()
        }
    )
    configurations = {
        "values_common": ("values", {}, None),
        "values_native": ("values", disclosed, native),
        "values_model": ("values", disclosed if available else {}, model_claims),
        "values_validmask": (
            "values",
            disclosed if available else {},
            native if available else None,
        ),
        "values_missingmask": ("values", disclosed if available else {}, missing_mask),
        "common_native": ("common", disclosed, native),
        "mask_age_native": ("mask_age", disclosed, native),
    }
    result = {}
    for name, (mode, view, claims) in configurations.items():
        features = feature_vector(target, candidate, qids, view, at=at, mode=mode, claims=claims)
        probabilities = predict_features(banks[mode], features)
        result[name + "_raw"] = {str(t): probabilities[str(t)] for t in (1000, 5000)}
        if "post_calibration" in banks[mode]:
            mapped = [
                apply_monotone(banks[mode]["post_calibration"][str(t)], probabilities[str(t)])
                for t in (1000, 5000)
            ]
            information = canonical_hash(features)
            values = coherent_cdf(mapped, [information, information])
            result[name + "_pav_prior2_cdf"] = dict(zip(("1000", "5000"), values, strict=True))
    return result
