"""Separate post-run settlement; never imported or called by the model worker."""

from collections import Counter, defaultdict
from fractions import Fraction
from statistics import mean

from disastertrace.active_forecast.schema import parse_instant

from .policies import audit_trace
from .schema import Outcome


def average(values):
    return sum(values) / len(values)


def score(episode, outcome, trace):
    outcome = Outcome.model_validate(outcome)
    if (outcome.episode_id, outcome.entity, outcome.variable, outcome.unit, outcome.valid_at) != (
        episode.id,
        episode.entity,
        episode.variable,
        episode.unit,
        episode.target_at,
    ):
        raise ValueError("outcome does not match the registered target")
    audit_trace(episode, trace)
    initial = next(a for a in episode.artifacts if a.id == episode.initial_artifact_id)
    checkpoints = []
    for checkpoint in episode.checkpoints:
        commits = [c for c in trace["commits"] if parse_instant(c["at"]) <= checkpoint]
        current = commits[-1] if commits else None
        prediction = Fraction(str(current["value"])) if current else average(initial.values)
        forecasts = [
            a for a in episode.artifacts if a.kind == "forecast" and a.release_at <= checkpoint
        ]
        official = average(max(forecasts, key=lambda a: a.issued_at).values)
        row = {
            "at": checkpoint.isoformat(),
            "prediction": float(prediction),
            "latest_professional_prediction": float(official),
            "fallback_to_initial": current is None,
            "submission_at_this_checkpoint": any(
                parse_instant(c["at"]) == checkpoint for c in commits
            ),
            "outcome_status": outcome.status,
            "absolute_error": None,
            "professional_absolute_error": None,
            "brier_diagnostic": None,
        }
        if outcome.value is not None:
            row.update(
                absolute_error=float(abs(prediction - outcome.value)),
                professional_absolute_error=float(abs(official - outcome.value)),
            )
            if episode.threshold is not None:
                y = int(outcome.value >= episode.threshold)
                p = (
                    Fraction(str(current["probability"]))
                    if current and current["probability"] is not None
                    else Fraction(prediction >= episode.threshold)
                )
                row.update(
                    binary_outcome=y,
                    probability=float(p),
                    brier_diagnostic=float((p - y) ** 2),
                    point_threshold_error=int((prediction >= episode.threshold) != bool(y)),
                    probability_fallback=current is None or current["probability"] is None,
                    decision_scenario_losses={
                        str(rho): float(rho * int(p >= rho) + y * int(p < rho))
                        for rho in (Fraction(1, 10), Fraction(1, 4), Fraction(1, 2))
                    },
                )
        checkpoints.append(row)
    return {
        "episode_id": episode.id,
        "group": episode.group,
        "family": episode.family,
        "unit": episode.unit,
        "scenario": episode.scenario,
        "budget": trace["budget"],
        "policy": trace["policy"],
        "fusion": trace["fusion"],
        "backend": trace["backend"],
        "spent": trace["spent"],
        "queries": len(trace["receipts"]),
        "serialized_delivery_bytes": sum(r.get("bytes", 0) for r in trace["receipts"]),
        "invalid_events": sum(e["kind"] == "invalid" for e in trace["events"]),
        "pending_at_deadline": sum(r["status"] == "pending" for r in trace["receipts"]),
        "model_calls": len(trace["calls"]),
        "model_input_tokens": sum(c.get("input_tokens", 0) for c in trace["calls"]),
        "model_output_tokens": sum(c.get("output_tokens", 0) for c in trace["calls"]),
        "model_seconds": sum(c.get("seconds", 0) for c in trace["calls"]),
        "outcome_status": outcome.status,
        "checkpoints": checkpoints,
    }


def aggregate(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[
            row["family"],
            row["scenario"],
            row["budget"],
            row["policy"],
            row["fusion"],
            row["backend"],
        ].append(row)
    reports = []
    for key, values in sorted(grouped.items()):
        group_errors, group_official = defaultdict(list), defaultdict(list)
        for row in values:
            for cp in row["checkpoints"]:
                if cp["absolute_error"] is not None:
                    group_errors[row["group"]].append(cp["absolute_error"])
                    group_official[row["group"]].append(cp["professional_absolute_error"])
        mae = mean(mean(v) for v in group_errors.values()) if group_errors else None
        official = mean(mean(v) for v in group_official.values()) if group_official else None
        reports.append(
            {
                "family": key[0],
                "scenario": key[1],
                "budget": key[2],
                "policy": key[3],
                "fusion": key[4],
                "backend": key[5],
                "unit": values[0]["unit"],
                "targets": len(values),
                "groups": len({r["group"] for r in values}),
                "settled_targets": sum(r["outcome_status"] != "unresolved" for r in values),
                "outcome_status": dict(Counter(r["outcome_status"] for r in values)),
                "scheduled_checkpoints": sum(len(r["checkpoints"]) for r in values),
                "missing_checkpoint_submissions": sum(
                    not c["submission_at_this_checkpoint"] for r in values for c in r["checkpoints"]
                ),
                "group_macro_mae": mae,
                "group_macro_latest_professional_mae": official,
                "mae_gain_over_latest_professional": None if mae is None else official - mae,
                "mean_queries": mean(r["queries"] for r in values),
                "mean_delivery_bytes": mean(r["serialized_delivery_bytes"] for r in values),
                "invalid_events": sum(r["invalid_events"] for r in values),
                "model_calls": sum(r["model_calls"] for r in values),
                "model_input_tokens": sum(r["model_input_tokens"] for r in values),
                "model_output_tokens": sum(r["model_output_tokens"] for r in values),
                "model_seconds": sum(r["model_seconds"] for r in values),
            }
        )
    return reports
