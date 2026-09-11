"""Write immutable phase notes from already verified P12-P14 analyses."""

import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1] / "disastertrace-starter"
AUTONOMY = PROJECT / "artifacts/autonomy_10h_v1"
sys.path.insert(0, str(AUTONOMY))

from disastertrace.forecast_task.common import digest, read
from seal_cohort_evidence_v3 import PHASES, locate, successful_command, validate_result

METHODS = ("snapshot", "structured_state", "answer_history")
CONDITIONS = {
    "p12": "The system contract is retained; XGrammar uses default JSON separator spacing.",
    "p13": "DeepSeek receives the same contract text in the user message, under default JSON separator spacing.",
    "p14": "Qwen receives the same contract text in the user message, under default JSON separator spacing.",
}


def generate(phase):
    bundle = PROJECT / "artifacts" / PHASES[phase][0]
    if (bundle / "COMPLETED_ACCEPTANCE.json").exists():
        raise FileExistsError("accepted findings cannot be regenerated")
    profiles = read(bundle / "PREREGISTRATION.json")["model_profiles"]
    cases = {}
    for profile in profiles:
        final, reviews, location = locate(phase, profile, bundle)
        for action in ("analyze", "verify"):
            successful_command(reviews, phase + "_" + profile + "_" + action)
        analysis = read(reviews / (phase + "_" + profile + ".json"))
        validate_result(read(final / "FINAL_STATUS.json"), read(final / "global_report.json"), analysis, 2412)
        if any(location[key] != analysis[key] for key in ("analysis_id", "report_id", "execution_id")):
            raise ValueError("phase note analysis differs from its verified location")
        cases[profile] = (analysis, location)
    lines = [f"# {phase.upper()}: verified model-condition results", "", CONDITIONS[phase], "",
             "These are separately generated, pre-registered development runs: six storms,",
             "36 original NHC products, 144 targets, 804 future checkpoints per method,",
             "three methods and one repeat. All methods receive the same cumulative",
             "visible source documents. Only their additional own-answer carriers differ.", "",
             "## Fixed-denominator results", "",
             "| Model | Returned / planned | Shape valid | Strict correct / planned | Strict % | Unattempted | Unknown |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for profile, (a, _) in cases.items():
        s, c = a["score_counts"], a["counts"]
        lines.append(f"| {a['settings']['model_id']} | {s['received']}/{s['planned']} | {s['shape_valid']} | "
                     f"{s['all_correct']}/{s['planned']} | {100*s['all_correct']/s['planned']:.4f} | "
                     f"{c['unattempted']} | {c['unknown_outcomes']} |")
    lines += ["", "Unreturned slots remain in the primary denominator. An audit pass means the",
              "recorded run reconstructs; collection completeness and GPU success are separate.", ""]
    for profile, (a, location) in cases.items():
        lines += [f"## {a['settings']['model_id']}", "",
                  "| Method | Returned / 804 | Strict correct / 804 | Whole targets correct / 144 | Fully captured targets / 144 |",
                  "| --- | ---: | ---: | ---: | ---: |"]
        for method in METHODS:
            row, targets = a["methods"][method], a["targets"][method]
            lines.append(f"| {method} | {row['received']} | {row['all_correct']} | "
                         f"{targets['whole_target_single_repeat']} | {targets['fully_captured_targets']} |")
        for group in ("status", "storm", "transition"):
            lines += ["", f"### Reference {group} groups", "",
                      "Cells show strict correct / planned; checkpoints within a storm are dependent.", "",
                      "| Group | snapshot | structured_state | answer_history |", "| --- | ---: | ---: | ---: |"]
            for name, methods in sorted(a["cross_tables"][group].items()):
                cells = [f"{methods[m]['all_correct']}/{methods[m]['planned']}" for m in METHODS]
                lines.append("| " + " | ".join([name, *cells]) + " |")
        numeric = a["cross_tables"]["status"]["numeric"]
        num = sum(numeric[m]["all_correct"] for m in METHODS)
        den = sum(numeric[m]["planned"] for m in METHODS)
        lines += ["", f"Numeric-only strict correctness is {num}/{den} ({100*num/den:.4f}%).",
                  "Headline correctness also includes not_stated and DISSIPATED cases.", "",
                  "### Errors, output and resources", "",
                  "Disjoint primary errors use precedence; component errors can overlap.", "",
                  "```json", json.dumps(a["score_counts"]["errors"], sort_keys=True, indent=2), "```", "",
                  "Observed unit strings among shape-valid outputs:", "", "```json",
                  json.dumps(a["observed_unit_strings"], sort_keys=True, indent=2), "```", "",
                  f"Finish reasons: `{json.dumps(a['finish_reasons'], sort_keys=True)}`.",
                  f"Shape by finish reason: `{json.dumps(a['shape_by_finish'], sort_keys=True)}`.",
                  f"Reasoning-extraction errors: {a['counts']['extraction_errors']}.",
                  f"Output tokens: {a['counts']['output_tokens']}; generation-job H100 allocation hours: {a['generation_h100_hours']:.7f}.",
                  f"Final-text whitespace characters: {a['whitespace_characters']['sum']}; maximum per answer: {a['whitespace_characters']['max']}.", "",
                  "Whitespace includes strings. Allocation hours include model loading and worker",
                  "lifetime, exclude separate preflights, and are neither device utilization nor cost.", "",
                  "| Worker | Job | ACP terminal state | Returned / planned | Stop reason | Error |",
                  "| --- | --- | --- | ---: | --- | --- |"]
        for worker in a["workers"]:
            end = worker.get("completion") or {}
            error = str(end.get("error") or "none").replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {worker['worker_id']} | {worker['job']['job_id']} | {worker['job']['state']} | "
                         f"{worker['returned']}/{worker['planned']} | {end.get('stop_reason', 'unavailable')} | {error} |")
        lines += ["", "All listed allocations are terminal and released. A context-guard failure",
                  "retains the original whole-worker stopping behavior; this phase does not",
                  "isolate the oversized trajectory or retry its unrelated remaining slots.", "",
                  f"Report ID: `{a['report_id']}`.", f"Analysis ID: `{a['analysis_id']}`.",
                  f"Verified finalization: `{location['finalization']}`.",
                  f"Analysis location record: `artifacts/autonomy_10h_v1/reviews_continuation_v2/LOCATION_{phase}_{profile}.json`.", ""]
    lines += ["## Verification and interpretation limits", "",
              "Report construction/verification, token-mask replay, relocated CPU review and",
              "descriptive-analysis reconstruction all have successful command receipts.",
              "Preserved initial CPU-observer failures and any fresh CPU continuation are",
              "identified by the LOCATION record; no GPU answer is replaced by that recovery.", "",
              "Default JSON separator spacing does not constrain correct values, units, source",
              "versions or line locators. It must not be described as compact JSON with no spaces.",
              "P11/P12/P13/P14 have their own generated histories. Their three role/spacing",
              "cells are not a full factorial. Later dispatches have less time before the shared",
              "02:05:16 UTC deadline; any resulting censoring is not a pure prompt-role effect.", "",
              "The public deterministic resolver solves the task without private Gold. This",
              "measures understanding and citation of published forecasts, not numerical weather",
              "prediction. Six early-advisory development storms, English inputs, one repeat,",
              "no terminal-revision checkpoints, uncertain historical availability and shared",
              "Qwen ancestry limit population and model-family conclusions.", "",
              "No unit normalization, answer repair, model retries, paid API, training, heldout",
              "inference or per-item human/LLM judging is introduced.", ""]
    findings = "\n".join(lines)
    intro = [f"# {phase.upper()} completed model-condition audits", "", CONDITIONS[phase], ""]
    for _, (a, _) in cases.items():
        s = a["score_counts"]
        intro.append(f"{a['settings']['model_id']}: {s['all_correct']}/{s['planned']} strictly correct "
                     f"({100*s['all_correct']/s['planned']:.4f}%), with {s['received']}/{s['planned']} returned.")
    intro += ["", "All allocations are released. The fixed denominator includes missing returns;",
              "audit completion does not imply a fully collected matrix or successful GPU jobs.", "",
              f"See [phase findings](artifacts/{bundle.name}/FINDINGS.md) for all method, storm,",
              "reference-status, error, unit, output and resource breakdowns. Exact report and",
              "analysis paths are bound by the LOCATION records under",
              "`artifacts/autonomy_10h_v1/reviews_continuation_v2/`.", "",
              "Every method sees the same cumulative source documents. Own-answer carriers",
              "differ; no hidden-evidence memory or numerical weather-forecasting claim follows.",
              "Interpret prompt conditions with their separate histories and remaining time.", "",
              "Verify the completed inventory without restarting any model launch:", "", "```bash",
              "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python \\",
              f"  artifacts/autonomy_10h_v1/seal_cohort_evidence_v3.py --phase {phase} --verify", "```", "",
              "Use a compatible CPU Python in a restored review workspace. No retries, heldout",
              "inference, paid API, training, unit normalization or human/LLM judge occurs.", ""]
    return bundle / "FINDINGS.md", findings, PROJECT / ("README_" + phase.upper() + "_COMPLETED_V1.md"), "\n".join(intro)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=CONDITIONS, required=True)
    args = parser.parse_args()
    findings_path, findings, readme_path, readme = generate(args.phase)
    if findings_path.exists() or readme_path.exists():
        raise FileExistsError("phase findings already exist")
    for path, text in ((findings_path, findings), (readme_path, readme)):
        with path.open("x") as stream:
            stream.write(text)
    print({"phase": args.phase, "findings_sha256": digest(findings_path),
           "readme_sha256": digest(readme_path), "source_sha256": digest(__file__)}, flush=True)
