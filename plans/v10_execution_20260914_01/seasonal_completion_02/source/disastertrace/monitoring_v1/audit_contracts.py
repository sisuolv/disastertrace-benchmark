"""Exact registered coverage checks; observed files cannot define the denominator."""


def require_exact_ids(expected, observed, scope):
    expected, observed = list(expected), list(observed)
    if len(expected) != len(set(expected)) or len(observed) != len(set(observed)):
        raise ValueError(f"Duplicate coverage identity in {scope}")
    missing, extra = set(expected) - set(observed), set(observed) - set(expected)
    if missing or extra:
        raise ValueError(f"Incomplete coverage in {scope}: missing={sorted(missing)}, extra={sorted(extra)}")
    return len(expected)
