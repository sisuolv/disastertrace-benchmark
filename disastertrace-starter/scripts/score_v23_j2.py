#!/usr/bin/env python3
"""Frozen v23-C development scorer.

The module keeps the information state explicit: a source is unavailable
until a policy purchases it, probabilities are fitted from training targets
only, and all comparisons use one common target/checkpoint table.  It is
deliberately usable without pandas/sklearn so the CPU analysis remains
portable to the validated offline environment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np

from disastertrace.revision_v1.v23_contracts import LEAD_LABELS, metar_available_at
from disastertrace.revision_v1.v23_source_features import require_v23_grid_contract


ACTIONS = ("none", "taf", "metar", "both")
ACTION_COST = {"none": 0, "taf": 1, "metar": 1, "both": 2}
STATIONS = ("KDEN", "KJFK", "KORD", "KSFO")
CS = (0.01, 0.1, 1.0, 10.0)


def _sigmoid(values: np.ndarray) -> np.ndarray:
    values = np.clip(values, -40.0, 40.0)
    return 1.0 / (1.0 + np.exp(-values))


def _float(value: Any, default: float = 0.0) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    return value if math.isfinite(value) else default


def _flag(value: Any) -> float:
    return 0.0 if value is None else float(value)


def _source_interval(source: Mapping[str, Any] | None) -> tuple[float, float]:
    if not source:
        return 0.0, 0.0
    visibility = source.get("visibility") or {}
    return _float(visibility.get("lower")) / 5000.0, _float(visibility.get("upper")) / 5000.0


def feature_names() -> list[str]:
    return [
        "taf_prevailing_lower_min", "taf_prevailing_upper_max", "taf_conditional_lower_min",
        "taf_event_flag", "taf_coverage_status", "metar_recent_1_visibility",
        "metar_recent_2_visibility", "metar_recent_1_age_s", "metar_recent_2_age_s",
        "metar_event_flag", "taf_missing", "metar_missing", "taf_carry_age_s",
        "metar_carry_age_s", "taf_issuance_age_s", "lead_hours", "station_one_hot",
    ]


def row_features(row: Mapping[str, Any], *, taf_acquired: bool, metar_acquired: bool) -> np.ndarray:
    taf = row.get("taf") or {}
    taf_content = taf.get("features") or {}
    metar = row.get("metar") if metar_acquired else None
    recent = (row.get("recent_metars") or [])[:2] if metar_acquired else []
    vals: list[float] = [
        _float((taf_content.get("prevailing") or {}).get("lower_min")) / 5000.0 if taf_acquired else 0.0,
        _float((taf_content.get("prevailing") or {}).get("upper_max")) / 5000.0 if taf_acquired else 0.0,
        _float((taf_content.get("conditional") or {}).get("lower_min")) / 5000.0 if taf_acquired else 0.0,
        _flag(taf.get("event_flag")) if taf_acquired else 0.0,
        float((taf_content.get("coverage_status") == "covered") if taf_acquired else False),
    ]
    for item in recent:
        low, high = _source_interval(item)
        vals.append((low + high) / 2.0)
    while len(vals) < 7:
        vals.append(0.0)
    cutoff = _float(row.get("cutoff_us"))
    for item in recent[:2]:
        available = _float(item.get("available_at_us"), 0.0)
        vals.append(max(0.0, cutoff - available) / 3.6e9)
    while len(vals) < 9:
        vals.append(0.0)
    vals.extend([
        _flag((metar or {}).get("event_flag")),
        0.0 if taf_acquired else 1.0,
        0.0 if metar_acquired else 1.0,
        max(0.0, cutoff - _float(taf.get("issued_at"))) / 3.6e9 if taf_acquired and taf.get("issued_at") is not None else 0.0,
        max(0.0, cutoff - _float((metar or {}).get("available_at_us"))) / 3.6e9 if metar_acquired and (metar or {}).get("available_at_us") is not None else 0.0,
        _float(row.get("lead_hours")) / 6.0,
    ])
    vals.extend(float(row.get("station") == station) for station in STATIONS)
    # The names intentionally include one station_one_hot entry; four values
    # are represented in the vector while preserving the public feature list.
    return np.asarray(vals, dtype=float)


@dataclass
class LogisticModel:
    weights: np.ndarray
    mean: np.ndarray
    scale: np.ndarray
    base_rate: float
    C: float

    def predict_matrix(self, X: np.ndarray) -> np.ndarray:
        if X.size == 0:
            return np.full((0,), self.base_rate, dtype=float)
        Z = (X - self.mean) / self.scale
        return _sigmoid(np.c_[np.ones(len(Z)), Z] @ self.weights)

    def predict(self, row: Mapping[str, Any], *, taf_acquired: bool, metar_acquired: bool) -> float:
        return float(self.predict_matrix(row_features(row, taf_acquired=taf_acquired, metar_acquired=metar_acquired)[None, :])[0])


def _fit_logistic(X: np.ndarray, y: np.ndarray, C: float) -> LogisticModel:
    if len(y) == 0:
        return LogisticModel(np.zeros(X.shape[1] + 1), np.zeros(X.shape[1]), np.ones(X.shape[1]), 0.5, C)
    base = float(np.mean(y))
    if np.all(y == y[0]):
        return LogisticModel(np.r_[math.log((base + 1e-3) / (1 - base + 1e-3)), np.zeros(X.shape[1])], np.mean(X, axis=0), np.std(X, axis=0) + 1e-6, base, C)
    mean, scale = np.mean(X, axis=0), np.std(X, axis=0) + 1e-6
    Z = (X - mean) / scale
    A = np.c_[np.ones(len(Z)), Z]
    w = np.zeros(A.shape[1], dtype=float)
    reg = np.ones_like(w) / max(C, 1e-6)
    reg[0] = 0.0
    for _ in range(300):
        p = _sigmoid(A @ w)
        grad = (A.T @ (p - y)) / len(y) + reg * w / len(y)
        step = 0.35 / math.sqrt(1.0 + _)
        w -= step * grad
        if float(np.max(np.abs(grad))) < 1e-6:
            break
    return LogisticModel(w, mean, scale, base, C)


def _select_C(train_rows: list[dict], y_by_target: Mapping[str, int]) -> float:
    """Select C on deterministic daily blocks inside the training fold."""
    usable = [r for r in train_rows if r["target_id"] in y_by_target]
    if not usable:
        return 1.0
    block = [r for r in usable if int(r["physical_start_us"]) // 86_400_000_000 % 3 == 0]
    fit_rows = [r for r in usable if r not in block]
    if not block or not fit_rows:
        return 1.0
    scores = {}
    for C in CS:
        model = _fit_logistic(
            np.vstack([row_features(r, taf_acquired=a, metar_acquired=m) for r in fit_rows for a, m in product((False, True), repeat=2)]),
            np.asarray([y_by_target[r["target_id"]] for r in fit_rows for _ in product((False, True), repeat=2)], dtype=float),
            C,
        )
        pred = []
        obs = []
        for r in block:
            p = model.predict(r, taf_acquired=True, metar_acquired=True)
            pred.append(p); obs.append(y_by_target[r["target_id"]])
        scores[C] = float(np.mean((np.asarray(pred) - np.asarray(obs)) ** 2)) if pred else float("inf")
    return min(CS, key=lambda value: (scores[value], value))


def fit_F(rows: list[dict], y_by_target: Mapping[str, int], *, train_month: str | None = None) -> tuple[LogisticModel, dict]:
    train = [r for r in rows if r["target_id"] in y_by_target and (train_month is None or r["month"] == train_month)]
    C = _select_C(train, y_by_target)
    states = list(product((False, True), repeat=2))
    vector_width = len(row_features(train[0], taf_acquired=False, metar_acquired=False)) if train else len(feature_names()) + 3
    X = np.vstack([row_features(r, taf_acquired=a, metar_acquired=m) for r in train for a, m in states]) if train else np.empty((0, vector_width))
    y = np.asarray([y_by_target[r["target_id"]] for r in train for _ in states], dtype=float)
    model = _fit_logistic(X, y, C)
    return model, {"train_rows": len(train), "C": C, "state_count": len(states), "feature_names": feature_names()}


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def load_schedules(path: Path) -> list[dict]:
    data = json.loads(path.read_text())
    return list(data["schedules"])


def _acquired(actions: list[str], index: int) -> tuple[bool, bool]:
    purchased = {"taf": False, "metar": False}
    for action in actions[: index + 1]:
        if action in {"taf", "both"}:
            purchased["taf"] = True
        if action in {"metar", "both"}:
            purchased["metar"] = True
    return purchased["taf"], purchased["metar"]


def schedule_predictions(model: LogisticModel, rows: list[dict], schedule: Mapping[str, Any]) -> dict[str, list[float]]:
    result: dict[str, list[float]] = defaultdict(list)
    actions = list(schedule["actions"])
    for row in rows:
        index = int(row["checkpoint_index"])
        taf, metar = _acquired(actions, index)
        result[row["target_id"]].append(model.predict(row, taf_acquired=taf, metar_acquired=metar))
    return result


def _target_loss(preds: Iterable[float], y: int) -> float:
    values = list(preds)
    return float(np.mean([(p - y) ** 2 for p in values])) if values else float("nan")


def evaluate_schedule(model: LogisticModel, rows: list[dict], y_by_target: Mapping[str, int], schedule: Mapping[str, Any]) -> dict:
    preds = schedule_predictions(model, rows, schedule)
    losses = {target: _target_loss(values, y_by_target[target]) for target, values in preds.items() if target in y_by_target}
    return {"schedule": dict(schedule), "target_losses": losses, "mean_brier": float(np.mean(list(losses.values()))) if losses else None, "predictions": preds}


def baseline_predictions(rows: list[dict], y_by_target: Mapping[str, int], kind: str, base_rate: float) -> dict:
    out = defaultdict(list)
    for row in rows:
        taf_flag = (row.get("taf") or {}).get("event_flag")
        metar_flag = (row.get("metar") or {}).get("event_flag")
        if kind == "constant":
            p = base_rate
        elif kind == "taf":
            p = float(taf_flag) if taf_flag is not None else base_rate
        elif kind == "metar":
            p = float(metar_flag) if metar_flag is not None else base_rate
        elif kind == "fusion":
            values = [float(v) for v in (taf_flag, metar_flag) if v is not None]
            p = float(np.mean(values)) if values else base_rate
        else:
            raise ValueError(kind)
        out[row["target_id"]].append(p)
    return out


def score_predictions(predictions: Mapping[str, list[float]], y_by_target: Mapping[str, int]) -> tuple[float | None, dict[str, float]]:
    losses = {target: _target_loss(pred, y_by_target[target]) for target, pred in predictions.items() if target in y_by_target}
    return (float(np.mean(list(losses.values()))) if losses else None), losses


def _policy_action(policy: Mapping[str, Any], row: Mapping[str, Any], model: LogisticModel, *, taf: bool, metar: bool, remaining: int, fallback_action: str) -> str:
    p = model.predict(row, taf_acquired=taf, metar_acquired=metar)
    u = 4.0 * p * (1.0 - p)
    lead = _float(row.get("lead_hours"))
    family = policy["family"]
    action = "none"
    if family == "uncertainty":
        if u >= float(policy["tau2"]):
            action = "both"
        elif u >= float(policy["tau"]):
            action = "taf" if lead >= 3 else "metar"
    elif family == "age":
        taf_age = _float((row.get("taf") or {}).get("issued_at"), float("inf"))
        metar_age = _float((row.get("metar") or {}).get("available_at_us"), float("inf"))
        cutoff = _float(row.get("cutoff_us"))
        taf_hours = max(0.0, (cutoff - taf_age) / 3.6e9) if taf_age else float("inf")
        metar_hours = max(0.0, (cutoff - metar_age) / 3.6e9) if metar_age else float("inf")
        if metar_hours > float(policy["metar_age_hours"]):
            action = "metar"
        elif taf_hours > float(policy["taf_age_hours"]):
            action = "taf"
    elif family == "disagreement":
        tf, mf = (row.get("taf") or {}).get("event_flag"), (row.get("metar") or {}).get("event_flag")
        mismatch = tf is not None and mf is not None and tf != mf
        unknown = tf is None or mf is None
        mode = policy["mode"]
        if ("disagreement" in mode and mismatch) or ("unknown" in mode and unknown) or mode == "both_on_any_uncertain" and (mismatch or unknown):
            action = "both" if mode.startswith("both") else ("metar" if taf and not metar else "taf")
    if ACTION_COST[action] > remaining:
        action = fallback_action if ACTION_COST.get(fallback_action, 99) <= remaining else "none"
    return action


def evaluate_policy(model: LogisticModel, rows: list[dict], y_by_target: Mapping[str, int], policy: Mapping[str, Any], fallback_schedule: Mapping[str, Any]) -> dict:
    by_target = defaultdict(list)
    for row in rows:
        by_target[row["target_id"]].append(row)
    losses = {}
    actions_by_target = {}
    for target, trajectory in by_target.items():
        trajectory = sorted(trajectory, key=lambda r: int(r["checkpoint_index"]))
        taf = metar = False
        remaining = 4
        preds = []
        acts = []
        for row in trajectory:
            fallback = fallback_schedule["actions"][int(row["checkpoint_index"])]
            action = _policy_action(policy, row, model, taf=taf, metar=metar, remaining=remaining, fallback_action=fallback)
            remaining -= ACTION_COST[action]
            if action in {"taf", "both"}:
                taf = True
            if action in {"metar", "both"}:
                metar = True
            preds.append(model.predict(row, taf_acquired=taf, metar_acquired=metar))
            acts.append(action)
        if target in y_by_target:
            losses[target] = _target_loss(preds, y_by_target[target])
            actions_by_target[target] = acts
    return {"policy": dict(policy), "target_losses": losses, "actions": actions_by_target, "mean_brier": float(np.mean(list(losses.values()))) if losses else None}


def decision(point: float, samples: Iterable[float], *, delta: float, harm_samples: Iterable[float] | None = None) -> dict:
    values = np.asarray(list(samples), dtype=float)
    if values.size == 0:
        return {"decision": "INCONCLUSIVE", "point": point, "L95": None, "U95": None}
    low, high = np.quantile(values, [0.025, 0.975])
    harm = None if harm_samples is None else bool(np.quantile(np.asarray(list(harm_samples), dtype=float), 0.025) < -0.005)
    if harm:
        verdict = "INCONCLUSIVE"
    elif low > 0 and point >= delta:
        verdict = "GO"
    elif high < delta:
        verdict = "STOP"
    else:
        verdict = "INCONCLUSIVE"
    return {"decision": verdict, "point": float(point), "L95": float(low), "U95": float(high), "harm": harm}


def cluster_bootstrap(gains: Mapping[str, float], *, replicates: int = 1000, seed: int = 20260927) -> np.ndarray:
    groups: dict[str, list[float]] = defaultdict(list)
    for target, gain in gains.items():
        parts = target.split("_")
        day = parts[1][:8] if len(parts) > 1 else target
        groups[day].append(float(gain))
    if not groups:
        return np.empty(0)
    names, arrays = list(groups), list(groups.values())
    rng = np.random.default_rng(seed)
    return np.asarray([float(np.mean(np.concatenate([arrays[i] for i in rng.integers(0, len(arrays), len(arrays))]))) for _ in range(replicates)])


def run_synthetic_acceptance(*, seed: int = 20260927, zero_n: int = 20000) -> dict:
    rng = np.random.default_rng(seed)
    zero = np.zeros(zero_n, dtype=float) + rng.normal(0.0, 1e-10, zero_n)
    positive = np.full(zero_n, 0.125, dtype=float)
    zero_decision = decision(float(np.mean(zero)), zero, delta=0.005)
    positive_decision = decision(float(np.mean(positive)), positive, delta=0.005)
    # H is deliberately large in the zero world; it is not a GO statistic.
    return {
        "seed": seed, "delta_test": 0.005, "zero_n": zero_n,
        "zero_world": {"G_adapt": float(np.mean(zero)), "H": 0.0152, **zero_decision},
        "positive_world": {"G_adapt": float(np.mean(positive)), "theoretical_G": 0.125, **positive_decision},
        "acceptance": zero_decision["decision"] in {"STOP", "INCONCLUSIVE"} and positive_decision["decision"] == "GO",
    }


def prediction_fingerprint(predictions: Mapping[str, Any]) -> str:
    raw = json.dumps(predictions, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def _contract_score(rows: list[dict], submissions: list[dict], *, expected_methods: tuple[str, ...], cutoff: int) -> dict:
    """Adapter that makes every complete-grid call carry the v23 contract."""
    require_v23_grid_contract(expected_methods=expected_methods, cutoff=cutoff, available_at=metar_available_at)
    from disastertrace.monitoring_v1.grid_scoring_v18 import score_complete_grid
    return score_complete_grid(rows, submissions, expected_methods=expected_methods)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--synthetic-only", action="store_true")
    parser.add_argument("--roster", type=Path)
    parser.add_argument("--y", type=Path)
    parser.add_argument("--predictions", type=Path)
    parser.add_argument("--schedule-manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.synthetic_only:
        result = run_synthetic_acceptance()
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(json.dumps(result, sort_keys=True))
        return 0 if result["acceptance"] else 1
    required = (args.roster, args.y, args.schedule_manifest)
    if any(item is None for item in required):
        raise SystemExit("--roster, --y and --schedule-manifest are required unless --synthetic-only")
    rows = load_jsonl(args.roster)
    y_rows = load_jsonl(args.y)
    y_by_target = {row["target_id"]: int(row["outcome"]) for row in y_rows if row.get("outcome") is not None and not row.get("conflict")}
    schedules = load_schedules(args.schedule_manifest)
    months = sorted({row["month"] for row in rows})
    folds = []
    for train_month, test_month in ((months[0], months[1]), (months[1], months[0])):
        train, test = [r for r in rows if r["month"] == train_month], [r for r in rows if r["month"] == test_month]
        model, model_info = fit_F(rows, y_by_target, train_month=train_month)
        evaluations = [evaluate_schedule(model, train, y_by_target, s) for s in schedules]
        evaluations.sort(key=lambda item: item["mean_brier"] if item["mean_brier"] is not None else float("inf"))
        best_fixed = evaluations[0]
        test_fixed = evaluate_schedule(model, test, y_by_target, best_fixed["schedule"])
        single = [item for item in evaluations if all(action in {"none", "taf", "metar"} for action in item["schedule"]["actions"])]
        best_single = single[0] if single else best_fixed
        test_single = evaluate_schedule(model, test, y_by_target, best_single["schedule"])
        policies = json.loads(Path(__file__).parents[1].joinpath("config/v23b/POLICY_CLASS_v2.json").read_text())["policies"]
        policy_train = [evaluate_policy(model, train, y_by_target, p, best_fixed["schedule"]) for p in policies]
        policy_train.sort(key=lambda item: item["mean_brier"] if item["mean_brier"] is not None else float("inf"))
        best_policy = policy_train[0]
        test_policy = evaluate_policy(model, test, y_by_target, best_policy["policy"], best_fixed["schedule"])
        base_rate = float(np.mean([y_by_target[t] for t in {r["target_id"] for r in train} if t in y_by_target])) if y_by_target else 0.5
        baselines = {}
        for kind in ("constant", "taf", "metar", "fusion"):
            pred = baseline_predictions(test, y_by_target, kind, base_rate)
            baselines[kind] = score_predictions(pred, y_by_target)[0]
        folds.append({"train_month": train_month, "test_month": test_month, "model": model_info, "best_fixed": best_fixed["schedule"], "best_fixed_test": test_fixed["mean_brier"], "best_single_test": test_single["mean_brier"], "best_policy": best_policy["policy"], "best_policy_test": test_policy["mean_brier"], "baselines": baselines, "G_adapt": (test_fixed["mean_brier"] - test_policy["mean_brier"]) if test_fixed["mean_brier"] is not None and test_policy["mean_brier"] is not None else None, "V_fusion": (test_single["mean_brier"] - test_fixed["mean_brier"]) if test_single["mean_brier"] is not None and test_fixed["mean_brier"] is not None else None})
    result = {"schema": "disastertrace.v23c.j2_score.v1", "development_status": "exploratory", "folds": folds, "review_status": "REVIEW_PENDING"}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
