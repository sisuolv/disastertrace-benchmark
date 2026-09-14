"""Reconstruct new-bank identities and arithmetic without refitting/selecting."""

import argparse
import importlib.util
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from disastertrace.monitoring_v1.native_feature_forecast import feature_vector
from disastertrace.monitoring_v1.spool_backend import digest, publish, read
from disastertrace.monitoring_v1.targets import canonical_hash


def independent_probabilities(bank, features, calibrated):
    vector = [
        (features.get(name, 0.0) - bank["mean"][i]) / bank["scale"][i]
        for i, name in enumerate(bank["feature_names"])
    ]
    logits = [
        bank["intercepts"][k]
        + math.fsum(a * b for a, b in zip(bank["coefficients"][k], vector, strict=True))
        for k in range(3)
    ]
    weights = [math.exp(x - max(logits)) for x in logits]
    values = [weights[0] / sum(weights), (weights[0] + weights[1]) / sum(weights)]
    if calibrated:
        mapped = []
        for t, probability in zip(("1000", "5000"), values, strict=True):
            blocks = bank["post_calibration"][t]
            chosen = next((b for b in blocks if probability <= b["upper"]), blocks[-1])
            mapped.append(chosen["value"])
        values = mapped if mapped[0] <= mapped[1] else [(mapped[0] + mapped[1]) / 2] * 2
    return dict(zip((1000, 5000), values, strict=True))


