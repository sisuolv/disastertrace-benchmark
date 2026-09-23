"""Conservative temporal/asset components and fully purged chronological roles."""

from itertools import pairwise

from .targets import canonical_hash


def validate_footprints(rows):
    seen = set()
    for row in rows:
        key = row["opportunity_id"]
        if not isinstance(key, str) or not key:
            raise ValueError("Invalid process opportunity identity")
        if key in seen:
            raise ValueError("Duplicate process opportunity")
        seen.add(key)
        start, stop = row["footprint_start"], row["footprint_end"]
        if type(start) is not int or type(stop) is not int or start >= stop:
            raise ValueError("Invalid complete input/reference footprint")
        assets = row.get("native_versions", [])
        if not isinstance(assets, list) or any(not isinstance(x, str) or not x for x in assets):
            raise ValueError("Invalid native version identities")


def process_components(rows, *, gap_us=0):
    """These are dependence blocks, not proven independent meteorological systems."""
    if type(gap_us) is not int or gap_us < 0:
        raise ValueError("Nonnegative grouping gap required")
    rows = list(rows)
    validate_footprints(rows)
    by_id = {r["opportunity_id"]: r for r in rows}
    if len(by_id) != len(rows):
        raise ValueError("Duplicate process opportunity")
    parent = {key: key for key in by_id}

    def find(key):
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    def join(a, b):
        parent[find(b)] = find(a)

    representative, end, assets = None, None, {}
    for row in sorted(rows, key=lambda r: (r["footprint_start"], r["opportunity_id"])):
        start, stop, key = row["footprint_start"], row["footprint_end"], row["opportunity_id"]
        if representative is not None and start < end + gap_us:
            join(representative, key)
            end = max(end, stop)
        else:
            representative, end = key, stop
        for asset in row.get("native_versions", []):
            if asset in assets:
                join(assets[asset], key)
            else:
                assets[asset] = key
    groups = {}
    for key in by_id:
        groups.setdefault(find(key), []).append(key)
    result = {}
    for values in groups.values():
        identity = "dependency-" + canonical_hash(sorted(values))[:20]
        for key in values:
            result[key] = identity
    return result


def chronological_roles(rows, intervals):
    """Require the entire footprint, including future reference, inside one role."""
    rows = list(rows)
    validate_footprints(rows)
    bounds = sorted((lo, hi, name) for name, (lo, hi) in intervals.items())
    if any(type(lo) is not int or type(hi) is not int or lo >= hi for lo, hi, _ in bounds) or any(
        a[1] > b[0] for a, b in pairwise(bounds)
    ):
        raise ValueError("Overlapping or invalid chronological role intervals")
    assignments = {}
    versions = {}
    for row in rows:
        roles = [
            name
            for lo, hi, name in bounds
            if lo <= row["footprint_start"] and row["footprint_end"] <= hi
        ]
        role = roles[0] if roles else "purged"
        assignments[row["opportunity_id"]] = role
        if role != "purged":
            for version in row.get("native_versions", []):
                previous = versions.setdefault(version, role)
                if previous != role:
                    raise ValueError("A native version crosses fitted/evaluated roles")
    return assignments
