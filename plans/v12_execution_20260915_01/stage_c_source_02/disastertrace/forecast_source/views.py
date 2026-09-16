"""Keep every source line in both exports, including unmeasured nuisance information."""


def export(product, canonical_text):
    lines = canonical_text.splitlines()
    indices = {product["issue_line"], product["center_line"]}
    for row in product["forecasts"]:
        indices.add(row["forecast_line"])
        if row["wind_line"] is not None:
            indices.add(row["wind_line"])
    source = [{"line": i, "text": line} for i, line in enumerate(lines, 1)]
    identity = {
        k: product[k]
        for k in (
            "storm_id",
            "advisory_number",
            "issued_at",
            "center_at",
            "initialization_at",
            "available_at",
            "reference_kind",
        )
    }
    raw = {"identity": identity, "source_lines": source}
    normalized = {
        "identity": identity,
        "forecasts": product["forecasts"],
        "measurement_source_lines": [line for line in source if line["line"] in indices],
        "other_source_lines": [line for line in source if line["line"] not in indices],
    }
    if restore(normalized) != canonical_text:
        raise ValueError("normalized view lost source information")
    return {
        "raw": raw,
        "normalized": normalized,
        "information_equivalence": "all canonical source line bytes retained; structured atoms are derived",
        "intended_use": "source review exports; no representation-comparison inference performed",
    }


def restore(normalized):
    lines = normalized["measurement_source_lines"] + normalized["other_source_lines"]
    ordered = sorted(lines, key=lambda value: value["line"])
    if [line["line"] for line in ordered] != list(range(1, len(ordered) + 1)):
        raise ValueError("source view has missing or duplicate lines")
    return "\n".join(line["text"] for line in ordered) + "\n"
