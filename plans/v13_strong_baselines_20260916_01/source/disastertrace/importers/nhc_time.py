from __future__ import annotations

import re
from datetime import datetime, timezone

UTC_LINE = re.compile(
    r"\b(?P<hhmm>\d{4})\s+UTC\s+(?:MON|TUE|WED|THU|FRI|SAT|SUN)\s+"
    r"(?P<month>JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+"
    r"(?P<day>\d{1,2})\s+(?P<year>\d{4})\b",
    re.IGNORECASE,
)
MONTHS = {
    name: index
    for index, name in enumerate(
        ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"],
        start=1,
    )
}


def parse_nhc_issued_at(text: str) -> datetime:
    """Parse the explicit UTC issue line from an NHC advisory.

    Deliberately fail closed when no UTC line is found; do not silently coerce a
    timezone-naive local timestamp into `available_at`.
    """
    match = UTC_LINE.search(text)
    if not match:
        raise ValueError("no explicit NHC UTC issue line found")
    hhmm = match.group("hhmm")
    hour, minute = int(hhmm[:2]), int(hhmm[2:])
    return datetime(
        int(match.group("year")),
        MONTHS[match.group("month").upper()],
        int(match.group("day")),
        hour,
        minute,
        tzinfo=timezone.utc,
    )
