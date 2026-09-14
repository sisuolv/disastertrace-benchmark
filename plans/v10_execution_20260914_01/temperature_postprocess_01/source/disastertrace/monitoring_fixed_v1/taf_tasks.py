"""Dedicated native-product E contracts; these heads submit no future probability."""

import json
from dataclasses import dataclass

from ..monitoring_v1.providers.aviation import parse_taf
from ..monitoring_v1.providers.versions import latest_issuance
from .contracts import Target, canonical, fingerprint, require_fields, timestamp
from .heads import _reject_constant, _unique_object
from .support_bridge import iso

VERSION = "taf_current_product_E.v1"
STATUSES = {"resolved", "unknown", "unsupported", "conflict"}
COMMON = (
    "Use only the disclosed complete native TAF products. Times are UTC microseconds. "
    "This is an E task about the provided products, not a future-weather probability. "
    "The current version has the latest native issued_at among the disclosed products; "
    "retain all equivalent mirrors at that issuance. Rebuild from the current version, "
    "do not intersect a superseded product with its replacement. An inconsistent pair "
    "at the same latest issuance is conflict. Unknown means no disclosed product; "
    "unsupported means the declared native parser contract cannot interpret the current "
    "product. Do not treat unsupported syntax as evidence of noncoverage. "
    "Return JSON only, no examples or default answers. status is one of the JSON "
    "strings resolved, unknown, unsupported, conflict. current_source_ids is an array "
    "of disclosed source IDs at the latest issuance, or empty when none is disclosed. "
)
SYSTEMS = {
    "coverage": COMMON
    + (
        "Use the fixed target interval [physical_start,physical_end). Native TAF validity "
        "[valid_start,valid_end) determines full, partial, or none coverage. TEMPO/PROB "
        "do not extend that validity. NIL/CNL have none coverage. The exact output fields "
        "are status, coverage, current_source_ids; coverage is full, partial, none when "
        "resolved and null otherwise."
    ),
    "revision": COMMON
    + (
        "The exact output fields are status, current_source_ids, superseded_source_ids. "
        "superseded_source_ids lists every disclosed source with strictly older issuance. "
        "A newer CNL or shorter validity supersedes an older covering forecast; it does "
        "not revive the old product. No product or future outcome outside this input exists "
        "for purposes of this task."
    ),
}


@dataclass(frozen=True)
class TafEvidenceTask:
    _json: str

    def __post_init__(self):
        row = self.view()
        require_fields(
            row, "schema task_id kind target as_of availability_basis products", "TAF E task"
        )
        if (
            row["schema"] != "disastertrace.taf_E_task.v1"
            or not row["task_id"]
            or row["kind"] not in SYSTEMS
        ):
            raise ValueError("Unknown TAF task contract")
        target = Target(**row["target"])
        if not target.entity.startswith("station:") or target.support_kind != "interval":
            raise ValueError("Native TAF requires a fixed station interval")
        timestamp(row["as_of"])
        target.check_cutoff(row["as_of"])
        if row["availability_basis"] not in {
            "declared_archive_scenario",
            "observed_first_seen",
            "documented_historical_release",
        }:
            raise ValueError("Explicit source-availability basis required")
        if not isinstance(row["products"], list):
            raise TypeError("Native products must be a list")
        seen = set()
        for p in row["products"]:
            require_fields(
                p, "source_id station raw issued_at available_at completed_at", "native TAF"
            )
            if (
                not p["source_id"]
                or p["source_id"] in seen
                or p["station"] != target.entity.removeprefix("station:")
            ):
                raise ValueError("Duplicate source or incorrect station support")
            if type(p["raw"]) is not str or not p["raw"]:
                raise ValueError("Complete native text required")
            for field in ("issued_at", "available_at", "completed_at"):
                timestamp(p[field])
            if not p["issued_at"] <= p["available_at"] <= p["completed_at"] <= row["as_of"]:
                raise ValueError("Undisclosed or future native source")
            seen.add(p["source_id"])

    @classmethod
    def freeze(cls, row):
        return cls(canonical(row))

    def view(self):
        return json.loads(self._json)

    @property
    def task_hash(self):
        return fingerprint(self.view())


