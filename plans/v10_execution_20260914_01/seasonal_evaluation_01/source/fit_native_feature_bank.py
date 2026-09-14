"""Fit small preregistered coherent feature controls on purged December data."""

import argparse
import datetime as dt
import itertools
import json
import math
import shutil
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

from disastertrace.monitoring_v1.native_feature_forecast import FEATURE_VERSION, feature_vector, predict_features
from disastertrace.monitoring_v1.providers.versions import current_taf
from disastertrace.monitoring_v1.regional_calibration import apply_monotone
from disastertrace.monitoring_v1.regional_calibration_v2 import coherent_cdf, fit_fixed_prior
from disastertrace.monitoring_v1.spool_backend import digest, publish, read
from disastertrace.monitoring_v1.targets import canonical_hash

MODES = ("common", "mask_age", "values")


def native_examples(dataset, rows):
    targets = {r["target_id"]: r for r in read(dataset / "public/TARGETS.json")}
    native = read(dataset / "environment/NATIVE_PRODUCT_INDEX.json")
    candidates = {(r["opportunity_id"], r["source_id"]): r for r in read(dataset / "environment/BASELINE_CANDIDATES.json")}
    catalog = {r["query_id"]: r for r in read(dataset / "public/QUERY_CATALOG.json")}
    results = {r["query_id"]: r for r in read(dataset / "environment/QUERY_RESULTS.json")}
    paired = {}
    for row in rows:
        target = targets[row["target_id"]]
        at = row["cutoff"]-600_000_000
        decision = current_taf(native, station=row["station"], cutoff=at,
                              start=target["physical_start"], end=target["physical_end"])
        candidate = candidates.get((row["opportunity_id"], decision.get("selected_id")))
        qids = row["query_ids"]
        legal = sorted(q for q in qids if catalog[q]["available_at"]+catalog[q]["latency_ms"]*1000 <= at)
        views = [{q: results[q] for q in selected} for n in range(len(legal)+1) for selected in itertools.combinations(legal, n)]
        key = (row["station"], target["physical_start"], target["physical_end"], row["cutoff"])
        information = {"station": row["station"], "start": target["physical_start"], "end": target["physical_end"],
            "at": at, "query_ids": qids, "evidence": views[-1],
            "taf": None if candidate is None else {k:candidate.get(k) for k in ("raw", "projection", "issued_at", "available_at")}}
        item = paired.setdefault(key, {"region": row["region"], "role": row["role"], "targets": {},
            "outcomes": {}, "opportunity_ids": {}, "information_sha256": canonical_hash(information),
            "target": target, "candidate": candidate, "query_ids": qids, "views": views, "at": at})
        if (item["information_sha256"] != canonical_hash(information) or item["role"] != row["role"]
                or target["threshold"] in item["outcomes"]):
            raise ValueError("Nested thresholds have unequal information, duplicate IDs or crossed roles")
        item["outcomes"][target["threshold"]] = row["outcome"]
        item["opportunity_ids"][target["threshold"]] = row["opportunity_id"]
        item["targets"][target["threshold"]] = target
    for item in paired.values():
        if set(item["outcomes"]) != {1000, 5000}:
            raise ValueError("Both registered thresholds must be retained")
        low, high = item["outcomes"][1000], item["outcomes"][5000]
        if low is not None and high is not None and low > high:
            raise ValueError("Reference outcomes violate nested visibility thresholds")
        item["class"] = None if low is None or high is None else 0 if low else 1 if high else 2
        yield item


def vectors(examples, mode, *, full_only=False):
    rows = []
    for item in examples:
        views = [{}] if mode == "common" else [item["views"][-1]] if full_only else item["views"]
        for view in views:
            features = feature_vector(item["target"], item["candidate"], item["query_ids"], view,
                                      at=item["at"], mode=mode)
            rows.append((features, item["class"], 1/len(views), item["information_sha256"]))
    return rows


