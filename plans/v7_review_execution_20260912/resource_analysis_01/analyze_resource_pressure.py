"""Describe which declared resources were actually used by verified model runs."""

from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from analyze_calendar import digest, load, write

BASE = Path(__file__).resolve().parent


def main(args):
    args.output.mkdir(exist_ok=False)
    shutil.copyfile(__file__, args.output / "analyze_resource_pressure.py")
    analyses, bindings, session_rows = {}, {}, []
    for directory in args.analyses:
        path = directory / "REPORT.json"
        report = load(path)
        bindings[str(path.resolve())] = digest(path)
        rows = defaultdict(list)
        for original, expected in report["input_bindings"].items():
            trace_path = Path(original)
            if trace_path.name != "TRACE.json" or not trace_path.parent.parent.name.startswith("worker-"):
                continue
            if not trace_path.is_file():
                suffix = trace_path.parts[trace_path.parts.index(BASE.name) + 1:]
                trace_path = BASE.joinpath(*suffix)
            if digest(trace_path) != expected:
                raise ValueError("Calendar trace differs from its checked binding")
            bindings[str(trace_path.resolve())] = expected
            trace = load(trace_path)
            batch = trace_path.parents[2]
            plan_path = batch / "PLAN.json"
            plan = load(plan_path)
            if digest(plan_path) != trace["plan_sha256"]:
                raise ValueError("Trace does not match model plan")
            bindings[str(plan_path.resolve())] = digest(plan_path)
            worker = trace_path.parent.parent.name.removeprefix("worker-")
            cfg = trace["config"]
            arm = "/".join(("model", plan["worker_models"][worker], cfg["selector_kind"], cfg["protocol"]))
            spent = trace["resource_spent"]
            if any(trace["resource_reserved"].values()):
                raise ValueError("Completed trace has outstanding reservations")
            model_limit = cfg.get("model_call_budget", cfg["forecast_call_cap"])
            limits = {"requests": cfg["request_budget"], "tokens": cfg["token_cap"], "compute_ms": cfg["compute_ms_cap"]}
            if trace["actual_model_calls"] > model_limit or any(spent[k] > cap for k, cap in limits.items()):
                raise ValueError("Verified run exceeds a declared resource cap")
            calls = trace["calls"]
            selectors = trace.get("selector_calls", [])
            if len(calls) + len(selectors) != trace["actual_model_calls"]:
                raise ValueError("Selector and forecast calls do not reconcile")
            confusion = Counter(f"{c['expected_e_from_disclosed_products']} -> {c['reported_e']}" for c in calls)
            row = {"analysis": directory.name, "arm": arm, "run_id": trace["run_id"],
                   "source_trace": str(trace_path.resolve()), "limits": limits, "spent": spent,
                   "resource_fractions": {k: spent[k] / cap for k, cap in limits.items()},
                   "model_call_limit": model_limit, "actual_model_calls": trace["actual_model_calls"],
                   "model_call_limit_reached": trace["actual_model_calls"] == model_limit,
                   "source_request_limit_reached": spent["requests"] == cfg["request_budget"],
                   "forecast_calls": len(calls), "selector_calls": len(selectors),
                   "remaining_covers_one_forecast_reservation_dimensions": {
                       "tokens": cfg["token_cap"] - spent["tokens"] >= cfg["input_token_cap"] + cfg["output_token_cap"],
                       "compute_ms": cfg["compute_ms_cap"] - spent["compute_ms"] >= cfg["call_compute_cap_ms"],
                   },
                   "attempt_statuses": dict(Counter(a["status"] for a in trace["attempts"])),
                   "selector_response_errors": sum(c["response_error"] is not None for c in selectors),
                   "forecast_response_errors": sum(c["response_error"] is not None for c in calls),
                   "forecast_E_correct": sum(c["reported_e"] == c["expected_e_from_disclosed_products"] for c in calls),
                   "forecast_E_confusion": dict(confusion)}
            rows[arm].append(row)
            session_rows.append(row)
        arms = {}
        for arm, sessions in rows.items():
            reference = report["arms"][arm]["costs_and_process"]
            sums = Counter()
            confusion, statuses = Counter(), Counter()
            for session in sessions:
                for name in ("actual_model_calls", "forecast_calls", "selector_calls", "forecast_E_correct",
                             "selector_response_errors", "forecast_response_errors"):
                    sums[name] += session[name]
                confusion.update(session["forecast_E_confusion"])
                statuses.update(session["attempt_statuses"])
            expected_values = {"actual_model_calls": "actual_model_calls", "forecast_calls": "forecast_updates",
                               "selector_calls": "selector_calls", "forecast_E_correct": "E_correct_on_updated_targets",
                               "forecast_response_errors": "invalid_forecast_responses"}
            if len(sessions) != reference["resource_sessions"] or any(sums[k] != reference[v] for k, v in expected_values.items()):
                raise ValueError("Resource and E counts differ from checked calendar analysis")
            for dimension in limits:
                if sum(s["spent"][dimension] for s in sessions) != reference["resource_" + dimension]:
                    raise ValueError("Resource sum differs from checked calendar analysis")
            arms[arm] = {"sessions": len(sessions), **dict(sums),
                         "sessions_model_call_limit_reached": sum(s["model_call_limit_reached"] for s in sessions),
                         "sessions_source_request_limit_reached": sum(s["source_request_limit_reached"] for s in sessions),
                         "selector_share_of_model_calls": sums["selector_calls"] / sums["actual_model_calls"] if sums["actual_model_calls"] else None,
                         "forecast_E_accuracy_on_updated_targets": sums["forecast_E_correct"] / sums["forecast_calls"] if sums["forecast_calls"] else None,
                         "forecast_E_confusion": dict(confusion), "attempt_statuses": dict(statuses),
                         "resource_fraction_by_session": {
                             dim: {"minimum": min(s["resource_fractions"][dim] for s in sessions),
                                   "maximum": max(s["resource_fractions"][dim] for s in sessions),
                                   "aggregate": sum(s["spent"][dim] for s in sessions) / sum(s["limits"][dim] for s in sessions)}
                             for dim in limits},
                         "sessions_final_slack_allows_one_forecast_tokens_and_compute_only": sum(
                             all(s["remaining_covers_one_forecast_reservation_dimensions"].values()) for s in sessions)}
        if set(arms) != {k for k in report["arms"] if k.startswith("model/")}:
            raise ValueError("Not all verified model arms were accounted for")
        analyses[directory.name] = arms
    result = {"created_at": datetime.now(timezone.utc).isoformat(), "analyses": analyses,
              "input_bindings": bindings, "implementation_sha256": digest(args.output / "analyze_resource_pressure.py"),
              "new_model_calls": 0, "new_network_requests": 0,
              "interpretation": [
                  "Post-hoc resource-use diagnosis of completed frozen matrices; no budget was retuned.",
                  "Source-slot and model-call caps are experimental constraints, not measured external scarcity.",
                  "Unused token/compute quota is not a measured active constraint; final slack does not establish a counterfactual legal action under other constraints.",
                  "Calendar E accuracy is conditional on the method's updated targets, not comparable coverage or a balanced benchmark accuracy.",
                  "An accepted override is a protocol outcome, not proof of predictive gain; unchanged predictions can reflect deliberate baseline following.",
              ]}
    write(args.output / "REPORT.json", result)
    write(args.output / "SESSIONS.json", session_rows)
    lines = ["# Resource-use and full-calendar E diagnostics", "",
             "All values reconstruct from traces already bound to completed calendar reports.",
             "Source requests count archive slots; real bulk transport is a separate audit.", "",
             "| Calendar | Arm | Calls | Selector calls | Token quota used | Compute quota used | Accepted overrides | E correct / forecast calls |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for name, arms in analyses.items():
        for arm, values in arms.items():
            fractions = values["resource_fraction_by_session"]
            lines.append(f"| {name} | {arm} | {values['actual_model_calls']} | {values['selector_calls']} | "
                         f"{fractions['tokens']['aggregate']:.2%} | {fractions['compute_ms']['aggregate']:.2%} | "
                         f"{values['attempt_statuses'].get('accepted', 0)} | {values['forecast_E_correct']}/{values['forecast_calls']} |")
    lines += ["", "Session minima/maxima, remaining reservation slack, complete E confusion and response errors are in REPORT.json and SESSIONS.json.",
              "E denominators differ by selected target and exposed evidence; these rows do not rank selectors on a common E test set.",
              "The balanced 96-case E diagnostic is a different diagnostic distribution and cannot replace full-calendar results.",
              "A low Brier gain with no accepted overrides does not establish whether a better selector or forecaster would improve this task.", ""]
    (args.output / "REPORT.md").write_text("\n".join(lines))
    print(json.dumps({"calendars": len(analyses), "sessions": len(session_rows), "new_model_calls": 0}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--analyses", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
