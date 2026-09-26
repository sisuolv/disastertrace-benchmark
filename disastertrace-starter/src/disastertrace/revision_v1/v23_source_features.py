"""Pure source-content features and fail-closed contracts for v23-B.

The helpers in this module are deliberately independent of outcome labels and
of filesystem access.  They are used by the guarded D1 roster builder and by
synthetic tests before any real weather body is opened.
"""

from __future__ import annotations

import calendar
import os
import subprocess
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _bound(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str):
        if value in {"+inf", "inf", "infinity"}:
            return float("inf")
        if value in {"-inf", "-infinity"}:
            return float("-inf")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def metar_event_flag(interval: Mapping[str, Any] | None, *, threshold_m: float = 5000.0) -> int | None:
    """Classify a visibility interval under the frozen ``< threshold`` event."""
    if not interval:
        return None
    lower, upper = _bound(interval.get("lower")), _bound(interval.get("upper"))
    if lower is None or upper is None or lower > upper:
        return None
    if upper < threshold_m:
        return 1
    if lower >= threshold_m:
        return 0
    return None


def _state_interval(state: Mapping[str, Any]) -> Mapping[str, Any] | None:
    value = state.get("visibility")
    return value if isinstance(value, Mapping) else None


def taf_event_flag(projected: Mapping[str, Any] | None, *, threshold_m: float = 5000.0) -> int | None:
    """Classify a projected TAF target window using the preregistered rules.

    A low prevailing state across every segment is event=1.  A high prevailing
    state across every segment is event=0 only when no conditional group can
    introduce a low state.  Mixed, crossing, missing, or uncovered content is
    unknown.
    """
    if not projected or not projected.get("segments"):
        return None
    prevailing_flags: list[int | None] = []
    conditional_flags: list[int | None] = []
    for segment in projected["segments"]:
        states = segment.get("prevailing") or []
        if not states:
            return None
        for state in states:
            prevailing_flags.append(metar_event_flag(_state_interval(state), threshold_m=threshold_m))
        for group in segment.get("conditional") or []:
            for state in group.get("states") or []:
                conditional_flags.append(metar_event_flag(_state_interval(state), threshold_m=threshold_m))
    if not prevailing_flags or any(flag is None for flag in prevailing_flags):
        return None
    if all(flag == 1 for flag in prevailing_flags):
        return 1
    if all(flag == 0 for flag in prevailing_flags):
        if any(flag != 0 for flag in conditional_flags):
            return None
        return 0
    return None


def _interval_summary(intervals: Sequence[Mapping[str, Any]]) -> dict[str, float | None]:
    lowers = [_bound(item.get("lower")) for item in intervals]
    uppers = [_bound(item.get("upper")) for item in intervals]
    lowers = [value for value in lowers if value is not None]
    uppers = [value for value in uppers if value is not None]
    return {
        "lower_min": min(lowers) if lowers else None,
        "upper_max": max(uppers) if uppers else None,
    }


def taf_content_features(product: Any, start_us: int, end_us: int, *, threshold_m: float = 5000.0) -> dict[str, Any]:
    """Project one parsed ``TafProduct`` and expose label-free content features."""
    try:
        projected = product.project(start_us, end_us)
    except (TypeError, ValueError):
        return {"coverage_status": "uncovered_or_invalid", "event_flag": None}
    prevailing = []
    conditional = []
    for segment in projected.get("segments", []):
        prevailing.extend(
            interval for state in segment.get("prevailing", [])
            if (interval := _state_interval(state)) is not None
        )
        for group in segment.get("conditional", []):
            conditional.extend(
                interval for state in group.get("states", [])
                if (interval := _state_interval(state)) is not None
            )
    return {
        "coverage_status": "covered" if projected.get("segments") else "uncovered_or_invalid",
        "event_flag": taf_event_flag(projected, threshold_m=threshold_m),
        "prevailing": _interval_summary(prevailing),
        "conditional": _interval_summary(conditional),
        "segment_count": len(projected.get("segments", [])),
        "conditional_group_count": sum(len(segment.get("conditional", [])) for segment in projected.get("segments", [])),
    }


def latest_visible_metar(observations: Sequence[Any], cutoff_us: int, *, available_at) -> Any | None:
    """Return latest visible routine or SPECI report, using the common delay rule."""
    visible = [obs for obs in observations if available_at(obs.observation_time) <= cutoff_us]
    return max(visible, key=lambda obs: obs.observation_time, default=None)


def recent_visible_metars(observations: Sequence[Any], cutoff_us: int, *, available_at, limit: int = 3) -> list[Any]:
    visible = [obs for obs in observations if available_at(obs.observation_time) <= cutoff_us]
    return sorted(visible, key=lambda obs: obs.observation_time, reverse=True)[:limit]


def merge_parse_stats(stats: dict, key: tuple[str, str], values: Mapping[str, Any]) -> dict:
    """Merge TAF and ASOS parser diagnostics without key overwrite."""
    current = dict(stats.get(key, {}))
    current.update(values)
    stats[key] = current
    return stats


def validate_source_only_row(row: Mapping[str, Any]) -> None:
    forbidden = {"outcome", "value", "label", "y", "target_value", "evaluator_label"}

    def walk(value: Any) -> None:
        if isinstance(value, Mapping):
            if forbidden.intersection(value):
                raise ValueError("source-only row contains an outcome-like field")
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(row)
    if row.get("source_only") is not True or row.get("features_do_not_include_outcome") is not True:
        raise ValueError("source-only row markers are missing")


def source_gap_month_end(month: str, day: int) -> bool:
    year, month_number = (int(part) for part in month.split("-"))
    return day == calendar.monthrange(year, month_number)[1]


def history_incomplete(target_start_us: int, month: str, *, grace_hours: int = 36) -> bool:
    year, month_number = (int(part) for part in month.split("-"))
    month_start_us = int(datetime(year, month_number, 1, tzinfo=timezone.utc).timestamp() * 1_000_000)
    return target_start_us < month_start_us + grace_hours * 3_600_000_000


def metar_age_hours(*, observation_us: int | None, cutoff_us: int) -> float | None:
    if observation_us is None:
        return None
    return max(0.0, (cutoff_us - observation_us) / 3_600_000_000)


def preflight_git_contract(config_path: str | os.PathLike[str] | None, *, repo_root: str | os.PathLike[str] | None = None, script_path: str | os.PathLike[str] | None = None) -> str:
    """Verify temporary git config, commit identity and clean tracked code."""
    if not config_path or not Path(config_path).is_file():
        raise PermissionError("GIT_CONFIG_GLOBAL must name an existing temporary config")
    root = Path(repo_root or Path(__file__).parents[3]).resolve()
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    if subprocess.call(["git", "diff", "--quiet", "HEAD", "--"], cwd=root) != 0:
        raise RuntimeError("tracked worktree has uncommitted changes")
    if subprocess.call(["git", "diff", "--cached", "--quiet"], cwd=root) != 0:
        raise RuntimeError("index has staged changes")
    if script_path is not None:
        path = Path(script_path)
        if subprocess.call(["git", "diff", "--quiet", "HEAD", "--", str(path)], cwd=root) != 0:
            raise RuntimeError("the executing script is not committed")
    return commit


def require_v23_grid_contract(*, expected_methods, cutoff, available_at) -> dict[str, Any]:
    if not expected_methods or cutoff is None or available_at is None:
        raise ValueError("v23 grid calls must explicitly provide expected_methods, cutoff, and available_at")
    available_name = getattr(available_at, "__name__", available_at)
    return {"expected_methods": sorted(str(item) for item in expected_methods), "cutoff": cutoff, "available_at": available_name}