def fit(rows, mode):
    names = sorted({name for f, _, _, _ in rows for name in f})
    x = np.asarray([[f.get(k, 0.0) for k in names] for f, _, _, _ in rows], dtype=np.float64)
    y = np.asarray([label for _, label, _, _ in rows], dtype=np.int64)
    weights = np.asarray([weight for _, _, weight, _ in rows], dtype=np.float64)
    mean = np.average(x, axis=0, weights=weights)
    scale = np.sqrt(np.average((x-mean)**2, axis=0, weights=weights))
    scale[scale < 1e-10] = 1.0
    x = (x-mean)/scale
    # One total Dirichlet prior of mass two, at the training feature mean.
    x = np.vstack([x, np.zeros((3, len(names)))])
    y = np.concatenate([y, [0, 1, 2]])
    weights = np.concatenate([weights, [2/3, 2/3, 2/3]])
    x = np.column_stack([x, np.ones(len(x))])
    total = weights.sum()

    def objective(flat):
        matrix = flat.reshape(3, x.shape[1])
        scores = x @ matrix.T
        scores -= scores.max(axis=1, keepdims=True)
        exp = np.exp(scores)
        p = exp/exp.sum(axis=1, keepdims=True)
        logp = scores-np.log(exp.sum(axis=1, keepdims=True))
        loss = -np.dot(weights, logp[np.arange(len(y)), y])/total + np.sum(matrix[:, :-1]**2)/(2*total)
        p[np.arange(len(y)), y] -= 1
        gradient = (p*weights[:, None]).T @ x/total
        gradient[:, :-1] += matrix[:, :-1]/total
        return loss, gradient.ravel()

    result = minimize(objective, np.zeros(3*x.shape[1]), jac=True, method="L-BFGS-B",
                      options={"maxiter": 1000, "ftol": 1e-10, "gtol": 1e-6})
    if not result.success:
        raise ValueError("Preregistered optimizer failed: "+str(result.message))
    matrix = result.x.reshape(3, x.shape[1])
    return {"schema": "disastertrace.native_feature_bank.v1", "feature_version": FEATURE_VERSION,
        "mapping_version": "pooled_dec2024_softmax_"+mode+".v1", "mode": mode,
        "feature_names": names, "mean": mean.tolist(), "scale": scale.tolist(),
        "coefficients": matrix[:, :-1].tolist(), "intercepts": matrix[:, -1].tolist(),
        "fit": {"feature_rows": len(rows), "information_units": len({r[3] for r in rows}),
            "weighted_n": float(total-2), "class_weight": dict(Counter({str(k): math.fsum(w for _, y, w, _ in rows if y == k) for k in range(3)})),
            "l2": 1.0, "total_prior_mass": 2.0, "iterations": int(result.nit),
            "gradient_inf_norm": float(np.max(np.abs(result.jac))), "objective": float(result.fun)}}


