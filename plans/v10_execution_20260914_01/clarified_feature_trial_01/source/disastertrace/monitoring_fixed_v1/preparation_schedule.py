"""Bind a synthetic, exogenous D schedule to the existing session event clock."""

from ..monitoring_v1.preparation import PreparationReducer
from .admission import AdmissionEvent
from .contracts import require_fields


def bind_preparation_schedule(config):
    if "preparation_schedule" not in config:
        return None, []
    if config.get("session_runtime") != "typed_admission_v1":
        raise ValueError("Preparation schedules require the typed session clock")
    schedule = config["preparation_schedule"]
    require_fields(schedule, "schema decision_basis scenario events", "preparation schedule")
    if (
        schedule["schema"] != "disastertrace.session_preparation_schedule.v1"
        or schedule["decision_basis"] != "frozen_exogenous_schedule"
        or not isinstance(schedule["scenario"], dict)
        or not isinstance(schedule["events"], list)
    ):
        raise ValueError("Explicit frozen exogenous preparation schedule required")
    reducer = PreparationReducer(schedule["scenario"])
    events, seen = [], set()
    for row in schedule["events"]:
        require_fields(row, "event_id time kind payload", "preparation schedule event")
        require_fields(row["payload"], "job_id", "preparation schedule payload")
        if (
            row["kind"] not in {"prepare", "cancel_preparation"}
            or row["payload"]["job_id"] not in reducer.jobs
            or not isinstance(row["event_id"], str)
            or row["event_id"] in seen
        ):
            raise ValueError("Unregistered or duplicate preparation schedule event")
        events.append(AdmissionEvent(**row))
        seen.add(row["event_id"])
    return reducer.card, events
