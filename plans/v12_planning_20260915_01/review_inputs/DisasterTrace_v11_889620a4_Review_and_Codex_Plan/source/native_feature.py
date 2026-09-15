"""Native H15 predictors with explicitly bound common or paid information."""

import json
import math

from ..monitoring_v1.native_feature_forecast import (
    FEATURE_VERSION,
    feature_vector,
    predict_features,
)
from ..monitoring_v1.regional_calibration import apply_monotone
from ..monitoring_v1.regional_calibration_v2 import coherent_cdf
from .contracts import Forecast, Target, canonical, fingerprint

FEATURE_KINDS = {"native_feature_raw", "native_feature_calibrated"}


def validate_feature_bank(bank, *, calibrated=False):
    if (
        not isinstance(bank, dict)
        or bank.get("feature_version") != FEATURE_VERSION
        or bank.get("mode") not in {"common", "values"}
    ):
        raise ValueError("A frozen common or values feature bank is required")
    fields = {"feature_names", "mean", "scale", "coefficients", "intercepts", "mapping_version"}
    if not fields <= set(bank) or not bank["mapping_version"]:
        raise ValueError("Incomplete feature bank")
    names = bank["feature_names"]
    if bank["mode"] == "common" and any(str(name).startswith("slot") for name in names):
        raise ValueError("A common information bank cannot consume paid slot features")
    n = len(names)
    if (
        not n
        or len(set(names)) != n
        or any(not isinstance(s, str) or not s for s in names)
        or len(bank["mean"]) != n
        or len(bank["scale"]) != n
        or len(bank["intercepts"]) != 3
        or len(bank["coefficients"]) != 3
        or any(len(row) != n for row in bank["coefficients"])
    ):
        raise ValueError("Invalid feature bank dimensions")
    numbers = [
        *bank["mean"],
        *bank["scale"],
        *bank["intercepts"],
        *(number for row in bank["coefficients"] for number in row),
    ]
    if any(type(x) not in (int, float) or not math.isfinite(x) for x in numbers) or any(
        s <= 0 for s in bank["scale"]
    ):
        raise ValueError("Feature coefficients and scales must be finite and valid")
    if calibrated:
        maps = bank.get("post_calibration", {})
        if set(maps) != {"1000", "5000"} or any(not blocks for blocks in maps.values()):
            raise ValueError("Both feature calibration maps are required")
        for blocks in maps.values():
            previous = -1.0
            for block in blocks:
                if (
                    set(block) != {"lower", "upper", "value"}
                    or any(
                        type(x) not in (int, float) or not math.isfinite(x) for x in block.values()
                    )
                    or not 0 <= block["lower"] <= block["upper"] <= 1
                    or not previous <= block["value"] <= 1
                ):
                    raise ValueError("Invalid monotone feature calibration")
                previous = block["value"]


class NativeFeaturePredictor:
    def __init__(self, bank, *, at, calibrated=False):
        validate_feature_bank(bank, calibrated=calibrated)
        self.bank = json.loads(canonical(bank))
        self.at, self.calibrated = at, calibrated

    def predict(self, bundle):
        view = bundle.policy_view()
        content = view["baseline"]["content"]
        assets = {a["content"]["query_id"]: a["content"] for a in view["assets"]}
        features = feature_vector(
            content["legacy_target_contract"],
            content["native_taf"],
            content["E_question"]["query_ids"],
            assets,
            at=self.at,
            mode=self.bank["mode"],
        )
        values = predict_features(self.bank, features)
        probabilities = [values[t] for t in ("1000", "5000")]
        if self.calibrated:
            mapped = [
                apply_monotone(self.bank["post_calibration"][t], p)
                for t, p in zip(("1000", "5000"), probabilities, strict=True)
            ]
            identity = fingerprint(features)
            probabilities = coherent_cdf(mapped, [identity, identity])
        threshold = content["legacy_target_contract"]["threshold"]
        if threshold not in (1000, 5000):
            raise ValueError("Native feature bank qualifies only its two registered thresholds")
        target = Target(**view["target"])
        return Forecast(
            target.contract_hash,
            "event_probability",
            "probability",
            probabilities[(1000, 5000).index(threshold)],
        )
