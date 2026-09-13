"""The shared deterministic clock for legacy and typed session reducers."""

import json


def run_clock(owner, events, *, until, event_order, decode):
    for event in events:
        encoded = event.to_dict()
        if event.event_id in owner._events:
            if owner._events[event.event_id] != encoded:
                raise ValueError("Conflicting idempotent event")
            continue
        if owner._last_time is not None and event.time <= owner._last_time:
            raise ValueError("No backdated events after a processed clock boundary")
        if owner.journal is not None:
            owner.journal.append(event.event_id, encoded)
        owner._events[event.event_id] = json.loads(json.dumps(encoded, allow_nan=False))
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
        group = sorted(
            (e for e in upcoming if e.time == time), key=lambda e: (event_order[e.kind], e.event_id)
        )
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
