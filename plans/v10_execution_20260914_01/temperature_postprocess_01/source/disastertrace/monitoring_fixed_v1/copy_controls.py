"""Explicit visible-value null predictors with ordinary override admission."""

from .contracts import Forecast

COPY_KINDS = {"copy_current_state", "copy_latest_baseline"}


class VisibleValuePredictor:
    def __init__(self, kind):
        if kind not in COPY_KINDS:
            raise ValueError("Unknown visible-value program")
        self.kind = kind

    def predict(self, bundle):
        view = bundle.policy_view()
        source = "state" if self.kind == "copy_current_state" else "baseline"
        return Forecast(**view[source]["forecast"])
