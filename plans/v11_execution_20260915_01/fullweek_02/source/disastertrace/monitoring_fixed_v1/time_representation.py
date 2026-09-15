"""A reversible time-encoding factor, with native products kept byte-identical."""

import copy
from datetime import datetime, timedelta, timezone

from .contracts import canonical
from .taf_tasks import messages

TIME_FIELDS = frozenset(
    {
        "as_of",
        "physical_start",
        "physical_end",
        "release_event_at",
        "issued_at",
        "available_at",
        "completed_at",
    }
)
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def encode_time(us):
    if type(us) is not int:
        raise TypeError("Time factor requires exact integer microseconds")
    return (
        (EPOCH + timedelta(microseconds=us))
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def decode_time(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() != timedelta(0):
        raise ValueError("Time representation must be UTC")
    delta = parsed - EPOCH
    return (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds


def transform(row, *, decode=False):
    row = copy.deepcopy(row)

    def visit(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in TIME_FIELDS and child is not None:
                    value[key] = decode_time(child) if decode else encode_time(child)
                else:
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(row)
    return row


def time_messages(task, encoding):
    original = messages(task)
    if encoding == "epoch_us":
        return original
    if encoding != "iso_utc":
        raise ValueError("Unregistered time encoding")
    row = task.view()
    changed = transform(row)
    if transform(changed, decode=True) != row:
        raise ValueError("Time representation loses information")
    system = original[0]["content"].replace(
        "Times are UTC microseconds.", "Times are ISO 8601 UTC strings."
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": canonical(changed)}]
