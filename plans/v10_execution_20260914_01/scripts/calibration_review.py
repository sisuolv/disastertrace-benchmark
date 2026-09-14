"""Real calibration support and fixed total-prior sensitivity; never choose on test loss."""

import argparse
import importlib.util
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from disastertrace.monitoring_v1.calibration import predict
from disastertrace.monitoring_v1.calibration_diagnostics import trace_prediction
from disastertrace.monitoring_v1.regional_calibration import (
    apply_monotone,
    fit_monotone,
)
from disastertrace.monitoring_v1.regional_calibration_v2 import (
    coherent_cdf,
    fit_fixed_prior,
)
from disastertrace.monitoring_v1.spool_backend import digest, publish, read
from disastertrace.monitoring_v1.targets import canonical_hash


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--historical", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(exist_ok=False)
    old = args.historical
    path = old / "scripts/fit_regional_baselines.py"
    spec = importlib.util.spec_from_file_location("frozen_fit_examples", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    manifest = read(old / "reports/process_manifest_02/DATA_PROCESS_MANIFEST.json")[
        "rows"
    ]
    cards, traces, coherent = [], [], []
    for region in ["bay", "new_york", "chicago", "denver"]:
        folder = old / "reports/regional_baselines_01" / region
        raw, bank = read(folder / "BANK_RAW.json"), read(folder / "BANK.json")
        rows = [r for r in manifest if r["region"] == region]
        training = [r for r in rows if r["role"] in {"fit", "calibration"}]
        data = old / "regional_training_02" / region / "dataset_v2"
        fitted, calibrated = (
            read(folder / "FIT_IDS.json"),
            read(folder / "CALIBRATION_IDS.json"),
        )
        if set(fitted) & set(calibrated):
            raise ValueError("Cross-role target reuse")
        asset_roles = defaultdict(set)
        for row in training:
            for asset in row["native_versions"]:
                asset_roles[asset].add(row["role"])
        if any(len(v) > 1 for v in asset_roles.values()):
            raise ValueError("Native version crosses roles")
        bins, identities = defaultdict(list), defaultdict(set)
        for row, target, candidate, qids, views in module.examples(data, training):
            if row["role"] != "calibration":
                continue
            threshold = str(target["threshold"])
            p = predict(raw, target, candidate)["probability"]
            bins[threshold, "base"].append((p, row["outcome"], 1.0))
            identities[threshold, "base"].add(row["opportunity_id"])
            for view in views:
                p = predict(raw, target, candidate, qids, view)["probability"]
                bins[threshold, "evidence"].append((p, row["outcome"], 1 / len(views)))
                identities[threshold, "evidence"].add(row["opportunity_id"])
        alternatives = {}
        for (threshold, family), observations in bins.items():
            recomputed = fit_monotone(observations)
            if recomputed != bank["post_calibration"][threshold][family]:
                raise ValueError("Frozen regional bank does not reconstruct")
            n = math.fsum(r[2] for r in observations)
            positive = math.fsum(r[1] * r[2] for r in observations)
            k = len({r[0] for r in observations})
            fixed = fit_fixed_prior(observations)
            zero = fit_fixed_prior(observations, prior_mass=0)
            alternatives[threshold + "__" + family] = {
                "fixed_total_prior_2": fixed,
                "unregularized_pav": zero,
            }
            cards.append(
                {
                    "region": region,
                    "threshold": threshold,
                    "family": family,
                    "unique_opportunities": len(identities[threshold, family]),
                    "weighted_n": n,
                    "weighted_positive": positive,
                    "distinct_raw_scores": k,
                    "historical_prior_mass": 2 * k,
                    "prior_to_data_ratio": 2 * k / n,
                    "fitted_targets": len(fitted),
                    "calibration_targets": len(calibrated),
                    "zero_positive_calibration": positive == 0,
                    "bank_exactly_reconstructed": True,
                    "source_bank_sha256": digest(folder / "BANK.json"),
                }
            )
        publish(args.out / (region + "__CALIBRATION_SENSITIVITY.json"), alternatives)
        evaluation = defaultdict(list)
        for row in rows:
            if row["role"] == "development_evaluation":
                evaluation[row["dataset"]].append(row)
        paired = defaultdict(dict)
        for dataset, subset in evaluation.items():
            for row, target, candidate, qids, views in module.examples(
                Path(dataset), subset
            ):
                known = views[-1] if views else {}
                trace = trace_prediction(bank, target, candidate, qids, known)
                trace.update(
                    region=region,
                    opportunity_id=row["opportunity_id"],
                    threshold=target["threshold"],
                    outcome=row["outcome"],
                    process_group_id=row["process_group_id"],
                )
                for name, blocks in alternatives[
                    str(target["threshold"]) + "__" + trace["calibration_family"]
                ].items():
                    trace[name] = apply_monotone(blocks, trace["raw_probability"])
                traces.append(trace)
                # Threshold-free identity must bind exactly the same native input.
                native = (
                    None
                    if candidate is None
                    else {
                        k: candidate.get(k)
                        for k in [
                            "issued_at",
                            "available_at",
                            "native_semantics_sha256",
                            "projection",
                        ]
                    }
                )
                information = canonical_hash(
                    {
                        "native": native,
                        "evidence": known,
                        "query_ids": qids,
                        "entity": target["entity"],
                        "start": target["physical_start"],
                        "end": target["physical_end"],
                        "cutoff": row["cutoff"],
                    }
                )
                key = (
                    row["station"],
                    target["physical_start"],
                    target["physical_end"],
                    row["cutoff"],
                )
                paired[key][target["threshold"]] = {
                    "information": information,
                    "trace": trace,
                }
        for key, values in paired.items():
            if set(values) != {1000, 5000}:
                continue
            low, high = values[1000], values[5000]
            same = low["information"] == high["information"]
            ps = [low["trace"]["post_probability"], high["trace"]["post_probability"]]
            coherent.append(
                {
                    "region": region,
                    "key": key,
                    "same_information": same,
                    "probabilities": ps,
                    "crossing": same and ps[0] > ps[1],
                    "projected_sensitivity": coherent_cdf(
                        ps, [low["information"], high["information"]]
                    )
                    if same
                    else None,
                }
            )
    with (args.out / "FIXED_EVIDENCE_ATTRIBUTION.jsonl").open("x") as stream:
        for row in traces:
            stream.write(json.dumps(row, sort_keys=True) + "\n")
    publish(
        args.out / "COHERENCE.json",
        {
            "pairs": coherent,
            "counts": dict(
                Counter(
                    "same_information_crossing"
                    if r["crossing"]
                    else "same_information_coherent"
                    if r["same_information"]
                    else "different_information_not_projected"
                    for r in coherent
                )
            ),
        },
    )
    publish(
        args.out / "RESULT.json",
        {
            "passed": True,
            "support_cards": cards,
            "trace_rows": len(traces),
            "new_banks_selected": False,
            "calibration_candidates": "fixed total prior2 and zero prior, declared before their evaluation",
            "scope": "Development sensitivity only; original four banks and scores unchanged",
            "confirmation_opened": False,
        },
    )
    print(
        json.dumps(
            {"passed": True, "support_cards": len(cards), "trace_rows": len(traces)}
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
