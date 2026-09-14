"""Fit one error-informed calendar ablation on original roles, then freeze and evaluate."""

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from audit_native_feature_bank import gradient_check
from disastertrace.monitoring_v1.native_feature_forecast import predict_features
from disastertrace.monitoring_v1.regional_calibration_v2 import fit_fixed_prior
from disastertrace.monitoring_v1.spool_backend import digest, publish, read
from fit_native_feature_bank import fit, native_examples, vectors

DROPPED = {"year_sin", "year_cos"}


def fit_mode(arguments):
    train, calibration, mode = arguments
    rows = [
        ({k: v for k, v in f.items() if k not in DROPPED}, y, w, identity)
        for f, y, w, identity in vectors(train, mode)
    ]
    bank = fit(rows, mode)
    if DROPPED.intersection(bank["feature_names"]):
        raise ValueError("Ablated calendar field survived fitting")
    bank["mapping_version"] += ".no_annual_calendar"
    bank["feature_ablation"] = sorted(DROPPED)
    observations = defaultdict(list)
    for features, label, weight, _ in vectors(calibration, mode):
        ps = predict_features(bank, features)
        for threshold, outcome in (
            (1000, int(label == 0)),
            (5000, int(label in (0, 1))),
        ):
            observations[str(threshold)].append((ps[str(threshold)], outcome, weight))
    bank["post_calibration"] = {
        t: fit_fixed_prior(values, prior_mass=2) for t, values in observations.items()
    }
    return mode, bank, gradient_check(bank, rows)


