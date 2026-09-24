"""Baseline/method registry for the v18 controlled pilot (Batch V4, task B1).

A "FOLLOW" name is not a real predictor (finding note from the original audit).  This module
registers actually-executable, non-LLM baselines alongside the pilot's LLM arm identities, with
full metadata, so a future round can compute genuine method comparisons once real Y is
authorized.  Nothing here reads real weather/Y/holdout data or dispatches any model/API call.

Status discipline: every entry's ``calibration_exposure`` is ``"INTERFACE_READY"``, never
``"CALIBRATED"``, because no real outcome (Y) has been authorized this round.  A prediction-gain
claim requires a qualified real baseline *and* real Y; neither exists yet.  Y-free behavioral
tests (e.g. "does this baseline ever raise on malformed input", "is it deterministic") are valid
and may be run now; forecast-gain claims may not.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping

from .support import Interval, classify

_PREVAILING_OPERATORS = {"BASE", "FM", "BECMG"}
_INTERVAL_KEYS = {"lower", "upper", "lower_closed", "upper_closed"}


def _bound(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if value == "+inf":
        return math.inf
    if value == "-inf":
        return -math.inf
    return None


def _visibility_interval(visibility_m: Any) -> Interval | None:
    """Real ``build_v18_dev_episodes.py`` output stores ``visibility_m`` as the same
    ``Interval.to_dict()`` shape ``providers.aviation.visibility`` produces (e.g. "P6SM" ->
    lower=9656.064m, upper=+inf, lower_closed=False) -- a censored/bucketed report, not always a
    single point. Only unit-test fixtures have used a bare number so far; both are accepted here.
    """

    if isinstance(visibility_m, bool):
        return None
    if isinstance(visibility_m, (int, float)):
        value = float(visibility_m)
        return Interval(value, value)
    if isinstance(visibility_m, Mapping) and _INTERVAL_KEYS.issubset(visibility_m):
        lower, upper = _bound(visibility_m.get("lower")), _bound(visibility_m.get("upper"))
        if lower is None or upper is None:
            return None
        try:
            return Interval(lower, upper, bool(visibility_m["lower_closed"]), bool(visibility_m["upper_closed"]))
        except ValueError:
            return None
    return None


@dataclass(frozen=True)
class BaselineEntry:
    """One registered method's identity and support, LLM or not."""

    name: str
    kind: str  # "non_llm_executable" | "llm_arm_registered_not_dispatched"
    source: str
    support: str
    units: str
    threshold: float
    lead: str
    availability: str
    calibration_exposure: str
    fallback: str

    def __post_init__(self) -> None:
        if self.kind not in {"non_llm_executable", "llm_arm_registered_not_dispatched"}:
            raise ValueError("Unknown baseline kind")
        if self.calibration_exposure not in {"INTERFACE_READY", "CALIBRATED"}:
            raise ValueError("calibration_exposure must be INTERFACE_READY or CALIBRATED")
        if self.calibration_exposure == "CALIBRATED":
            # Nothing in this repo has real Y yet; this branch exists so a future,
            # genuinely-calibrated entry has somewhere to go without a code change here.
            raise ValueError("No real Y is authorized this round; cannot register CALIBRATED")

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "source": self.source,
            "support": self.support,
            "units": self.units,
            "threshold": self.threshold,
            "lead": self.lead,
            "availability": self.availability,
            "calibration_exposure": self.calibration_exposure,
            "fallback": self.fallback,
        }


def persistence_baseline(current_evidence: Mapping[str, Any], *, threshold_m: float = 5000.0) -> float | None:
    """A genuinely executable, non-LLM, deterministic reference prediction.

    Reads only the *prevailing* (BASE/FM/BECMG) period of ``current_evidence`` -- the same
    scorer-label-free shape ``agent_view_v18.public_checkpoint`` already returns -- and applies a
    fixed step rule: 1.0 if the prevailing visibility is below ``threshold_m``, else 0.0. This is
    deliberately not smoothed or calibrated; a step function does not pretend to a confidence
    shape it has not earned. Native PROB30/PROB40 (conditional) periods are never read here --
    a conditional probability is not the target's routine-report Y, matching the existing guard
    against using native PROB directly as a target probability.

    Returns ``None`` when there is no prevailing period to persist from (empty/unknown evidence);
    this is a genuine "no opinion" result, not a guessed 0.0.
    """

    periods = current_evidence.get("periods") if isinstance(current_evidence, Mapping) else None
    if not isinstance(periods, list):
        return None
    prevailing = [p for p in periods if isinstance(p, Mapping) and p.get("operator") in _PREVAILING_OPERATORS]
    if not prevailing:
        return None
    interval = _visibility_interval(prevailing[-1].get("visibility_m"))
    if interval is None:
        return None
    verdict = classify(interval, "lt", threshold_m)
    if verdict == "undetermined":
        # The reported bucket straddles the threshold (e.g. a "4SM" ceiling report
        # against a 4500 m threshold) -- a real, honest "no opinion", not a bug.
        return None
    return 1.0 if verdict == "supported" else 0.0


def build_registry() -> list[dict[str, Any]]:
    """The full method registry: one executable non-LLM baseline plus the pilot's known LLM arms.

    The LLM arm entries are registered for identity/bookkeeping completeness (so a future round's
    method table has one place listing every method under comparison); they are NOT dispatched by
    this function and carry no execution here -- dispatching any of them requires a real,
    separately-authorized provider run (P1), which this round does not have.
    """

    entries = [
        BaselineEntry(
            name="persistence",
            kind="non_llm_executable",
            source="agent_view_v18.public_checkpoint current_evidence, prevailing period only",
            support="single future 1-hour target window, routine TAF report",
            units="probability in [0,1]",
            threshold=5000.0,
            lead="checkpoint cutoff (T-60/T-40/T-20 before target start)",
            availability="deterministic, always available once current_evidence is available",
            calibration_exposure="INTERFACE_READY",
            fallback="None (no opinion) when no prevailing period is visible",
        ),
    ]
    llm_arms = ("TRULY_FRESH", "PRIOR_P_ONLY", "PRIOR_P_FACT", "FULL_PREFIX_TRANSCRIPT")
    for arm in llm_arms:
        entries.append(
            BaselineEntry(
                name=arm,
                kind="llm_arm_registered_not_dispatched",
                source="scripts/run_v18_controlled_api.py prompt_for()",
                support="same target/support as the persistence baseline",
                units="probability in [0,1]",
                threshold=5000.0,
                lead="checkpoint cutoff (T-60/T-40/T-20 before target start)",
                availability="requires a separately-authorized real provider run (P1); not available this round",
                calibration_exposure="INTERFACE_READY",
                fallback="not applicable; unregistered/undispatched methods are not scored",
            )
        )
    return [entry.to_dict() for entry in entries]
