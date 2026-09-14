"""The shared deterministic clock for legacy and typed session reducers."""

import json


def run_clock(owner, events, *, until, event_order, decode):
    if getattr(owner, "_clock_running", False):
        raise ValueError("Reentrant event clock is not permitted")
    owner._clock_running = True
    try:
        return _advance_clock(owner, events, until=until, event_order=event_order, decode=decode)
    finally:
        owner._clock_running = False


def _advance_clock(owner, events, *, until, event_order, decode):
    if until is not None and (
        type(until) is not int or (owner._last_time is not None and until < owner._last_time)
    ):
        raise ValueError("Invalid or reversed event clock boundary")
    pending = {}
    for event in events:
        encoded = event.to_dict()
        decode(encoded)
        if event.kind not in event_order:
            raise ValueError("Unknown event phase")
        old = pending.get(event.event_id, owner._events.get(event.event_id))
        if old is not None:
            if old != encoded:
                raise ValueError("Conflicting idempotent event")
            continue
        if owner._last_time is not None and event.time <= owner._last_time:
            raise ValueError("No backdated events after a processed clock boundary")
        pending[event.event_id] = json.loads(json.dumps(encoded, allow_nan=False))
    # Registration follows complete batch validation, including duplicate IDs.
    for identity, encoded in pending.items():
        if owner.journal is not None:
            owner.journal.append(identity, encoded)
        owner._events[identity] = encoded
    upcoming = [decode(row) for key, row in owner._events.items() if key not in owner._processed]
    end = (
        max(
            [e.time for e in upcoming] + [o.cutoff for o in owner.opportunities.values()], default=0
        )
        if until is None
        else until
    )
    times = {e.time for e in upcoming if e.time <= end}
    times.update(
        o.cutoff
        for o in owner.opportunities.values()
        if o.cutoff <= end and o.opportunity_id not in owner.snapshots
    )
    times.update(t for t in owner._expiry_times(upcoming) if t <= end)
    if owner._last_time is not None:
        times = {t for t in times if t > owner._last_time}
    for time in sorted(times):
        key = getattr(owner, "_event_key", lambda e: (event_order[e.kind], e.event_id))
        group = sorted((e for e in upcoming if e.time == time), key=key)
        for event in group:
            if event_order[event.kind] <= 1:
                owner._process(event)
        owner._invalidate(time)
        owner._seal(time)
        owner._after_seal(time)
        for event in group:
            if event_order[event.kind] > 1:
                owner._process(event)
            owner._processed.add(event.event_id)
        owner._last_time = time
    owner._last_time = end if owner._last_time is None else max(owner._last_time, end)
    return owner.snapshots