def execute(args):
    out, parent, seasonal = (
        args.out.absolute(),
        args.parent.absolute(),
        args.seasonal.absolute(),
    )
    spec = read(out / "FIT_SPEC.json")
    if spec["features_removed"] != sorted(DROPPED):
        raise ValueError("Frozen ablation differs")
    publish(
        out / "RUN_CLAIM.json", {"at": dt.datetime.now(dt.timezone.utc).isoformat()}
    )
    for name, sha in spec["files"].items():
        if digest(out / name) != sha:
            raise ValueError("Frozen ablation source changed")
    freeze = read(parent / "BANK_FREEZE_BEFORE_EVALUATION.json")
    for name, sha in freeze["input_files"].items():
        path = Path(name)
        if path.suffix == ".py":
            copies = [
                parent / rel
                for rel, checksum in freeze["source_files"].items()
                if checksum == sha and Path(rel).name == path.name
            ]
            if len(copies) != 1:
                raise ValueError("Original source alias has no unique immutable copy")
            path = copies[0]
        if digest(path) != sha:
            raise ValueError("Original fitting source or input changed")
    manifest_path = next(
        Path(p)
        for p in freeze["input_files"]
        if p.endswith("DATA_PROCESS_MANIFEST.json")
    )
    if digest(manifest_path) != freeze["input_files"][str(manifest_path)]:
        raise ValueError("Original role manifest changed")
    by_dataset = defaultdict(list)
    for row in read(manifest_path)["rows"]:
        if row["role"] in {"fit", "calibration"}:
            by_dataset[row["dataset"]].append(row)
    examples = [
        item
        for dataset, rows in by_dataset.items()
        for item in native_examples(Path(dataset), rows)
    ]
    role_ids = read(parent / "ROLE_IDS.json")
    for role in ("fit", "calibration"):
        actual = sorted(
            {
                oid
                for row in examples
                if row["role"] == role
                for oid in row["opportunity_ids"].values()
            }
        )
        if actual != role_ids[role]:
            raise ValueError("Original fitting/calibration roster changed")
    train = [r for r in examples if r["role"] == "fit" and r["class"] is not None]
    calibration = [
        r for r in examples if r["role"] == "calibration" and r["class"] is not None
    ]
    support = read(parent / "TRAINING_SUPPORT.json")
    if (
        len(train) != support["fit_usable"]
        or len(calibration) != support["calibration_usable"]
    ):
        raise ValueError("Original fitting denominator changed")
    (out / "banks").mkdir()
    with ProcessPoolExecutor(max_workers=3) as pool:
        fitted = list(
            pool.map(
                fit_mode,
                [(train, calibration, m) for m in ("common", "mask_age", "values")],
            )
        )
    for mode, bank, _ in fitted:
        publish(out / "banks" / (mode + ".json"), bank)
    publish(
        out / "BANK_FREEZE_BEFORE_SEASONAL_EVALUATION.json",
        {
            "at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "fit_usable": len(train),
            "calibration_usable": len(calibration),
            "role_ids_sha256": digest(parent / "ROLE_IDS.json"),
            "banks": {
                mode: digest(out / "banks" / (mode + ".json")) for mode, _, _ in fitted
            },
            "independent_objective_gradient_audit": {
                mode: audit for mode, _, audit in fitted
            },
            "seasonal_labels_consumed_by_optimizer": False,
            "ablation_choice_informed_by_exposed_seasonal_diagnostics": True,
        },
    )
    evaluation = out / "evaluation_01"
    evaluation.mkdir()
    shutil.copytree(
        seasonal / "source",
        evaluation / "source",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    shutil.copyfile(
        out / "source/evaluate_seasonal_development.py",
        evaluation / "source/evaluate_seasonal_development.py",
    )
    shutil.copytree(out / "banks", evaluation / "banks")
    for region in ("new_york", "chicago", "denver"):
        shutil.copyfile(
            seasonal / "banks" / (region + ".json"),
            evaluation / "banks" / (region + ".json"),
        )
    evaluation_plan = read(seasonal / "PLAN.json")
    evaluation_plan.update(
        {
            "schema": "disastertrace.seasonal_no_annual_calendar.v1",
            "at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "new_fit": True,
            "scope": "one error-informed ablation on original Dec2024 roles; all12 seasonal development units retained",
            "features_removed": sorted(DROPPED),
            "files": {
                str(p.relative_to(evaluation)): digest(p)
                for p in evaluation.rglob("*")
                if p.is_file()
            },
        }
    )
    publish(evaluation / "PLAN.json", evaluation_plan)
    commands = [
        [
            sys.executable,
            str(evaluation / "source/evaluate_seasonal_development.py"),
            "--out",
            str(evaluation),
            "--execute",
            "--workers",
            "12",
        ],
        [
            sys.executable,
            str(out / "source/audit_seasonal_evaluation.py"),
            "--study",
            str(evaluation),
            "--out",
            str(out / "independent_audit_01"),
            "--workers",
            "12",
        ],
    ]
    env = dict(
        os.environ,
        PYTHONPATH=os.pathsep.join([str(out / "source"), str(evaluation / "source")]),
        PYTHONDONTWRITEBYTECODE="1",
        OPENBLAS_NUM_THREADS="1",
        OMP_NUM_THREADS="1",
    )
    for index, command in enumerate(commands):
        publish(out / ("COMMAND_" + str(index) + ".json"), {"command": command})
        with (out / ("command_" + str(index) + ".log")).open("x") as log:
            response = subprocess.run(
                command,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=3600,
                check=False,
            )
        publish(
            out / ("EXIT_" + str(index) + ".json"), {"exit_code": response.returncode}
        )
        if response.returncode:
            raise RuntimeError(
                "Ablation evaluation/audit failed; retain all prior artifacts"
            )
    metrics = read(evaluation / "METRICS.json")
    original = read(seasonal / "METRICS.json")
    if set(metrics) != set(original):
        raise ValueError("Paired seasonal metric groups changed")
    comparisons = {}
    for key, after in metrics.items():
        before = original[key]
        for field in ("opportunities", "settled", "missing", "base_brier"):
            if before[field] != after[field]:
                raise ValueError("Calendar ablation changed denominator or FOLLOW")
        comparisons[key] = {
            "original_brier": before["system_brier"],
            "ablation_brier": after["system_brier"],
            "original_minus_ablation": before["system_brier"] - after["system_brier"],
            "opportunities": after["opportunities"],
            "settled": after["settled"],
        }
    publish(out / "COMPARISON.json", comparisons)
    publish(
        out / "RESULT.json",
        {
            "passed": True,
            "fit_usable": len(train),
            "calibration_usable": len(calibration),
            "seasonal_opportunities": 12096,
            "feature_families": 3,
            "features_removed": sorted(DROPPED),
            "independent_arithmetic_audit_passed": True,
            "new_model_calls": 0,
            "confirmation_opened": False,
            "interpretation": "posthoc-development feature ablation; retains all original scores and changes no fit/calibration roles",
            "fit_scope": "new fit on original Dec2024 roles only; no seasonal labels enter the optimizer",
        },
    )
    print(
        json.dumps(
            {"passed": True, "fit_usable": len(train), "seasonal_opportunities": 12096}
        ),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--seasonal", type=Path, required=True)
    execute(parser.parse_args())
