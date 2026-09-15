"""Bounded planning probes against current modules; no weather or model run."""

import argparse
import copy
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from disastertrace.monitoring_v1 import api_capture_v2
from disastertrace.monitoring_v1.api_ledger import ApiLedger, call_spec
from disastertrace.monitoring_v1.feature_tasks import (
    parse_features,
    parse_temperature,
    temperature_ensemble_probability,
)
from disastertrace.monitoring_v1.temperature_postprocess import event_probability


def observe(function, *args):
    try:
        return {"returned": function(*args)}
    except Exception as exc:
        return {"exception": type(exc).__name__, "message": str(exc)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    if args.result.exists():
        raise SystemExit("Use a fresh result path")
    day = 86_400_000_000
    start = int(datetime(2018, 1, 2, tzinfo=timezone.utc).timestamp()) * 1_000_000
    base = {
        "cutoff": start - day,
        "target": {
            "units": "C",
            "physical_start": start,
            "physical_end": start + day,
            "variable": "daily_max_2m_temperature",
            "event_operator": "ge",
            "threshold": 30,
        },
        "common": {"daily_products": [{
            "target_date": "2018-01-02",
            "day_index": 1,
            "forecast_max_members_C": [31, 20],
            "forecast_min_members_C": [10, 5],
        }]},
    }
    cases = []

    def temperature_case(name, row):
        cases.append({
            "id": name,
            "feature_tasks": observe(temperature_ensemble_probability, row),
            "temperature_postprocess": observe(event_probability, row),
        })

    temperature_case("valid_utc_day", base)
    value = copy.deepcopy(base)
    value["target"]["physical_start"] += day // 2
    value["target"]["physical_end"] += day // 2
    temperature_case("midday_window", value)
    value = copy.deepcopy(base)
    duplicate = copy.deepcopy(value["common"]["daily_products"][0])
    duplicate["forecast_max_members_C"] = [35, 35]
    value["common"]["daily_products"].append(duplicate)
    temperature_case("duplicate_date", value)
    value["common"]["daily_products"].reverse()
    temperature_case("duplicate_date_reversed", value)
    value = copy.deepcopy(base)
    value["target"]["threshold"] = float("nan")
    temperature_case("nan_threshold", value)
    value = copy.deepcopy(base)
    value["common"]["daily_products"][0]["day_index"] = True
    temperature_case("boolean_day_index", value)
    value = copy.deepcopy(base)
    value["target"]["threshold"] = True
    temperature_case("boolean_threshold", value)

    def feature_case(name, lower, upper, lower_closed, upper_closed):
        raw = json.dumps({"slots": {"q": {
            "visibility": {"lower": lower, "upper": upper,
                           "lower_closed": lower_closed, "upper_closed": upper_closed},
            "temperature_c": None,
            "dewpoint_c": None,
        }}}, allow_nan=False)
        cases.append({"id": name, "parse_features": observe(parse_features, raw, ["q"])})

    feature_case("both_positive_infinity", "+inf", "+inf", True, True)
    feature_case("valid_censored_upper", 9656.064, "+inf", False, False)
    cases.append({"id": "huge_integer_probability",
                  "parse_temperature": observe(parse_temperature, '{"probability":' + '1' + '0' * 400 + '}')})
    cases.append({"id": "valid_probability", "parse_temperature": observe(parse_temperature, '{"probability":0.5}')})

    for mode in ("stop_after_claim", "deadline_after_claim"):
        with tempfile.TemporaryDirectory(prefix="dt-v11-planning-") as directory:
            root = Path(directory)
            messages = [{"role": "user", "content": "Synthetic transport probe only"}]
            spec = call_spec("synthetic", messages, "deepseek-flash", input_cap=8192, max_tokens=16)
            ledger = ApiLedger.create(root / "ledger", [spec],
                                      limit_nanodollars=spec["reserved_nanodollars"],
                                      max_calls=1, deadline_wall_ns=3_000_000_000)
            clock = [1_000_000_000]
            sends = []
            key_path = root / "synthetic.key"
            original_read_text = Path.read_text

            def synthetic_read(path, *pargs, **kwargs):
                if path == key_path:
                    if mode == "stop_after_claim":
                        ledger.stop("synthetic local stop")
                    else:
                        clock[0] = 4_000_000_000
                    return "not-a-real-credential"
                return original_read_text(path, *pargs, **kwargs)

            class OfflineOpener:
                def open(self, request, **kwargs):
                    sends.append({"wall_ns": clock[0]})
                    raise RuntimeError("Offline transport stub; no network")

            with patch.dict(os.environ, {"DISASTERTRACE_DEEPSEEK_KEY_FILE": str(key_path)}), \
                 patch.object(Path, "read_text", synthetic_read), \
                 patch.object(api_capture_v2.time, "time_ns", lambda: clock[0]), \
                 patch.object(api_capture_v2, "build_opener", return_value=OfflineOpener()):
                outcome = observe(api_capture_v2.capture, ledger, "synthetic", messages)
            cases.append({"id": mode, "transport_stub_calls": len(sends),
                          "actual_network_calls": 0, "capture": outcome})

    expectations = {
        "valid_utc_day": cases[0]["feature_tasks"] == {"returned": 0.5}
                         and cases[0]["temperature_postprocess"] == {"returned": 0.5},
        "six_temperature_differences": all("returned" in case["feature_tasks"]
                                           and case["temperature_postprocess"].get("exception") == "ValueError"
                                           for case in cases[1:7]),
        "infinite_lower_accepted": "returned" in cases[7]["parse_features"],
        "valid_upper_censoring_accepted": "returned" in cases[8]["parse_features"],
        "huge_integer_overflow": cases[9]["parse_temperature"].get("exception") == "OverflowError",
        "valid_probability_accepted": "returned" in cases[10]["parse_temperature"],
        "post_claim_gates_allow_stub_dispatch": all(case["transport_stub_calls"] == 1 for case in cases[11:]),
    }
    result = {
        "schema": "disastertrace.v11.planning_probes.v1",
        "at": datetime.now(timezone.utc).isoformat(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "scope": "13 synthetic cases, direct current-package imports; API transport replaced",
        "production_source_changed": False,
        "historical_weather_inputs_scanned": False,
        "model_calls": 0,
        "network_calls": 0,
        "credentials_read": False,
        "cases": cases,
        "expected_observations": expectations,
        "all_observed_as_expected": all(expectations.values()),
        "interpretation": "Observed gaps are not passing production correctness tests or proven historical score impact",
    }
    args.result.parent.mkdir(parents=True, exist_ok=True)
    with args.result.open("x") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"result": str(args.result), "cases": len(cases),
                      "all_observed_as_expected": result["all_observed_as_expected"]}))
    if not result["all_observed_as_expected"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
