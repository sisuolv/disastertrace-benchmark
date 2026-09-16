"""Finite preparation controls under a fixed, common probability forecast.

This is a synthetic decision scenario, not an operational warning optimizer.
The two-step planner assumes current probabilities persist over its horizon.
"""

import math

from .admission import AdmissionEvent


def projected_cost(engine, probabilities, miss_penalty):
    reducer = engine.preparation
    if reducer is None or set(probabilities) != set(reducer.jobs):
        raise ValueError("Every preparation job requires the same fixed forecast")
    if (
        type(miss_penalty) not in (int, float)
        or not math.isfinite(miss_penalty)
        or miss_penalty < 0
        or any(
            type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1
            for p in probabilities.values()
        )
    ):
        raise ValueError("Finite probabilities and nonnegative loss required")
    expected = float(reducer.spent)
    for jid, job in reducer.jobs.items():
        state = reducer.states[jid]
        if jid in reducer.snapshots:
            covered = reducer.snapshots[jid]["ready"]
        else:
            covered = (
                state["status"] in {"running", "ready"}
                and state["finished_at"] <= job["deadline"] <= job["expires_at"]
            )
        expected += probabilities[jid] * miss_penalty * (not covered)
    return expected


def act(engine, action, at, *, event_id):
    kind, job = action
    if kind == "wait":
        engine.run([], until=at)
        return True
    if kind not in {"prepare", "cancel_preparation"}:
        raise ValueError("Unknown decision action")
    engine.run([AdmissionEvent(event_id, at, kind, {"job_id": job})], until=at)
    return engine.preparation.history[-1]["status"] in {"started", "canceled_cleanup_pending"}


def possible_actions(engine):
    reducer = engine.preparation
    actions = [("wait", None)]
    for jid, state in sorted(reducer.states.items()):
        if state["status"] == "unstarted" and jid not in reducer.snapshots:
            actions.append(("prepare", jid))
        elif state["status"] in {"running", "ready"}:
            actions.append(("cancel_preparation", jid))
    return actions


def choose_preparation(engine, probabilities, *, method, at, next_at, miss_penalty):
    """Return one action using only current forecasts, state and known job costs."""
    projected_cost(engine, probabilities, miss_penalty)
    if engine._last_time != at or type(next_at) is not int or next_at <= at:
        raise ValueError("Advance the common clock before a forward decision")
    if method == "no_preparation":
        return ("wait", None)
    if method in {"threshold", "edf"}:
        jobs = sorted(engine.preparation.jobs)
        if method == "edf":
            jobs.sort(key=lambda jid: (engine.preparation.jobs[jid]["deadline"], jid))
        for jid in jobs:
            job = engine.preparation.jobs[jid]
            if probabilities[jid] * miss_penalty <= job["cost"]:
                continue
            branch = engine.fork()
            if act(
                branch,
                ("prepare", jid),
                at + 1,
                event_id="decision-trial-" + str(len(branch._events)),
            ):
                return ("prepare", jid)
        return ("wait", None)
    if method != "rolling_two_step":
        raise ValueError("Unregistered decision baseline")
    ranked = []
    for index, action in enumerate(possible_actions(engine)):
        first = engine.fork()
        if not act(first, action, at + 1, event_id="decision-trial-" + str(len(first._events))):
            continue
        first.run([], until=next_at)
        costs = []
        for following in possible_actions(first):
            second = first.fork()
            if act(
                second,
                following,
                next_at + 1,
                event_id="decision-trial-" + str(len(second._events)),
            ):
                costs.append(projected_cost(second, probabilities, miss_penalty))
        ranked.append((min(costs), index, action))
    return min(ranked)[2]
