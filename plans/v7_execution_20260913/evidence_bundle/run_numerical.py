"""Real station arrays through typed scalar outputs, journals and common scores.

Historical initialization is not publication. This is a numerical integration
diagnostic; an EvidenceBundle for an online cutoff is intentionally not fabricated.
"""

from __future__ import annotations

import hashlib
import json
import statistics
from datetime import datetime
from pathlib import Path

from disastertrace.monitoring_fixed_v1.contracts import (
    Forecast,
    ForecastState,
    Target,
    fingerprint,
    paired_scores,
)

HERE = Path(__file__).resolve().parent


def utc_us(value):
    return round(
        datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1_000_000
    )


def save(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def main():
    input_path = HERE.parent / "sources_numerical/paired_records.json"
    data = json.loads(input_path.read_text())
    output = HERE / "numerical_01"
    output.mkdir(exist_ok=False)
    (output / "policy").mkdir()
    (output / "evaluator").mkdir()
    opportunities, arms, exclusions, roundtrips = (
        [],
        {"ensemble_mean": {}, "ensemble_median": {}},
        [],
        0,
    )
    for record in data["records"]:
        if record["lead_hours"] <= 0:
            exclusions.append(
                {
                    "record_id": record["record_id"],
                    "reason": "zero_lead_is_not_future_forecast",
                }
            )
            continue
        if not record["point_forecast_diagnostic_eligible"]:
            raise ValueError(
                "Source pairing is not qualified for this numerical diagnostic"
            )
        valid = utc_us(record["valid_time"])
        origin = utc_us(record["forecast_reference_time"])
        if valid - origin != record["lead_hours"] * 3_600_000_000:
            raise ValueError("Initialization, lead and valid time disagree")
        target = Target(
            "dwd-460-" + record["valid_time"],
            "DWD:460:Berus",
            record["variable"],
            record["unit"],
            "scalar",
            "point",
            valid,
            valid,
            "future_physical",
            "DWD_TT_TU_instant_UTC.v1",
        )
        visible = {
            "record_id": record["record_id"],
            "target": target.to_dict(),
            "forecast_reference_time": record["forecast_reference_time"],
            "lead_hours": record["lead_hours"],
            "forecast_members": record["model_visible"]["forecast_members"],
            "member_ids": record["model_visible"]["member_ids"],
            "publication_time": None,
            "visibility_contract": "static_published_benchmark_forecast_arrays_only",
        }
        if (
            len(visible["forecast_members"]) != 51
            or len(set(visible["member_ids"])) != 51
        ):
            raise ValueError("Incomplete pinned ensemble")
        save(output / "policy" / (record["record_id"] + ".json"), visible)
        for name, reducer in [
            ("ensemble_mean", statistics.mean),
            ("ensemble_median", statistics.median),
        ]:
            forecast = Forecast(
                target.contract_hash,
                "scalar",
                "K",
                reducer(visible["forecast_members"]),
            )
            target.check_forecast(forecast)
            arms[name][record["record_id"]] = forecast.to_dict()
            # A single offline journal event exercises exact type/state serialization.
            state = ForecastState(target, "base_bound_override")
            state.update_baseline(forecast, fingerprint(visible), origin)
            recovered = ForecastState.restore(json.loads(json.dumps(state.to_dict())))
            if recovered.effective(origin).to_dict() != forecast.to_dict():
                raise ValueError("Typed state roundtrip changed forecast")
            roundtrips += 1
        opportunities.append(
            {
                "opportunity_id": record["record_id"],
                "target": target.to_dict(),
                "outcome": record["evaluator_only"]["observation"],
                "quality": record["evaluator_only"]["dwd_QN_9"],
            }
        )
    save(output / "PREDICTIONS.json", arms)
    save(output / "evaluator/OUTCOMES.json", opportunities)
    scores = paired_scores(opportunities, arms)
    # Independent direct calculation checks the typed scorer and Celsius conversion.
    crosscheck = {}
    for name, predictions in arms.items():
        residuals_c = [
            abs(
                (predictions[r["opportunity_id"]]["value"] - 273.15)
                - (r["outcome"] - 273.15)
            )
            for r in opportunities
        ]
        expected = sum(residuals_c) / len(residuals_c)
        if abs(expected - scores["arms"][name]["mean_loss"]) > 1e-12:
            raise ValueError("Independent MAE/unit check failed")
        crosscheck[name] = expected
    report = {
        "schema": "disastertrace.numerical_integration.v1",
        "source_pairs": len(data["records"]),
        "scored_positive_lead_pairs": len(opportunities),
        "unique_valid_targets": len({r["target"]["target_id"] for r in opportunities}),
        "excluded_zero_lead": exclusions,
        "typed_state_roundtrips": roundtrips,
        "scores": scores,
        "independent_mae_celsius_check": crosscheck,
        "raw_DWD_observation_matches": data["dwd_crosscheck_count"],
        "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "numerical_point_output_and_scoring_passed": True,
        "historical_online_availability_verified": False,
        "active_monitoring_qualified": False,
        "independent_weather_confirmation": False,
        "new_model_calls": 0,
        "limits": [
            "One station, three init dates, correlated leads; no heatwave/cold-wave task",
            "Initialization-clock journal only; not public release or cutoff chronology",
            "No nontrivial acquisition E/shared-evidence mechanism yet",
            "SEEPS not scored: physical accumulation day boundaries remain unverified",
        ],
    }
    save(output / "REPORT.json", report)
    print(
        json.dumps(
            {
                "paired_records": len(opportunities),
                "roundtrips": roundtrips,
                "scores": scores,
            }
        )
    )


if __name__ == "__main__":
    main()
