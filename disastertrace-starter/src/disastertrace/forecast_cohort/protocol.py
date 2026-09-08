"""One declared sampling repeat, retaining inherited slot and seed definitions."""

from disastertrace.forecast_task.protocol import METHODS
from disastertrace.forecast_task.protocol import schedule as inherited_schedule

REPEATS = 1
__all__ = ["METHODS", "REPEATS", "schedule"]


def schedule(public):
    return [slot for slot in inherited_schedule(public) if slot["repeat"] == 0]
