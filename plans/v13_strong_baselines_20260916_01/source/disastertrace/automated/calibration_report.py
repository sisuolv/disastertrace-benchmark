"""Audit-bound full-denominator scores; compatibility projections are not exposure."""

import argparse
from copy import deepcopy
from pathlib import Path

from .calibration import METHODS, cells, screen_budget
from .common import canonical, fingerprint, write_json, write_jsonl
from .dynamic import render_request, score_dynamic
from .execution_observations import summarize_observations
from .live_calibration import verify_execution
from .live_calibration_audit import audit_run
from .scoring_v2 import score_dynamic_v2


def _arm_comparisons(cell_reports):
    comparisons = []
    for earlier, later in (("legacy_4096", "explicit_4096"), ("explicit_4096", "explicit_8192")):
        for method in METHODS:
            before = cell_reports[earlier + "__" + method]
            after = cell_reports[later + "__" + method]
            before_events = {e["group_id"]: e for e in before["per_event"]}
            paired = []
            for event in after["per_event"]:
                prior = before_events[event["group_id"]]
                paired.append(
                    {
                        "group_id": event["group_id"],
                        "before": prior["metrics"],
                        "after": event["metrics"],
                        "after_minus_before": {
                            key: (
                                value["value"] - prior["metrics"][key]["value"]
                                if value["value"] is not None
                                and prior["metrics"][key]["value"] is not None
                                else None
                            )
                            for key, value in event["metrics"].items()
                        },
                    }
                )
            comparisons.append(
                {
                    "earlier_arm": earlier,
                    "later_arm": later,
                    "method": method,
                    "per_event": paired,
                    "complete_comparison": before["finalized"] == after["finalized"] == 30,
                    "interpretation": (
                        "descriptive paired storm differences "
                        "including changed carrier trajectories"
                    ),
                }
            )
    return comparisons


