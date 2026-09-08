from __future__ import annotations

import copy
import math
import re
from datetime import datetime, timedelta, timezone

from .common import canonical, fingerprint, strict_json
from .methods import DEFAULT_METHOD, method_contract, request_method, validate_method

FIELDS = (
    "maximum_wind_mph",
    "latitude_deg",
    "longitude_deg",
    "minimum_pressure_mb",
    "port_reopening_time",
)
POLICY = {
    "kind": "research_rule_not_operational_advice",
    "variable": "maximum_wind_mph",
    "threshold": 100,
    "known_at_or_above": "prepare",
    "known_below": "monitor",
    "unknown": "request_evidence",
}


def aware(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() is None:
        raise ValueError("timezone-aware timestamp required")
    return parsed.astimezone(timezone.utc)


def build_episodes(records: list[dict]) -> list[dict]:
    """Use unchanged official reports with explicitly controlled delivery schedules."""
    ordered = sorted(records, key=lambda item: aware(item["issued_at"]))
    if len(ordered) != 3 or len({item["storm_id"] for item in ordered}) != 1:
        raise ValueError("the first-work-package example requires three reports from one storm")
    if len({item["issued_at"] for item in ordered}) != 3:
        raise ValueError("ambiguous report times")
    first, second, third = ordered
    origins = {item.get("provenance", {}).get("source_origin") for item in ordered}
    if len(origins) != 1 or not origins <= {"official_record", "synthetic_record"}:
        raise ValueError("a homogeneous, explicit source origin is required")
    origin = next(iter(origins))
    if aware(third["issued_at"]) <= aware(second["issued_at"]) + timedelta(minutes=1):
        raise ValueError("the repeat checkpoint must precede the third report")
    checkpoints = [
        {
            "checkpoint_id": "c0",
            "at": (aware(first["issued_at"]) - timedelta(minutes=1)).isoformat(),
            "arrivals": [],
        },
        {"checkpoint_id": "c1", "at": first["issued_at"], "arrivals": [first["record_id"]]},
        {"checkpoint_id": "c2", "at": second["issued_at"], "arrivals": [second["record_id"]]},
        {
            "checkpoint_id": "c3",
            "at": (aware(second["issued_at"]) + timedelta(minutes=1)).isoformat(),
            "arrivals": [first["record_id"]],
        },
        {"checkpoint_id": "c4", "at": third["issued_at"], "arrivals": [third["record_id"]]},
    ]
    base = {
        "schema_version": "automated_episode_v1",
        "episode_id": first["storm_id"].lower() + ":controlled:base",
        "group_id": first["storm_id"],
        "split": "development_only",
        "source_origin": origin,
        "gold_origin": "generated_by_spec",
        "fact_origin": "derived_from_source" if origin == "official_record" else "synthetic",
        "schedule_origin": "controlled_release",
        "content_edits": False,
        "task_semantics": "latest_available_report_not_same_valid_time_forecast_revision",
        "required_fields": list(FIELDS),
        "policy": dict(POLICY),
        "records": ordered,
        "checkpoints": checkpoints,
    }
    delayed = copy.deepcopy(base)
    delayed["episode_id"] = first["storm_id"].lower() + ":controlled:delay"
    delayed["checkpoints"][2]["arrivals"] = []
    delayed["checkpoints"][3]["arrivals"] = [second["record_id"], first["record_id"]]
    for episode in (base, delayed):
        validate_episode(episode)
    return [base, delayed]


def validate_episode(episode: dict) -> None:
    if not episode["checkpoints"]:
        raise ValueError("episode must contain at least one checkpoint")
    if tuple(episode["required_fields"]) != FIELDS or episode["policy"] != POLICY:
        raise ValueError("unsupported task contract")
    records = episode["records"]
    record_map = {record["record_id"]: record for record in records}
    if len(record_map) != len(records):
        raise ValueError("duplicate record ID")
    if any(record["storm_id"] != episode["group_id"] for record in records):
        raise ValueError("mixed storm scope")
    if len({aware(record["issued_at"]) for record in records}) != len(records):
        raise ValueError("ambiguous report timestamps")
    for record in records:
        fields = record["fields"]
        for name in FIELDS[:-1]:
            value = fields[name]
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError("finite numeric source field required")
            evidence = record["field_evidence"][name]
            lines = record["raw_text"].splitlines()
            start, end = evidence["line_start"], evidence["line_end"]
            if not 1 <= start <= end <= len(lines):
                raise ValueError("source locator outside record")
            if "\n".join(lines[start - 1 : end]) != evidence["text"]:
                raise ValueError("source locator/text mismatch")
    previous_time = None
    ids = set()
    for checkpoint in episode["checkpoints"]:
        at = aware(checkpoint["at"])
        if checkpoint["checkpoint_id"] in ids or (
            previous_time is not None and at <= previous_time
        ):
            raise ValueError("duplicate checkpoint or non-increasing clock")
        ids.add(checkpoint["checkpoint_id"])
        previous_time = at
        for record_id in checkpoint["arrivals"]:
            if record_id not in record_map:
                raise ValueError("unknown arrival")
            if aware(record_map[record_id]["issued_at"]) > at:
                raise ValueError("report cannot arrive before its issue time")


def available_records(episode: dict, checkpoint_id: str) -> list[dict]:
    mapping = {record["record_id"]: record for record in episode["records"]}
    delivered = []
    for checkpoint in episode["checkpoints"]:
        delivered.extend(mapping[item] for item in checkpoint["arrivals"])
        if checkpoint["checkpoint_id"] == checkpoint_id:
            return delivered
    raise ValueError("unknown checkpoint")


def reference_at(episode: dict, checkpoint_id: str) -> dict:
    # Gold uses admitted typed fields; the diagnostic backend separately parses visible text.
    visible = available_records(episode, checkpoint_id)
    latest = max(visible, key=lambda item: aware(item["issued_at"])) if visible else None
    state = {}
    for field in FIELDS:
        if latest is None or field not in latest["fields"]:
            state[field] = {"status": "unknown", "value": None, "evidence": []}
        else:
            state[field] = {
                "status": "known",
                "value": latest["fields"][field],
                "evidence": [
                    {
                        "record_id": latest["record_id"],
                        "line": latest["field_evidence"][field]["line_start"],
                    }
                ],
            }
    value = state["maximum_wind_mph"]["value"]
    action = (
        "request_evidence"
        if value is None
        else ("prepare" if value >= POLICY["threshold"] else "monitor")
    )
    return {"state": state, "action": action}


def render_request(
    episode: dict,
    checkpoint_id: str,
    previous: dict | None,
    *,
    method: str = DEFAULT_METHOD,
    history: list[dict] | None = None,
) -> dict:
    method = validate_method(method)
    checkpoint = next(
        item for item in episode["checkpoints"] if item["checkpoint_id"] == checkpoint_id
    )
    evidence = []
    for index, record in enumerate(available_records(episode, checkpoint_id)):
        evidence.append(
            {
                "delivery_index": index,
                "record_id": record["record_id"],
                "issued_at": record["issued_at"],
                "text": "\n".join(
                    f"{n}: {line}" for n, line in enumerate(record["raw_text"].splitlines(), 1)
                ),
            }
        )
    # Explicit fields prevent full records, parsed labels, or future schedules entering a request.
    request = {
        "protocol": "disastertrace_text_v1",
        "instruction": (
            "Return JSON with exactly state and action. For each required field use "
            "{status: known|unknown, value: number|null, evidence: [{record_id, line}]}. "
            "Answer from the latest issued report actually provided, citing its numbered lines. "
            "These are successive reported observations, not revisions at one forecast valid time. "
            "Missing information is unknown; do not infer port reopening from storm intensity. "
            "Apply the supplied research rule, which is not operational advice."
        ),
        "checkpoint_time": checkpoint["at"],
        "required_fields": list(FIELDS),
        "policy": dict(POLICY),
        "evidence": evidence,
    }
    if method == DEFAULT_METHOD:
        request["previous_state"] = copy.deepcopy(previous)
    else:
        request["method"] = method
        if method == "answer_history":
            if history is None:
                history = []
            if not isinstance(history, list):
                raise ValueError("answer history must be a list of accepted decisions")
            try:
                request["answer_history"] = [parse_decision(canonical(item)) for item in history]
            except (ValueError, TypeError, KeyError):
                raise ValueError(
                    "answer history must contain only accepted decision objects"
                ) from None
    return request


def parse_decision(raw: str) -> dict:
    decision = strict_json(raw)
    if not isinstance(decision, dict) or set(decision) != {"state", "action"}:
        raise ValueError("decision must contain exactly state and action")
    if decision["action"] not in {"monitor", "prepare", "request_evidence"}:
        raise ValueError("invalid action")
    state = decision["state"]
    if not isinstance(state, dict) or set(state) != set(FIELDS):
        raise ValueError("exact required state fields needed")
    for item in state.values():
        if not isinstance(item, dict) or set(item) != {"status", "value", "evidence"}:
            raise ValueError("invalid slot structure")
        value = item["value"]
        if item["status"] == "unknown":
            if value is not None or item["evidence"] != []:
                raise ValueError("unknown requires null and no asserted support")
        elif item["status"] == "known":
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError("known requires a finite numeric value")
        else:
            raise ValueError("invalid slot status")
        if not isinstance(item["evidence"], list):
            raise ValueError("evidence list required")
        for ref in item["evidence"]:
            if not isinstance(ref, dict) or set(ref) != {"record_id", "line"}:
                raise ValueError("invalid citation")
            if (
                not isinstance(ref["record_id"], str)
                or type(ref["line"]) is not int
                or ref["line"] < 1
            ):
                raise ValueError("invalid citation type")
    return decision


def diagnostic_response(request: dict, backend: str) -> str:
    """An explicitly non-LLM text parser, plus intentionally defective controls."""
    unknown = {name: {"status": "unknown", "value": None, "evidence": []} for name in FIELDS}
    if backend == "no-update":
        method = request_method(request)
        carrier = None
        if method == DEFAULT_METHOD:
            carrier = request["previous_state"]
        elif method == "answer_history" and request["answer_history"]:
            carrier = request["answer_history"][-1]
        return canonical(carrier or {"state": unknown, "action": "request_evidence"})
    if backend not in {"rule", "last-arrival"}:
        raise ValueError("unknown diagnostic backend")
    evidence = request["evidence"]
    if not evidence:
        return canonical({"state": unknown, "action": "request_evidence"})
    selected = (
        max(evidence, key=lambda item: aware(item["issued_at"]))
        if backend == "rule"
        else evidence[-1]
    )
    patterns = {
        "maximum_wind_mph": r"MAXIMUM SUSTAINED WINDS\.\.\.(\d+) MPH",
        "minimum_pressure_mb": r"MINIMUM CENTRAL PRESSURE\.\.\.(\d+) MB",
        "latitude_deg": r"LOCATION\.\.\.(\d+(?:\.\d+)?)([NS])",
        "longitude_deg": r"LOCATION\.\.\.\d+(?:\.\d+)?[NS]\s+(\d+(?:\.\d+)?)([EW])",
    }
    state = unknown
    for name, pattern in patterns.items():
        for line in selected["text"].splitlines():
            match = re.search(pattern, line)
            if match:
                value = float(match[1])
                if name in {"latitude_deg", "longitude_deg"} and match[2] in {"S", "W"}:
                    value = -value
                state[name] = {
                    "status": "known",
                    "value": value,
                    "evidence": [
                        {"record_id": selected["record_id"], "line": int(line.split(":", 1)[0])}
                    ],
                }
                break
    value = state["maximum_wind_mph"]["value"]
    action = (
        "request_evidence"
        if value is None
        else ("prepare" if value >= request["policy"]["threshold"] else "monitor")
    )
    return canonical({"state": state, "action": action})


def run_episode(
    episode: dict,
    backend: str,
    *,
    max_queries: int,
    predictions: dict | None = None,
    method: str = DEFAULT_METHOD,
) -> list[dict]:
    method = validate_method(method)
    validate_episode(episode)
    if type(max_queries) is not int or max_queries < 0:
        raise ValueError("query budget must be a nonnegative integer")
    if backend == "submissions" and predictions is None:
        raise ValueError("submissions backend requires prediction records")
    rows, previous = [], None
    history = []
    for index, checkpoint in enumerate(episode["checkpoints"]):
        request = render_request(
            episode, checkpoint["checkpoint_id"], previous, method=method, history=history
        )
        status, raw, error = "ok", "", None
        if index >= max_queries:
            status, error = "budget_exhausted", "logical query budget exhausted"
        else:
            if backend == "submissions":
                key = (episode["episode_id"], checkpoint["checkpoint_id"])
                prediction = predictions.get(key)
                if prediction is None:
                    status, error = "missing", "no submitted response"
                else:
                    raw = prediction["raw_response"]
            else:
                raw = diagnostic_response(request, backend)
            if status == "ok":
                try:
                    previous = parse_decision(raw)
                    history.append(copy.deepcopy(previous))
                except (ValueError, TypeError, KeyError) as exc:
                    status, error = "invalid", str(exc)
        rows.append(
            {
                "episode_id": episode["episode_id"],
                "checkpoint_id": checkpoint["checkpoint_id"],
                "backend": backend,
                "method": method,
                "model_kind": "submitted_unverified"
                if backend == "submissions"
                else "diagnostic_program",
                "eligible_for_llm_leaderboard": False,
                "request": request,
                "request_hash": fingerprint(request),
                "raw_response": raw,
                "status": status,
                "error": error,
                "state_after": copy.deepcopy(previous),
                "logical_queries": int(index < max_queries),
                "provider_requests": 0,
            }
        )
    return rows


def score_dynamic(episodes: list[dict], traces: list[dict]) -> dict:
    if not episodes or len({episode["episode_id"] for episode in episodes}) != len(episodes):
        raise ValueError("a nonempty set of unique episodes is required")
    expected_keys = {
        (episode["episode_id"], cp["checkpoint_id"])
        for episode in episodes
        for cp in episode["checkpoints"]
    }
    indexed = {}
    methods = {validate_method(row.get("method", DEFAULT_METHOD)) for row in traces}
    if len(methods) > 1:
        raise ValueError("mixed declared methods cannot be scored as one run")
    method = next(iter(methods), DEFAULT_METHOD)
    for row in traces:
        if request_method(row["request"]) != method:
            raise ValueError("trace method and request declaration mismatch")
        status = row["status"]
        if status not in {"ok", "invalid", "missing", "budget_exhausted"}:
            raise ValueError("unknown trace status")
        expected_queries = int(status != "budget_exhausted")
        if type(row["logical_queries"]) is not int or row["logical_queries"] != expected_queries:
            raise ValueError("trace logical query accounting mismatch")
        if type(row["provider_requests"]) is not int or row["provider_requests"] != 0:
            raise ValueError("offline trace must have zero provider requests")
        if status in {"missing", "budget_exhausted"} and row["raw_response"] != "":
            raise ValueError("missing or exhausted trace cannot contain a response")
        key = (row["episode_id"], row["checkpoint_id"])
        if key not in expected_keys or key in indexed:
            raise ValueError("unknown or duplicate trace checkpoint")
        indexed[key] = row
    per_checkpoint = []
    totals = {
        name: 0
        for name in (
            "attempts",
            "valid",
            "value_correct",
            "grounded_correct",
            "slots",
            "action_correct",
            "unknown_correct",
            "unknown_required",
            "known_answered",
            "known_required",
            "required_changes",
            "correct_changes",
            "preserve_eligible",
            "preserve_correct",
        )
    }
    for episode in episodes:
        validate_episode(episode)
        previous, previous_gold = None, None
        history = []
        for checkpoint in episode["checkpoints"]:
            key = (episode["episode_id"], checkpoint["checkpoint_id"])
            row = indexed.get(key)
            reference = reference_at(episode, checkpoint["checkpoint_id"])
            decision = None
            status = "missing" if row is None else row["status"]
            if row is not None:
                actual_request = render_request(
                    episode, checkpoint["checkpoint_id"], previous, method=method, history=history
                )
                if row["request"] != actual_request or row["request_hash"] != fingerprint(
                    actual_request
                ):
                    raise ValueError("trace input/history mismatch")
                if status == "ok":
                    try:
                        decision = parse_decision(row["raw_response"])
                    except (ValueError, KeyError, TypeError):
                        status = "invalid"
                expected_state = decision if decision is not None else previous
                if row["state_after"] != expected_state:
                    raise ValueError("trace silently changed model state")
            score = {
                "episode_id": key[0],
                "checkpoint_id": key[1],
                "status": status,
                "method": method,
                "slots": {},
            }
            totals["attempts"] += 1
            totals["valid"] += int(decision is not None)
            for name in FIELDS:
                gold = reference["state"][name]
                submitted = decision["state"][name] if decision else None
                value_ok = (
                    submitted is not None
                    and submitted["status"] == gold["status"]
                    and submitted["value"] == gold["value"]
                )
                support_ok = value_ok and (
                    gold["status"] == "unknown"
                    or (
                        bool(submitted["evidence"])
                        and all(ref in gold["evidence"] for ref in submitted["evidence"])
                    )
                )
                totals["slots"] += 1
                totals["value_correct"] += int(value_ok)
                totals["grounded_correct"] += int(support_ok)
                if gold["status"] == "unknown":
                    totals["unknown_required"] += 1
                    totals["unknown_correct"] += int(value_ok)
                else:
                    totals["known_required"] += 1
                    totals["known_answered"] += int(
                        submitted is not None and submitted["status"] == "known"
                    )
                if previous is not None and previous_gold is not None:
                    before = previous["state"][name]
                    before_gold = previous_gold["state"][name]
                    semantic_before = (before["status"], before["value"])
                    semantic_gold = (gold["status"], gold["value"])
                    if semantic_before != semantic_gold:
                        totals["required_changes"] += 1
                        totals["correct_changes"] += int(support_ok)
                    elif semantic_before == (before_gold["status"], before_gold["value"]):
                        totals["preserve_eligible"] += 1
                        totals["preserve_correct"] += int(value_ok)
                score["slots"][name] = {"value_correct": value_ok, "grounded_correct": support_ok}
            score["action_correct"] = (
                decision is not None and decision["action"] == reference["action"]
            )
            score["all_correct"] = score["action_correct"] and all(
                value["grounded_correct"] for value in score["slots"].values()
            )
            totals["action_correct"] += int(score["action_correct"])
            if decision is not None:
                previous = decision
                history.append(copy.deepcopy(decision))
            previous_gold = reference
            per_checkpoint.append(score)

    def rate(numerator: str, denominator: str) -> dict:
        n, d = totals[numerator], totals[denominator]
        return {"numerator": n, "denominator": d, "value": n / d if d else None}

    results = {
        "schema_version": "dynamic_score_v1",
        "method": method,
        "methods": [method],
        "method_contract": method_contract(method),
        "schedule_origin": "controlled_release",
        "gold_origins": sorted({ep["gold_origin"] for ep in episodes}),
        "source_origins": sorted({ep["source_origin"] for ep in episodes}),
        "independent_event_groups": len({ep["group_id"] for ep in episodes}),
        "model_kinds": sorted({row["model_kind"] for row in traces}),
        "eligible_for_llm_leaderboard": False,
        "metrics": {
            name: rate(n, d)
            for name, n, d in [
                ("schema_success", "valid", "attempts"),
                ("state_accuracy", "value_correct", "slots"),
                ("grounded_state", "grounded_correct", "slots"),
                ("action_accuracy", "action_correct", "attempts"),
                ("unknown_accuracy", "unknown_correct", "unknown_required"),
                ("known_answer_coverage", "known_answered", "known_required"),
                ("required_change_success", "correct_changes", "required_changes"),
                ("preservation", "preserve_correct", "preserve_eligible"),
            ]
        },
        "per_checkpoint": per_checkpoint,
        "status_counts": {
            status: sum(row["status"] == status for row in per_checkpoint)
            for status in {row["status"] for row in per_checkpoint}
        },
    }
    return results
