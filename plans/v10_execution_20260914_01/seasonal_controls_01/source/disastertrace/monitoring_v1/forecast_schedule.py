"""Public forecast slots separate acquisition policy from invocation scheduling."""


def validate_schedule(config):
    schedule = config.get("forecast_schedule")
    if schedule is None:
        return
    fields = {"kind", "lead_seconds", "spacing_seconds"}
    if (
        not isinstance(schedule, dict)
        or set(schedule) != fields
        or schedule["kind"] != "public_serial_slots.v1"
        or config.get("session_runtime") != "typed_admission_v1"
        or config.get("admission_semantics") != "measurement.v3"
        or config.get("gate")
    ):
        raise ValueError("Public forecast schedule requires typed v3 with no prediction gate")
    if any(
        type(schedule[k]) is not int or schedule[k] <= 0
        for k in ("lead_seconds", "spacing_seconds")
    ):
        raise ValueError("Forecast slot durations must be positive integer seconds")
    cap = config["per_tick_forecast_cap"]
    if (
        type(cap) is not int
        or cap < 1
        or schedule["lead_seconds"] >= config["wakeup_seconds"]
        or (cap - 1) * schedule["spacing_seconds"] >= schedule["lead_seconds"]
    ):
        raise ValueError("Forecast slots must follow wakeup and precede the deadline")


def public_slots(active, config, stable_rank):
    """Only public opportunity identity, deadline and registered seed affect slots."""
    validate_schedule(config)
    schedule = config.get("forecast_schedule")
    if schedule is None:
        return None
    if len({o["cutoff"] for o in active}) != 1:
        raise ValueError("One common cutoff required for a forecast slot frame")
    cutoff = active[0]["cutoff"]
    ordered = sorted(
        active, key=lambda o: stable_rank(config["seed"], "forecast_slot", o["opportunity_id"])
    )
    return {
        o["opportunity_id"]: cutoff
        - schedule["lead_seconds"] * 1_000_000
        + index * schedule["spacing_seconds"] * 1_000_000
        for index, o in enumerate(ordered[: config["per_tick_forecast_cap"]])
    }