def report_run(execution: Path, run: Path, output: Path) -> dict:
    plan = verify_execution(execution)
    audit = audit_run(execution, run)
    actual = {row["slot_index"]: row for row in audit["records"]}
    pending = audit["pending"]
    cell_reports, counts = {}, []
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    for cell in cells():
        projections, actual_views, previous, histories = [], [], {}, {}
        schema_valid = length = received = attempted = finalized = 0
        dispositions = []
        for index, slot in enumerate(plan["schedule"]):
            if slot["cell_id"] != cell["cell_id"]:
                continue
            ep = next(ep for ep in plan["episodes"] if ep["episode_id"] == slot["episode_id"])
            trajectory = slot["trajectory_id"]
            before = previous.get(trajectory)
            history = histories.get(trajectory, [])
            legacy = render_request(
                ep, slot["checkpoint_id"], before, method=slot["method"], history=history
            )
            record = actual.get(index)
            unresolved = pending if pending is not None and pending["slot_index"] == index else None
            saved = record or unresolved
            sent = record is not None or (
                unresolved is not None and unresolved["phase"] != "reserved"
            )
            capture = saved.get("capture") if saved is not None else None
            attempted += int(sent)
            received += int(
                capture is not None
                and capture["capture_kind"] == "complete"
                and capture["http_status"] == 200
            )
            disposition = (
                "finalized_" + record["status"]
                if record
                else ("pending_" + unresolved["phase"] if unresolved else "not_sent")
            )
            dispositions.append(
                {
                    "slot_index": index,
                    "disposition": disposition,
                    "attempted": sent,
                    "capture_kind": capture["capture_kind"] if capture else None,
                    "capture_error": capture["error_code"] if capture else None,
                    "usage_settled": bool(
                        record or (unresolved and unresolved["phase"] == "settled")
                    ),
                }
            )
            if saved is not None:
                actual_views.append(
                    {
                        "slot_index": index,
                        "disposition": disposition,
                        "prepared_public_request": saved["request"],
                        "send_intent_observed": sent,
                        "capture": capture,
                        "raw_response": record["raw_response"] if record else None,
                        "capture_sha256": fingerprint(capture) if capture else None,
                    }
                )
            if record:
                view = record["request"]
                if {k: v for k, v in view.items() if k != "instruction"} != {
                    k: v for k, v in legacy.items() if k != "instruction"
                }:
                    raise ValueError("projection changes more than instruction")
                finalized += 1
                schema_valid += record["status"] == "ok"
                length += record["completion"]["metadata"]["finish_reason"] == "length"
                raw, status, after = record["raw_response"], record["status"], record["state_after"]
                if status == "ok":
                    previous[trajectory] = deepcopy(after)
                    histories.setdefault(trajectory, []).append(deepcopy(after))
            else:
                raw, status, after = "", "missing" if sent else "budget_exhausted", before
            projections.append(
                {
                    "episode_id": ep["episode_id"],
                    "checkpoint_id": slot["checkpoint_id"],
                    "backend": "audited_capture_projection",
                    "method": slot["method"],
                    "model_kind": audit["mode"],
                    "eligible_for_llm_leaderboard": False,
                    "request": legacy,
                    "request_hash": fingerprint(legacy),
                    "raw_response": raw,
                    "status": status,
                    "error": None,
                    "state_after": deepcopy(after),
                    "logical_queries": int(sent),
                    "provider_requests": 0,
                }
            )
        metrics = score_dynamic_v2(plan["episodes"], projections)
        directory = output / cell["cell_id"]
        directory.mkdir()
        write_jsonl(directory / "actual_views.jsonl", actual_views)
        write_jsonl(directory / "dispositions.jsonl", dispositions)
        write_jsonl(directory / "scoring_projection.jsonl", projections)
        write_json(directory / "score_v2.json", metrics)
        write_json(directory / "score_v1.json", score_dynamic(plan["episodes"], projections))
        cell_reports[cell["cell_id"]] = {
            "metrics": metrics["metrics"],
            "per_event": metrics["per_event"],
            "event_macro": metrics["event_macro"],
            "paired_delay_minus_base": metrics["paired_delay_minus_base"],
            "operations": summarize_observations(
                plan,
                audit,
                [i for i, s in enumerate(plan["schedule"]) if s["cell_id"] == cell["cell_id"]],
            ),
            "actual_views_sha256": fingerprint(actual_views),
            "projection_sha256": fingerprint(projections),
            "materialization_model_calls": 0,
            "unsubmitted": 30 - attempted,
            "attempted": attempted,
            "received": received,
            "finalized": finalized,
        }
        counts.append(
            {
                "cell_id": cell["cell_id"],
                "received": received,
                "schema_valid": schema_valid,
                "length_failures": length,
            }
        )
    screening = screen_budget(counts)
    live = audit["mode"] == "urllib_http" and audit["complete"] and audit["stop_reason"] is None
    result = {
        "schema_version": "calibration_report_v1_1",
        "execution_id": plan["execution_id"],
        "audit_id": audit["audit_id"],
        "complete": audit["complete"],
        "mode": audit["mode"],
        "cells": cell_reports,
        "arm_comparisons": _arm_comparisons(cell_reports),
        "operations": summarize_observations(plan, audit),
        "cell_counts": counts,
        "budget": audit["budget"],
        "stop_reason": audit["stop_reason"],
        "received": audit["received"],
        "attempted": audit["attempts"],
        "unsubmitted": 270 - audit["attempts"],
        "selected_output_tokens": screening["selected_output_tokens"] if live else None,
        "live_recommendation": live and screening["selected_output_tokens"] is not None,
        "diagnostic_budget_screen": screening,
        "provider_origin_authenticated": False,
        "projection_policy": (
            "instruction-only compatibility; unresolved attempted rows are missing "
            "and unsent rows are unsubmitted"
        ),
        "model_api_calls": audit["model_api_calls"],
    }
    write_json(output / "report.json", result)
    table = [
        "| Cell | Attempted / 30 | Received | Schema valid | Length | Known grounded |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in counts:
        cell = cell_reports[row["cell_id"]]
        metric = cell["metrics"]["known_grounded_accuracy"]
        table.append(
            f"| {row['cell_id']} | {cell['attempted']} | {cell['received']} | "
            f"{row['schema_valid']} | {row['length_failures']} | "
            f"{metric['numerator']}/{metric['denominator']} |"
        )
    (output / "REPORT.md").write_text(
        "# Calibration execution report\n\n"
        f"Mode: `{audit['mode']}`. Completed {audit['completed']}/270.\n\n"
        "Program transports are diagnostics, never LLM results. Projection construction makes zero "
        "provider calls; actual calls are counted in the separately audited journal. Missing "
        "opportunities remain in fixed denominators and are not claims of model knowledge "
        "errors.\n\n"
        f"Live budget recommendation: `{result['selected_output_tokens']}`.\n\n"
        + "\n".join(table)
        + "\n\n"
        "report.json includes per-storm numerators/denominators, equal-weight event macros, "
        "paired arm differences, overlapping failure counts, captured usage and transport latency. "
        "UTC intent/capture times bracket collection; they are not authenticated provider billing "
        "timestamps. Snapshot-rate/cache-aware estimates require complete, consistent cache counts "
        "and a single pricing window. Missing or crossed windows retain unknown cost; conservative "
        "reservations remain separate. Diagnostic estimates are simulations, "
        "never incurred spend.\n",
        encoding="utf-8",
    )
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execution", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = report_run(args.execution, args.run, args.output)
    print(canonical({k: v for k, v in result.items() if k != "cells"}))


if __name__ == "__main__":
    main()