def gradient_check(bank, rows):
    x = np.asarray(
        [
            [
                (f.get(k, 0.0) - m) / s
                for k, m, s in zip(
                    bank["feature_names"], bank["mean"], bank["scale"], strict=True
                )
            ]
            for f, _, _, _ in rows
        ]
    )
    labels = np.array([y for _, y, _, _ in rows] + [0, 1, 2])
    weights = np.array([w for _, _, w, _ in rows] + [2 / 3] * 3)
    x = np.vstack((x, np.zeros((3, x.shape[1]))))
    matrix = np.asarray(bank["coefficients"])
    logits = x @ matrix.T + np.asarray(bank["intercepts"])
    logits -= logits.max(axis=1, keepdims=True)
    probabilities = np.exp(logits)
    probabilities /= probabilities.sum(axis=1, keepdims=True)
    losses = -np.log(probabilities[np.arange(len(labels)), labels])
    objective = float((weights @ losses + 0.5 * np.sum(matrix**2)) / sum(weights))
    residual = probabilities - np.eye(3)[labels]
    gradient = ((residual * weights[:, None]).T @ x + matrix) / sum(weights)
    intercept_gradient = (residual * weights[:, None]).sum(axis=0) / sum(weights)
    maximum = max(
        float(np.max(np.abs(gradient))), float(np.max(np.abs(intercept_gradient)))
    )
    if not math.isclose(
        objective, bank["fit"]["objective"], rel_tol=1e-10, abs_tol=1e-10
    ):
        raise ValueError("Independent regularized objective differs")
    if not math.isclose(
        maximum, bank["fit"]["gradient_inf_norm"], rel_tol=1e-8, abs_tol=1e-10
    ):
        raise ValueError("Independent gradient differs")
    return {"objective": objective, "gradient_inf_norm": maximum, "refitted": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bank", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(exist_ok=False)
    freeze = read(args.bank / "BANK_FREEZE_BEFORE_EVALUATION.json")
    source_relocations = []
    for group in ("input_files", "bank_files", "source_files"):
        for path, sha in freeze[group].items():
            candidate = Path(path) if group == "input_files" else args.bank / path
            if group == "input_files" and candidate.suffix == ".py":
                copies = [
                    args.bank / rel
                    for rel, checksum in freeze["source_files"].items()
                    if checksum == sha and Path(rel).name == candidate.name
                ]
                if len(copies) != 1:
                    raise ValueError(
                        "Original source alias requires one hash-bound frozen copy"
                    )
                source_relocations.append(
                    {
                        "original_alias": str(candidate),
                        "verified_copy": str(copies[0]),
                        "working_alias_still_matches": digest(candidate) == sha,
                    }
                )
                candidate = copies[0]
            if digest(candidate) != sha:
                raise ValueError("Original bank/source/input hash changed")
    helper_path = args.bank / "source/fit_native_feature_bank.py"
    spec = importlib.util.spec_from_file_location("frozen_native_bank", helper_path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    manifest_path = next(
        Path(p)
        for p in freeze["input_files"]
        if p.endswith("DATA_PROCESS_MANIFEST.json")
    )
    grouped = defaultdict(list)
    for row in read(manifest_path)["rows"]:
        if row["role"] in {"fit", "calibration", "development_evaluation"}:
            grouped[row["dataset"]].append(row)
    examples = [
        example
        for dataset, rows in grouped.items()
        for example in helper.native_examples(Path(dataset), rows)
    ]
    registered = read(args.bank / "ROLE_IDS.json")
    for role, ids in registered.items():
        actual = [
            oid
            for row in examples
            if row["role"] == role
            for oid in row["opportunity_ids"].values()
        ]
        if len(actual) != len(set(actual)) or sorted(actual) != ids:
            raise ValueError("Role/opportunity registry changed")
    bank_by_mode = {m: read(args.bank / ("BANK_" + m + ".json")) for m in helper.MODES}
    optimizer = {
        mode: gradient_check(
            bank,
            helper.vectors(
                [r for r in examples if r["role"] == "fit" and r["class"] is not None],
                mode,
            ),
        )
        for mode, bank in bank_by_mode.items()
    }
    expected = {}
    for row in examples:
        if row["role"] != "development_evaluation":
            continue
        for mode, bank in bank_by_mode.items():
            for scope in ("common_only", "all_registered"):
                view = {} if scope == "common_only" else row["views"][-1]
                features = feature_vector(
                    row["target"],
                    row["candidate"],
                    row["query_ids"],
                    view,
                    at=row["at"],
                    mode=mode,
                )
                for calibrated in (False, True):
                    method = (
                        mode
                        + "__"
                        + scope
                        + "__"
                        + ("pav_prior2_cdf" if calibrated else "raw")
                    )
                    ps = independent_probabilities(bank, features, calibrated)
                    for t, p in ps.items():
                        expected[row["opportunity_ids"][t], method] = (
                            p,
                            row["outcomes"][t],
                            canonical_hash(features),
                            t,
                        )
    metrics = defaultdict(
        lambda: {"registered": 0, "scored": 0, "positive": 0, "losses": []}
    )
    seen = set()
    for line in (args.bank / "EVALUATION_ROWS.jsonl").open():
        row = json.loads(line)
        key = (row["opportunity_id"], row["method"])
        if key in seen:
            raise ValueError("Duplicate forecast evaluation row")
        seen.add(key)
        p, y, sha, t = expected[key]
        if (
            row["outcome"] != y
            or row["feature_sha256"] != sha
            or not math.isclose(row["probability"], p, abs_tol=1e-12, rel_tol=0)
        ):
            raise ValueError("Independent feature/forecast arithmetic differs")
        metric = metrics[str(t) + "__" + row["method"]]
        metric["registered"] += 1
        if y is not None:
            metric["scored"] += 1
            metric["positive"] += y
            metric["losses"].append((p - y) ** 2)
    if seen != set(expected):
        raise ValueError("Incomplete bank evaluation coverage")
    result = read(args.bank / "RESULT.json")
    for key, metric in metrics.items():
        original = result["metrics"][key]
        for field in ("registered", "scored", "positive"):
            if metric[field] != original[field]:
                raise ValueError("Evaluation count mismatch")
        if not math.isclose(
            math.fsum(metric["losses"]),
            original["loss_sum"],
            abs_tol=1e-10,
            rel_tol=1e-10,
        ):
            raise ValueError("Independent Brier loss sum mismatch")
    publish(
        args.out / "RESULT.json",
        {
            "passed": True,
            "forecast_rows_verified": len(seen),
            "role_units": dict(Counter(r["role"] for r in examples)),
            "optimizer": optimizer,
            "source_bindings_verified": sum(
                len(freeze[k]) for k in ("input_files", "bank_files", "source_files")
            ),
            "immutable_source_resolutions": source_relocations,
            "refit_or_model_calls": 0,
            "confirmation_opened": False,
            "audit_boundary": "independent softmax/objective/gradient/scoring and identity replay; reuses frozen feature/provider extraction",
        },
    )
    print({"verified_rows": len(seen)}, flush=True)


if __name__ == "__main__":
    main()
