"""Audit recorded calls without creating responses for uncalled opportunities."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PRIOR = REPO / "plans/v7_review_execution_20260912"
sys.path.insert(0, str(REPO / "disastertrace-starter/src"))

from disastertrace.monitoring_v1.calibration import feature_key, predict  # noqa: E402
from disastertrace.monitoring_v1.policies import parse_answer  # noqa: E402

COHORTS = {
    "bay2024": ("calendar_analysis_bay_02", "calibration_bank_01", 5000),
    "front2024": ("calendar_analysis_front_02", "calibration_bank_01", 1000),
    "front2026": ("calendar_analysis_replication_01", "calibration_bank_2025_01", 1000),
}


def read(path):
    data = Path(path).read_bytes()
    return json.loads(data), hashlib.sha256(data).hexdigest()


def dump(path, value):
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def index_unique(rows, key):
    result = {r[key]: r for r in rows}
    if len(result) != len(rows):
        raise ValueError("Duplicate " + key)
    return result


def direction(value):
    return "improved" if value > 1e-12 else "worsened" if value < -1e-12 else "unchanged"


def independent_scores(rows):
    """Use fsum and the binary formula, without the production score function."""
    index_unique(rows, "opportunity_id")
    settled = [r for r in rows if r["outcome"] is not None]
    for row in rows:
        if row["outcome"] is not None and type(row["outcome"]) is not int:
            raise ValueError("Non-integer binary outcome")
        if row["outcome"] not in (None, 0, 1):
            raise ValueError("Non-binary outcome")
        if any(type(row[k]) not in (int, float) or not math.isfinite(row[k]) or not 0 <= row[k] <= 1
               for k in ("base", "prediction")):
            raise ValueError("Invalid prediction")
    n = len(settled)
    base = math.fsum((r["base"] - r["outcome"]) ** 2 for r in settled)
    system = math.fsum((r["prediction"] - r["outcome"]) ** 2 for r in settled)
    gains = [(r["base"] - r["outcome"]) ** 2 - (r["prediction"] - r["outcome"]) ** 2 for r in settled]
    missing = defaultdict(lambda: [0.0, 0.0])
    for row in rows:
        if row["outcome"] is None:
            for y in (0, 1):
                missing[row["target_id"]][y] += (row["base"] - y) ** 2 - (row["prediction"] - y) ** 2
    known = math.fsum(gains)
    return {
        "opportunities": len(rows), "settled": n, "missing": len(rows) - n,
        "base_brier": base / n if n else None,
        "system_brier": system / n if n else None,
        "net_realized_gain": known / n if n else None,
        "g_plus": math.fsum(max(0, g) for g in gains) / n if n else None,
        "g_minus": math.fsum(max(0, -g) for g in gains) / n if n else None,
        "full_population_gain_bounds": [
            (known + math.fsum(min(v) for v in missing.values())) / len(rows),
            (known + math.fsum(max(v) for v in missing.values())) / len(rows),
        ] if rows else None,
    }


def validate_common_rows(rows_by_arm):
    anchor = None
    for label, rows in rows_by_arm.items():
        values = index_unique(rows, "opportunity_id")
        view = {k: (r["target_id"], r["outcome"], r["base"], r["cutoff"]) for k, r in values.items()}
        if anchor is not None and view != anchor:
            raise ValueError("Common opportunity/outcome/baseline contract differs: " + label)
        anchor = view
    return anchor


def backoff(bank, target, candidate, query_ids=(), disclosed=None):
    attempts = []
    if disclosed:
        attempts.append(("evidence_cell", feature_key(target, candidate, query_ids, disclosed)))
    attempts.append(("taf_cell", feature_key(target, candidate)))
    attempts.append(("threshold_pool", json.dumps([target["threshold"], "pooled"], separators=(",", ":"))))
    visited = []
    selected = None
    for name, key in attempts:
        cell = bank["cells"].get(key)
        status = "absent" if cell is None else "below_minimum_n" if cell["n"] < bank["minimum_cell_n"] and name != "threshold_pool" else "selected"
        visited.append({"level": name, "key": key, "n": None if cell is None else cell["n"], "status": status})
        if status == "selected":
            selected = {"level": name, "cell_key": key, "n": cell["n"], "positive": cell["positive"],
                        "probability": (cell["positive"] + 1) / (cell["n"] + 2), "attempts": visited}
            break
    if selected is None:
        raise ValueError("Missing threshold fallback")
    original = predict(bank, target, candidate, query_ids, disclosed)
    if original["cell_key"] != selected["cell_key"] or original["probability"] != selected["probability"]:
        raise ValueError("Independent backoff disagrees with frozen mapper")
    return selected


def captured_request(path, expected_call):
    capture, digest = read(path)
    if capture["call_id"] != expected_call:
        raise ValueError("Capture call identity differs")
    user_messages = [m["content"] for m in capture["messages"] if m["role"] == "user"]
    if len(user_messages) != 1:
        raise ValueError("Ambiguous captured request")
    return json.loads(user_messages[0]), digest


def audit_session(trace, requests, anchor, bank, native_index):
    if trace["config"].get("gate"):
        raise ValueError("This audit's model scope excludes gated trajectories")
    calls = index_unique(trace["calls"], "call_id")
    attempts = index_unique(trace["attempts"], "call_id")
    if set(calls) != set(attempts) or set(calls) != set(requests):
        raise ValueError("Call/attempt/request identities fail reconciliation")
    selectors = index_unique(trace.get("selector_calls", []), "call_id")
    if trace["actual_model_calls"] != len(calls) + len(selectors):
        raise ValueError("Predictor and selector calls fail reconciliation")
    snapshots = index_unique(trace["snapshots"], "opportunity_id")
    snapshot_by_call = defaultdict(list)
    for row in snapshots.values():
        expected = anchor[row["opportunity_id"]]
        if (row["probability"], row["base_probability"], row["target_id"], row["cutoff"]) != (expected["prediction"], expected["base"], expected["target_id"], expected["cutoff"]):
            raise ValueError("Actual snapshot differs from published rows")
        if row["override_call_id"] is not None:
            if row["override_call_id"] not in calls:
                raise ValueError("Snapshot refers to unrecorded candidate")
            if attempts[row["override_call_id"]]["status"] != "accepted":
                raise ValueError("Snapshot adopted an unaccepted candidate")
            snapshot_by_call[row["override_call_id"]].append(row)
    counters = Counter({
        "sessions": 1, "registered_opportunities": len(snapshots),
        "actual_model_calls": trace["actual_model_calls"], "predictor_calls": len(calls),
        "selector_calls": len(selectors), "recorded_candidates": len(attempts),
        "selector_invalid_responses": sum(r["response_error"] is not None for r in selectors.values()),
        "sessions_at_model_call_cap": int(trace["actual_model_calls"] == trace["config"].get("model_call_budget", trace["config"]["forecast_call_cap"])),
        "snapshots_in_override_mode": sum(r["mode"] == "override" for r in snapshots.values()),
        "snapshots_different_from_base": sum(r["probability"] != r["base_probability"] for r in snapshots.values()),
    })
    counters.update("state_end:" + r["reason"] for r in trace["state_audit"] if r["kind"] == "override_end")
    candidate_rows = []
    for call_id, call in calls.items():
        request = requests[call_id]
        attempt = attempts[call_id]
        if (request["opportunity_id"], request["clock"]) != (call["opportunity_id"], call["started_at"]):
            raise ValueError("Request opportunity or clock differs")
        if request["common_baseline"]["context_hash"] != attempt["snapshot_context_hash"]:
            raise ValueError("Captured base is not the call's snapshot")
        if request["target"]["target_id"] != attempt["target_id"]:
            raise ValueError("Target mismatch")
        parse_error = None
        try:
            parsed = parse_answer(call["raw"])
            if not call["details"].get("ended_with_eos", True):
                raise ValueError("Generation did not finish with EOS")
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            parse_error = str(error)
            parsed = None
        if (parse_error is None) != (call["response_error"] is None):
            raise ValueError("Stored response validity differs from reparsing")
        if parsed is not None and (parsed["probability"], parsed["decision"], parsed["e_status"]) != (call["proposed_probability"], call["decision"], call["reported_e"]):
            raise ValueError("Stored candidate differs from actual raw response")
        valid = parsed is not None
        visible_assets = {r["asset_id"] for r in request["read_evidence"]}
        citation_errors = [] if parsed is None else [x for x in parsed["citations"] if x not in visible_assets]
        if citation_errors != call["citation_errors"]:
            raise ValueError("Citation audit differs from visible assets")
        adopted = snapshot_by_call[call_id]
        effective = [r for r in adopted if r["probability"] != r["base_probability"]]
        target = request["target"]
        base = request["common_baseline"]
        candidate = None
        if base["product_revision_id"] != "frozen_fallback":
            native = native_index[base["product_revision_id"]]
            candidate = {"projection": base["relevant_content"], "issued_at": native["issued_at"]}
            if "segments" not in base["relevant_content"]:
                candidate["projection_status"] = "unavailable"
        disclosed = {r["content"]["query_id"]: r["content"] for r in request["read_evidence"]}
        mapped_base = backoff(bank, target, candidate)
        mapped_evidence = backoff(bank, target, candidate, request["registered_query_ids"], disclosed)
        if base["probability"] != mapped_base["probability"]:
            raise ValueError("Captured baseline probability cannot be reconstructed")
        outcome = anchor[request["opportunity_id"]]["outcome"]
        p = call["proposed_probability"]
        gain = None if not valid or outcome is None else (base["probability"] - outcome) ** 2 - (p - outcome) ** 2
        changes_base = valid and p != base["probability"]
        changes_state = valid and p != request["current_state"]["probability"]
        row = {
            "call_id": call_id, "opportunity_id": request["opportunity_id"], "target_id": target["target_id"],
            "started_at": call["started_at"], "completed_at": call["completed_at"], "intended_cutoff": request["cutoff"],
            "valid_response": valid, "response_error": call["response_error"], "citation_errors": citation_errors,
            "decision": call["decision"], "status": attempt["status"],
            "proposed_probability": p, "base_at_start": base["probability"],
            "baseline_kind_at_start": base.get("baseline_kind", "unspecified"),
            "current_probability_at_start": request["current_state"]["probability"],
            "differs_from_base_at_start": changes_base, "differs_from_current_state_at_start": changes_state,
            "base_context_survived_completion": attempt["snapshot_context_hash"] == attempt["current_context_hash"],
            "completed_by_intended_cutoff": call["completed_at"] <= request["cutoff"],
            "adopted_snapshot_ids": [r["opportunity_id"] for r in adopted],
            "nonbase_adopted_snapshot_ids": [r["opportunity_id"] for r in effective],
            "read_query_ids": sorted(disclosed), "expected_e": call["expected_e_from_disclosed_products"],
            "reported_e": call["reported_e"],
            "baseline_mapping": mapped_base, "actual_disclosed_mapping": mapped_evidence,
            "outcome_evaluator_only": outcome, "static_candidate_gain_vs_start_base_evaluator_only": gain,
        }
        candidate_rows.append(row)
        counters.update({
            "valid_responses": int(valid), "invalid_responses": int(not valid),
            "candidate_changes_base_at_start": int(changes_base),
            "candidate_changes_current_state_at_start": int(changes_state),
            "valid_override_decisions": int(valid and call["decision"] == "override"),
            "override_decisions_with_nonbase_proposal": int(valid and call["decision"] == "override" and changes_base),
            "follow_or_nochange_with_nonbase_proposal": int(valid and call["decision"] != "override" and changes_base),
            "accepted_candidates": int(attempt["status"] == "accepted"),
            "accepted_without_any_snapshot": int(attempt["status"] == "accepted" and not adopted),
            "candidates_adopted_by_any_snapshot": int(bool(adopted)),
            "candidates_adopted_as_nonbase_by_any_snapshot": int(bool(effective)),
            "candidates_late_for_intended_cutoff": int(call["completed_at"] > request["cutoff"]),
            "candidates_context_changed_during_call": int(not row["base_context_survived_completion"]),
            "calls_with_read_evidence": int(bool(disclosed)),
            "citation_error_calls": int(bool(citation_errors)),
            "accepted_with_citation_errors": int(bool(citation_errors) and attempt["status"] == "accepted"),
            "e_correct_calls": int(call["reported_e"] == call["expected_e_from_disclosed_products"]),
            "calls_with_unavailable_taf_projection": int(candidate is not None and candidate.get("projection_status") == "unavailable"),
        })
        counters["decision:" + call["decision"]] += 1
        counters["attempt:" + attempt["status"]] += 1
        counters["actual_disclosed_mapping:" + mapped_evidence["level"]] += 1
        if gain is not None:
            counters["static_called_candidate:" + direction(gain)] += 1
    addressed = {c["opportunity_id"] for c in calls.values()}
    counters["distinct_directly_called_opportunities"] = len(addressed)
    counters["opportunities_without_direct_call"] = len(snapshots) - len(addressed)
    # A candidate for an earlier lead can lawfully persist to a later opportunity.
    counters["opportunities_without_direct_call_but_adopted_override"] = sum(
        r["opportunity_id"] not in addressed and r["override_call_id"] is not None for r in snapshots.values()
    )
    return dict(counters), candidate_rows


def summarize_backoff(rows, field):
    levels = Counter(row[field]["level"] for row in rows)
    failures = Counter(a["level"] + ":" + a["status"] for row in rows for a in row[field]["attempts"] if a["status"] != "selected")
    cells = defaultdict(list)
    for row in rows:
        cells[row[field]["cell_key"]].append(row)
    return {"rows": len(rows), "selected_levels": dict(levels), "fallthrough_reasons": dict(failures),
            "selected_cells": [{"key": key, "uses": len(values), "fit_n": values[0][field]["n"],
                                "fit_positive": values[0][field]["positive"], "probability": values[0][field]["probability"]}
                               for key, values in sorted(cells.items())]}


def main(args):
    args.output.mkdir(parents=True, exist_ok=False)
    bindings = {}
    reports, score_report, backoff_report = {}, {}, {}
    all_counts = Counter()
    with (args.output / "CALL_LINKS.jsonl").open("x") as links:
        for cohort, (analysis_name, bank_name, threshold) in COHORTS.items():
            analysis_path = PRIOR / analysis_name / "REPORT.json"
            analysis, bindings[str(analysis_path.relative_to(REPO))] = read(analysis_path)
            rows_path = PRIOR / analysis_name / "ROWS.json"
            rows, bindings[str(rows_path.relative_to(REPO))] = read(rows_path)
            validate_common_rows(rows)
            dataset = REPO / analysis["dataset"]
            outcomes_path = dataset / "private/OUTCOMES.json"
            outcomes, digest = read(outcomes_path)
            if digest != analysis["outcomes_sha256"]:
                raise ValueError("Frozen result table changed")
            bindings[str(outcomes_path.relative_to(REPO))] = digest
            outcomes = index_unique(outcomes, "target_id")
            for values in rows.values():
                if any(r["outcome"] != outcomes[r["target_id"]]["outcome"] for r in values):
                    raise ValueError("Row result differs from frozen result table")
            bank_path = PRIOR / bank_name / "BANK.json"
            bank, bindings[str(bank_path.relative_to(REPO))] = read(bank_path)
            native_path = dataset / "environment/NATIVE_PRODUCT_INDEX.json"
            native, bindings[str(native_path.relative_to(REPO))] = read(native_path)
            native_index = index_unique(native, "source_id")
            arm_counts = defaultdict(Counter)
            arm_backoff = defaultdict(list)
            arm_scores = {}
            for label, values in rows.items():
                checked = independent_scores(values)
                expected = analysis["arms"][label]["scores"]
                differences = {}
                for key, actual in checked.items():
                    if key == "full_population_gain_bounds":
                        continue
                    reference = expected[key]
                    if actual is None or reference is None:
                        if actual != reference:
                            raise ValueError("Null score mismatch")
                    elif abs(actual - reference) > 1e-12:
                        raise ValueError("Independent score mismatch " + label + "/" + key)
                    differences[key] = None if actual is None else actual - reference
                # Production brier_report uses per-opportunity bounds; calendar paired report
                # additionally enforces one common unknown outcome per repeated target.
                target_bounds = analysis["arms"][label]["relative_to_common_base"]["full_population_gain_bounds"]
                if any(abs(a - b) > 1e-12 for a, b in zip(checked["full_population_gain_bounds"], target_bounds)):
                    raise ValueError("Repeated-target missingness bounds mismatch")
                arm_scores[label] = {"independent_scores": checked, "difference_from_saved_score": differences,
                                     "target_consistent_missingness_bounds_match": True}
            score_report[cohort] = {"arms": arm_scores, "common_masks_and_baselines_identical": True,
                                    "unique_opportunities": len(next(iter(rows.values())))}
            verified_paths = [Path(p) for p in analysis["input_bindings"] if p.endswith("/VERIFIED.json")]
            for verified_path in verified_paths:
                verified, digest = read(verified_path)
                if digest != analysis["input_bindings"][str(verified_path)]:
                    raise ValueError("Frozen verification changed")
                bindings[str(verified_path.relative_to(REPO))] = digest
                batch = PRIOR / Path(verified["batch"]).name
                plan_path = batch / "PLAN.json"
                plan, digest = read(plan_path)
                if digest != verified["plan_sha256"]:
                    raise ValueError("Frozen plan changed")
                bindings[str(plan_path.relative_to(REPO))] = digest
                for identity, checked in verified["reports"].items():
                    worker, run = identity.split(":", 1)
                    label = "/".join(("model", plan["worker_models"][worker], checked["config"]["selector_kind"], checked["config"]["protocol"]))
                    trace_path = batch / ("worker-" + worker) / run / "TRACE.json"
                    trace, digest = read(trace_path)
                    if digest != analysis["input_bindings"][str(trace_path)] or trace["config"] != checked["config"]:
                        raise ValueError("Frozen trace/config changed")
                    if trace.get("outcome_table_accessed_by_policy") or trace["plan_sha256"] != verified["plan_sha256"]:
                        raise ValueError("Isolation or plan binding failed")
                    bindings[str(trace_path.relative_to(REPO))] = digest
                    calls = trace["calls"]
                    paths = [trace_path.parent / (c["details"]["capture_prefix"] + "-request.json") for c in calls]
                    with ThreadPoolExecutor(max_workers=8) as pool:
                        captures = list(pool.map(lambda pc: captured_request(*pc), zip(paths, [c["call_id"] for c in calls])))
                    requests = {}
                    for path, call, (request, capture_digest) in zip(paths, calls, captures):
                        bindings[str(path.relative_to(REPO))] = capture_digest
                        requests[call["call_id"]] = request
                    anchor = index_unique(rows[label], "opportunity_id")
                    counts, call_rows = audit_session(trace, requests, anchor, bank, native_index)
                    for row in call_rows:
                        row.update(cohort=cohort, arm=label, session=str(trace_path.parent.relative_to(REPO)))
                        links.write(json.dumps(row, separators=(",", ":"), allow_nan=False) + "\n")
                    arm_counts[label].update(counts)
                    arm_backoff[label].extend({"actual_disclosed_mapping": r["actual_disclosed_mapping"]} for r in call_rows)
                    all_counts.update(counts)
                    print(cohort + ": " + identity + " audited", flush=True)
            reports[cohort] = {"arms": {k: dict(v) for k, v in arm_counts.items()},
                               "unique_registered_opportunities": len(next(iter(rows.values()))),
                               "gate": "absent in all audited model configs; no uncalled gate candidates imputed",
                               "all_opportunity_candidate_rows_created": False}
            for label, counts in arm_counts.items():
                process = analysis["arms"][label]["costs_and_process"]
                if counts["actual_model_calls"] != process["actual_model_calls"] or counts["predictor_calls"] != process["forecast_updates"]:
                    raise ValueError("Published model count reconciliation failed")
            targets_path = dataset / "public/TARGETS.json"
            target_values, digest = read(targets_path)
            bindings[str(targets_path.relative_to(REPO))] = digest
            targets = index_unique(target_values, "target_id")
            base_path = dataset / "environment/LATEST_BASELINES.json"
            base_values, digest = read(base_path)
            bindings[str(base_path.relative_to(REPO))] = digest
            bases = index_unique(base_values, "opportunity_id")
            reference = next(iter(rows.values()))
            baseline_rows = []
            for r in reference:
                target = targets[r["target_id"]]
                if target["threshold"] != threshold:
                    raise ValueError("Wrong declared threshold cohort")
                mapped = backoff(bank, target, bases.get(r["opportunity_id"]))
                if mapped["probability"] != r["base"]:
                    raise ValueError("Calendar base reconstruction mismatch")
                baseline_rows.append({"opportunity_id": r["opportunity_id"], "target_id": r["target_id"],
                                      "station": r["station"], "outcome": r["outcome"], "mapping": mapped})
            dump(args.output / (cohort + "_BASELINE_ROWS.json"), baseline_rows)
            station_counts = {}
            for station in sorted({r["station"] for r in baseline_rows}):
                subset = [r for r in baseline_rows if r["station"] == station]
                settled = [r for r in subset if r["outcome"] is not None]
                unique_targets = {r["target_id"]: r["outcome"] for r in settled}
                station_counts[station] = {"opportunities": len(subset), "settled": len(settled),
                                          "event_rate_on_settled_opportunities": sum(r["outcome"] for r in settled) / len(settled),
                                          "mean_base_on_settled": math.fsum(r["mapping"]["probability"] for r in settled) / len(settled),
                                          "unique_settled_targets": len(unique_targets), "unique_positive_targets": sum(unique_targets.values())}
            backoff_report[cohort] = {"bank": str(bank_path.relative_to(REPO)), "mapping_version": bank["mapping_version"],
                                     "threshold_m": threshold, "fit_geography": "Bay Area, prior December",
                                     "transfer_to_other_geography": cohort.startswith("front"),
                                     "baseline": summarize_backoff(baseline_rows, "mapping"),
                                     "actual_predictor_call_evidence_mappings": {k: summarize_backoff(v, "actual_disclosed_mapping") for k, v in arm_backoff.items()},
                                     "station_event_rates": station_counts,
                                     "fit_cell_inventory": {"all_cells": len(bank["cells"]), "below_minimum_n": sum(c["n"] < bank["minimum_cell_n"] for c in bank["cells"].values()),
                                                            "minimum_cell_n": bank["minimum_cell_n"]}}
    now = datetime.now(timezone.utc).isoformat()
    scope = {"created_at": now, "new_model_calls": 0, "new_downloads": 0,
             "scope": "Previously verified three full calendars, Qwen3-8B model arms plus saved program scores",
             "no_new_causal_or_calibration_guarantee": True}
    dump(args.output / "REVISION_FUNNEL.json", {**scope, "schema": "disastertrace.recorded_revision_audit.v1", "cohorts": reports, "total_model_arm_counts": dict(all_counts),
        "denominators": {"registered_opportunities": "Sum over arms/sessions, not independent weather cases", "predictor_calls": "Actual saved predictor outputs, excludes selector calls", "recorded_candidates": "One engine candidate event per actual predictor call, including follow/no_change and invalid responses", "accepted_candidates": "Accepted engine override events; not necessarily nonbaseline or present at a cutoff", "snapshots": "One per declared opportunity; overrides may persist from calls addressing another lead"},
        "static_candidate_gain_scope": "Evaluator-only comparison of each actually returned probability with the base at its call start, regardless of decision. It ignores subsequent time/versions and is not an end-to-end policy score.",
        "selector_selection_limitation": "Trace records successful calls and selector outputs but not every hypothetical skipped candidate. Uncalled probabilities and reasons for every unselected opportunity remain unavailable."})
    dump(args.output / "BASELINE_BACKOFF_AUDIT.json", {**scope, "cohorts": backoff_report,
        "interpretation": "Cell counts are unique targets within a cell, not independent storms. Overlapping cells cannot be summed as independent observations. Actual evidence mappings are diagnostic deterministic outputs, not substituted LLM predictions. No refitting or local mapping has been performed."})
    dump(args.output / "SCORE_CROSSCHECK.json", {**scope, "cohorts": score_report, "absolute_tolerance": 1e-12,
        "implementation": "Independent binary formula with math.fsum; production brier_report not imported or called", "all_common_mask_checks_pass": True})
    for path in [Path(__file__), REPO / "disastertrace-starter/src/disastertrace/monitoring_v1/calibration.py", REPO / "disastertrace-starter/src/disastertrace/monitoring_v1/policies.py"]:
        bindings[str(path.relative_to(REPO))] = hashlib.sha256(path.read_bytes()).hexdigest()
    dump(args.output / "INPUT_BINDINGS.json", {"created_at": now, "sha256_by_repo_relative_path": bindings, "count": len(bindings)})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