def probability(bank, features, *, calibrated):
    p = predict_features(bank, features)
    values = [p["1000"], p["5000"]]
    if calibrated:
        values = [apply_monotone(bank["post_calibration"][str(t)], value) for t, value in zip((1000, 5000), values, strict=True)]
        info = canonical_hash(features)
        values = coherent_cdf(values, [info, info])
    return dict(zip((1000, 5000), values, strict=True))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.absolute()
    out.mkdir(exist_ok=False)
    root = Path(__file__).resolve().parents[3]
    old = root / "plans/v9_followup_execution_20260914_01"
    publish(out / "PREDICTOR_SPEC.json", {"registered_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "mode": "three-bin coherent softmax with L2=1 and total prior mass=2; raw and fixed-prior-PAV/CDF outputs both reported",
        "feature_version": FEATURE_VERSION, "families": list(MODES), "primary": "raw coherent softmax",
        "fit_period": "2024-12-01..19", "calibration_period": "2024-12-23..29", "regions": ["bay", "new_york", "chicago", "denver"],
        "selection": "all existing fully purged role manifests; no new test-loss selection",
        "paired_unit": "station, fixed physical report window, cutoff; both thresholds share one three-bin label",
        "view_weighting": "one total weight per information unit in each family, divided among legal evidence subsets",
        "E": "registered native neighbor reports; values include visibility censoring, temperature/dewpoint and age",
        "scope": "fixed-information exposed development, not active-session or independent confirmation",
        "new_self_station_source": False, "confirmation_opened": False, "model_calls": 0})
    manifest_path = old / "reports/process_manifest_02/DATA_PROCESS_MANIFEST.json"
    manifest = read(manifest_path)["rows"]
    by_dataset = defaultdict(list)
    for row in manifest:
        if row["role"] in {"fit", "calibration", "development_evaluation"}:
            by_dataset[row["dataset"]].append(row)
    examples = [item for dataset, rows in by_dataset.items() for item in native_examples(Path(dataset), rows)]
    train = [r for r in examples if r["role"] == "fit" and r["class"] is not None]
    calibration = [r for r in examples if r["role"] == "calibration" and r["class"] is not None]
    evaluation = [r for r in examples if r["role"] == "development_evaluation"]
    ids = {role: sorted({oid for r in examples if r["role"] == role for oid in r["opportunity_ids"].values()})
           for role in ("fit", "calibration", "development_evaluation")}
    assert all(not (set(ids[a]) & set(ids[b])) for a,b in itertools.combinations(ids, 2))
    publish(out / "ROLE_IDS.json", ids)
    publish(out / "TRAINING_SUPPORT.json", {"paired_units": {role: sum(r["role"] == role for r in examples) for role in ids},
        "fit_usable": len(train), "calibration_usable": len(calibration),
        "missing_class_retained": sum(r["class"] is None for r in examples),
        "fit_classes": dict(Counter(r["class"] for r in train)),
        "calibration_classes": dict(Counter(r["class"] for r in calibration)),
        "prior_dependency_audit": "../reports/dependency_audit_01/RESULT.json"})
    banks = {}
    for mode in MODES:
        bank = fit(vectors(train, mode), mode)
        observations = defaultdict(list)
        for features, label, weight, _ in vectors(calibration, mode):
            p = predict_features(bank, features)
            for t, y in ((1000, int(label == 0)), (5000, int(label in (0, 1)))):
                observations[str(t)].append((p[str(t)], y, weight))
        bank["post_calibration"] = {t: fit_fixed_prior(rows, prior_mass=2) for t, rows in observations.items()}
        publish(out / ("BANK_"+mode+".json"), bank)
        banks[mode] = bank
    source_paths = [manifest_path, Path(__file__), root / "disastertrace-starter/src/disastertrace/monitoring_v1/native_feature_forecast.py"]
    for dataset in by_dataset:
        source_paths.extend(Path(dataset)/p for p in ("public/TARGETS.json", "environment/NATIVE_PRODUCT_INDEX.json",
            "environment/BASELINE_CANDIDATES.json", "public/QUERY_CATALOG.json", "environment/QUERY_RESULTS.json"))
    (out / "source").mkdir()
    for package in ("monitoring_v1", "monitoring_fixed_v1", "forecast_task"):
        shutil.copytree(root / "disastertrace-starter/src/disastertrace" / package, out / "source/disastertrace" / package,
                        ignore=shutil.ignore_patterns("__pycache__"))
    (out / "source/disastertrace/__init__.py").write_text('"""Frozen native feature model."""\n')
    shutil.copyfile(__file__, out / "source/fit_native_feature_bank.py")
    publish(out / "BANK_FREEZE_BEFORE_EVALUATION.json", {"input_files": {str(p): digest(p) for p in source_paths},
        "bank_files": {name: digest(out / name) for name in ("BANK_common.json", "BANK_mask_age.json", "BANK_values.json")},
        "source_files": {str(p.relative_to(out)): digest(p) for p in (out / "source").rglob("*.py")},
        "at": dt.datetime.now(dt.timezone.utc).isoformat()})
    output_rows, metrics = [], defaultdict(lambda: {"registered": 0, "scored": 0, "positive": 0, "loss_sum": 0.0})
    for item in evaluation:
        for mode, bank in banks.items():
            for info in ("common_only", "all_registered"):
                view = {} if info == "common_only" else item["views"][-1]
                features = feature_vector(item["target"], item["candidate"], item["query_ids"], view,
                                          at=item["at"], mode=mode)
                for calibrated in (False, True):
                    probabilities = probability(bank, features, calibrated=calibrated)
                    assert 0 <= probabilities[1000] <= probabilities[5000] <= 1
                    for t, p in probabilities.items():
                        y = item["outcomes"][t]
                        name = mode+"__"+info+"__"+("pav_prior2_cdf" if calibrated else "raw")
                        row = {"opportunity_id": item["opportunity_ids"][t], "region": item["region"], "threshold": t,
                            "method": name, "probability": p, "outcome": y, "information_sha256": item["information_sha256"],
                            "feature_sha256": canonical_hash(features)}
                        output_rows.append(row)
                        m = metrics[str(t)+"__"+name]
                        m["registered"] += 1
                        if y is not None:
                            m["scored"] += 1
                            m["positive"] += y
                            m["loss_sum"] += (p-y)**2
    for value in metrics.values():
        value["brier"] = value["loss_sum"]/value["scored"] if value["scored"] else None
    with (out / "EVALUATION_ROWS.jsonl").open("x") as stream:
        for row in output_rows:
            stream.write(json.dumps(row, sort_keys=True)+"\n")
    publish(out / "RESULT.json", {"passed": True, "fit_units": len(train), "calibration_units": len(calibration),
        "development_units": len(evaluation), "forecast_rows": len(output_rows), "metrics": dict(metrics),
        "threshold_crossings": 0, "new_banks_selected_by_evaluation": False,
        "forecast_scope": "fixed-information native report prediction; no model or adaptive session calls", "confirmation_opened": False})


if __name__ == "__main__":
    main()