def _semantics(product):
    return {
        "station": product.station,
        "status": product.status,
        "valid_start": product.valid_start,
        "valid_end": product.valid_end,
        "amendment_scheduling": product.amendment_scheduling,
        "clauses": [
            {
                "operator": c.operator,
                "start": c.start,
                "end": c.end,
                "fields": c.fields,
                "native_probability": c.native_probability,
            }
            for c in product.clauses
        ],
    }


def evaluate(task):
    """Evaluator-only reconstruction, never added to model messages."""
    row = task.view()
    current, older = latest_issuance(row["products"])
    previous = sorted(p["source_id"] for p in older)
    errors, meanings, products = {}, {}, []
    for p in current:
        try:
            native = parse_taf(p["raw"], station=p["station"], archive_issue=iso(p["issued_at"]))
            semantic = _semantics(native)
            meanings[fingerprint(semantic)] = semantic
            products.append(native)
        except (ValueError, TypeError) as exc:
            errors[p["source_id"]] = str(exc)
    status = (
        "unknown"
        if not current
        else "unsupported"
        if errors
        else "conflict"
        if len(meanings) != 1
        else "resolved"
    )
    answer = {"status": status, "current_source_ids": sorted(p["source_id"] for p in current)}
    detail = {"parser_errors": errors, "superseded_source_ids": previous}
    if row["kind"] == "coverage":
        coverage = None
        if status == "resolved":
            native, target = products[0], Target(**row["target"])
            overlap = (
                0
                if native.status != "active"
                else max(
                    0,
                    min(target.physical_end, native.valid_end)
                    - max(target.physical_start, native.valid_start),
                )
            )
            coverage = (
                "none"
                if overlap == 0
                else "full"
                if overlap == target.physical_end - target.physical_start
                else "partial"
            )
            detail["coverage_fraction"] = overlap / (target.physical_end - target.physical_start)
            detail["native_status"] = native.status
            if coverage == "full":
                detail["projection"] = native.project(target.physical_start, target.physical_end)
        answer["coverage"] = coverage
    else:
        answer["superseded_source_ids"] = previous
    return {
        "task_hash": task.task_hash,
        "rule_version": VERSION,
        "answer": answer,
        "diagnostics": detail,
        "reference_kind": "product_label",
        "support_assumption": "product_exact",
        "visible_information_scope": "provided_common_native_products",
        "future_forecast_submitted": False,
    }


def messages(task):
    return [
        {"role": "system", "content": SYSTEMS[task.view()["kind"]]},
        {"role": "user", "content": canonical(task.view())},
    ]


def parse_answer(raw, task):
    row = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    kind = task.view()["kind"]
    last = "coverage" if kind == "coverage" else "superseded_source_ids"
    require_fields(row, "status current_source_ids " + last, "TAF E answer")
    if type(row["status"]) is not str or row["status"] not in STATUSES:
        raise ValueError("Invalid TAF answer status")
    allowed = {p["source_id"] for p in task.view()["products"]}
    for field in (
        ("current_source_ids",)
        if kind == "coverage"
        else ("current_source_ids", "superseded_source_ids")
    ):
        ids = row[field]
        if (
            not isinstance(ids, list)
            or any(type(i) is not str for i in ids)
            or len(set(ids)) != len(ids)
            or not set(ids) <= allowed
        ):
            raise ValueError("Answer cites duplicate or undisclosed sources")
        row[field] = sorted(ids)
    if kind == "coverage":
        if row["status"] == "resolved":
            if type(row["coverage"]) is not str or row["coverage"] not in {
                "full",
                "partial",
                "none",
            }:
                raise ValueError("Resolved coverage must be a native-window category")
        elif row["coverage"] is not None:
            raise ValueError("Unresolved coverage must be null")
    return row


def score_answer(raw, task):
    reference = evaluate(task)["answer"]
    try:
        answer = parse_answer(raw, task)
    except (ValueError, TypeError) as exc:
        return {"correct": False, "valid": False, "error": str(exc), "task_hash": task.task_hash}
    return {
        "correct": answer == reference,
        "valid": True,
        "task_hash": task.task_hash,
        "field_correct": {k: answer[k] == v for k, v in reference.items()},
    }
