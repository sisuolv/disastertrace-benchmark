"""Separate aviation E/F output heads over the same immutable visible snapshot.

This interface prepares future independent calls. It never projects a recorded
joint response into an E-only or F-only model call.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from .aviation import TRUTH_TO_SUPPORT
from .contracts import EvidenceBundle, Forecast, Target, canonical

Head = Literal["e_only", "f_only", "joint"]
PROMPT_VERSION = "aviation_heads.explicit_truth.v1"

_COMMON = (
    "Use only the information disclosed in this frozen snapshot. Timestamps are UTC "
    "microseconds. Native product facts and parsed measurement intervals are not "
    "error-free physical weather. Do not retrieve external sources or use memorized "
    "weather outcomes. There are no default answers and no example output values. "
    "Return only a JSON object, without explanations or markdown. "
)
_E = (
    "Answer the factual query about the PAST registered neighbor report slots in "
    "E_question. The proposition is existential: AT LEAST ONE registered slot has "
    "reported visibility strictly below threshold_m. fact_truth must be one of four "
    "JSON strings: true, false, unknown, conflict; never a JSON boolean. Return true "
    "only if a disclosed report's visibility interval proves it is below threshold_m. "
    "Return false only if EVERY registered slot is disclosed and its report interval "
    "proves it is NOT below threshold_m. Return unknown for unresolved or unqueried "
    "slots unless another disclosed slot already proves the existential proposition. "
    "Return conflict only for inconsistent source facts, not ordinary uncertainty. "
    "The presence of some evidence does not itself make the proposition true. Use "
    "visibility bounds in meters, including open/closed endpoints. "
)
_F = (
    "Forecast the FUTURE native routine visibility report event defined by target. "
    "probability must be a finite JSON number in [0,1], not a boolean or string. "
    "Use the common full TAF, frozen prior-month research probability and any "
    "disclosed neighbor report information; you may retain the baseline. TEMPO is "
    "not an official event probability. Unresolved past evidence does not force the "
    "future probability to 0.5, and known past facts do not determine the future. "
)
SYSTEMS = MappingProxyType(
    {
        "e_only": _COMMON + _E + "The output object must contain exactly fact_truth.",
        "f_only": _COMMON + _F + "The output object must contain exactly probability.",
        "joint": _COMMON
        + _E
        + _F
        + "The past evidence proposition and future target are separate. "
        "The output object must contain exactly fact_truth and probability.",
    }
)
_FIELDS = {
    "e_only": {"fact_truth"},
    "f_only": {"probability"},
    "joint": {"fact_truth", "probability"},
}


def _check_head(head):
    if type(head) is not str or head not in SYSTEMS:
        raise ValueError("Unknown output head")


def _aviation_target(bundle: EvidenceBundle) -> Target:
    row = bundle.policy_view()
    target = Target(**row["target"])
    if (
        target.output_kind != "event_probability"
        or target.variable != "visibility"
        or target.units != "m"
        or target.event_operator != "lt"
        or target.support_kind != "interval"
        or target.temporal_semantics != "future_physical"
        or target.report_policy != "iem_routine_unique_hour.v1"
    ):
        raise ValueError("These heads require the native aviation visibility event contract")
    question = row["baseline"]["content"].get("E_question", {})
    if question.get("predicate") != "any_registered_neighbor_slot_below_threshold":
        raise ValueError("Unsupported aviation E proposition")
    return target


@dataclass(frozen=True)
class HeadResponse:
    head: Head
    fact_truth: str | None
    forecast: Forecast | None

    def __post_init__(self):
        _check_head(self.head)
        if self.head == "f_only":
            if self.fact_truth is not None:
                raise ValueError("F-only cannot contain an E answer")
        elif type(self.fact_truth) is not str or self.fact_truth not in TRUTH_TO_SUPPORT:
            raise ValueError("Invalid fact_truth string")
        if self.head == "e_only":
            if self.forecast is not None:
                raise ValueError("E-only cannot contain an F forecast")
        elif not isinstance(self.forecast, Forecast):
            raise ValueError("F head requires a typed forecast")

    @property
    def e_status(self) -> str | None:
        # Absent E is not an 'unknown' answer and must never enter the E denominator.
        return None if self.fact_truth is None else TRUTH_TO_SUPPORT[self.fact_truth]


def model_messages(bundle: EvidenceBundle, head: Head) -> list[dict[str, str]]:
    _check_head(head)
    _aviation_target(bundle)
    return [
        {"role": "system", "content": SYSTEMS[head]},
        {"role": "user", "content": canonical(bundle.policy_view())},
    ]


def _unique_object(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("Duplicate response field")
        result[name] = value
    return result


def _reject_constant(value):
    raise ValueError("Nonfinite JSON constant: " + value)


def parse_response(raw: str, bundle: EvidenceBundle, head: Head) -> HeadResponse:
    _check_head(head)
    target = _aviation_target(bundle)
    if type(raw) is not str:
        raise ValueError("Model response must be JSON text")
    row = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    if not isinstance(row, dict) or set(row) != _FIELDS[head]:
        raise ValueError("Unexpected or missing fields for " + head)
    forecast = None
    if head != "e_only":
        try:
            forecast = Forecast(
                target.contract_hash, "event_probability", "probability", row["probability"]
            )
        except OverflowError as exc:
            raise ValueError("Probability must be finite and in [0,1]") from exc
        target.check_forecast(forecast)
    return HeadResponse(head, row.get("fact_truth"), forecast)
