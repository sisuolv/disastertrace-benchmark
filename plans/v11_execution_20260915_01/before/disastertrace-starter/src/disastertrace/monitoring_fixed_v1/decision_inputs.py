"""Read lawful current F values for the synthetic preparation baselines."""

from .contracts import fingerprint
from .decision_baselines import choose_preparation


def choose_admitted_preparation(engine, *, method, at, next_at, miss_penalty):
    """Select without changing the engine or accessing eventual outcomes.

    Repeated calls may use revised forecasts. The two-step baseline itself keeps
    the current probabilities constant within its limited planning horizon.
    """
    if type(at) is not int or engine._last_time != at:
        raise ValueError("Decision requires the current processed shared clock")
    if engine.preparation is None:
        raise ValueError("A bound preparation scenario is required")
    probabilities, bindings = {}, {}
    for jid, job in sorted(engine.preparation.jobs.items()):
        state = engine.states[job["target_id"]]
        forecast = state.effective(at)
        if forecast.kind != "event_probability" or forecast.units != "probability":
            raise ValueError("Preparation demands require an admitted probability")
        probabilities[jid] = forecast.value
        active_override = state.override is not None and at <= state.expires_at
        bindings[jid] = {
            "target_id": job["target_id"],
            "forecast": forecast.to_dict(),
            "base_hash": state.base_hash,
            "mode": "OVERRIDE" if active_override else "FOLLOW",
            "override_base_hash": state.override_base if active_override else None,
            "override_expires_at": state.expires_at if active_override else None,
        }
    action = choose_preparation(
        engine,
        probabilities,
        method=method,
        at=at,
        next_at=next_at,
        miss_penalty=miss_penalty,
    )
    record = {
        "schema": "disastertrace.admitted_preparation_decision.v1",
        "at": at,
        "next_at": next_at,
        "action_at": at + 1,
        "method": method,
        "miss_penalty": miss_penalty,
        "forecast_basis": "current_admitted_effective",
        "planning_assumption": "Current probabilities remain fixed inside the two-step horizon.",
        "probabilities": probabilities,
        "forecast_bindings": bindings,
        "preparation_state_sha256": fingerprint(engine.preparation.to_dict()),
        "action": list(action),
    }
    return {**record, "sha256": fingerprint(record)}
