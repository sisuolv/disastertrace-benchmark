"""Public, compact handles for a charged global/shared LLM selector."""

from __future__ import annotations

import json

SELECTOR_SYSTEM = """Allocate one shared monitoring budget to improve forecasts of fixed future native visibility reports. The common complete professional TAF inputs and frozen research probability map are already supplied. Extra queries reveal past registered neighbor report slots. One shared query can serve several targets, but acquiring facts does not guarantee useful future predictions. You pay for this selection call and each forecast call from the SAME model-call/token/compute budget. The remaining hard resources shown exclude this call's reservation; the forecast-call upper bound tells you what each additional call must reserve. Consider remaining calendar ticks and all scored opportunities, including those left at their baseline. Each target's current_state shows whether it already has an explicit override. The session protocol controls whether a relevant baseline change invalidates that override (base_bound_override) or retains it (persistent_override). Choose zero or more registered query handles and zero or more forecast handles, up to the stated capacity. You may save resources. Use only the public common inputs and lawfully acquired shared reports shown here. Return only JSON: {"query_order":["q0"],"forecast_handles":["t0"]}. Handles must be unique and registered; no extra prose."""


def parse_selection(raw, *, query_handles, target_handles, forecast_cap):
    text = raw.strip()
    if text.startswith("```json\n") and text.endswith("```"):
        text = text[8:-3].strip()
    elif text.startswith("```\n") and text.endswith("```"):
        text = text[4:-3].strip()
    value = json.loads(text)
    if not isinstance(value, dict) or set(value) != {"query_order", "forecast_handles"}:
        raise ValueError("Invalid selector schema")
    for key, allowed in (("query_order", query_handles), ("forecast_handles", target_handles)):
        sequence = value[key]
        if (
            not isinstance(sequence, list)
            or not all(isinstance(v, str) for v in sequence)
            or len(sequence) != len(set(sequence))
            or not set(sequence) <= set(allowed)
        ):
            raise ValueError("Selector returned duplicate or unregistered handles")
    if len(value["forecast_handles"]) > forecast_cap:
        raise ValueError("Selector exceeds the per-tick forecast capacity")
    return value
