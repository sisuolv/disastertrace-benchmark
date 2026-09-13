"""Compare portfolio E coverage with verified source-only joint path references."""

from __future__ import annotations

import argparse
import json
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from analyze_calendar import digest, load, write

BASE = Path(__file__).resolve().parent
REPO = BASE.parents[1]
E_STATES = ("supported", "refuted", "undetermined", "inconsistent")


def main(args):
    args.output.mkdir(exist_ok=False)
    shutil.copyfile(__file__, args.output / "analyze_joint_E.py")
    report_path = args.analysis / "REPORT.json"
    verification_path = args.joint_verification
    report, checked = load(report_path), load(verification_path)
    if checked["source_audit_sha256"] != report["source_audit_sha256"]:
        raise ValueError("Joint reference and model calendar use different data")
    bindings = {str(report_path.resolve()): digest(report_path), str(verification_path.resolve()): digest(verification_path)}
    by_budget = defaultdict(list)
    bound_paths = {Path(path).name + ":" + Path(path).parent.name: checksum
                   for path, checksum in report["input_bindings"].items() if Path(path).name.startswith("JOINT-budget")}
    for record in checked["references"]:
        path = REPO / record["path"]
        sha = digest(path)
        if sha != record["sha256"] or bound_paths.get(path.name + ":" + path.parent.name) != sha:
            raise ValueError("Reference differs from either independent witness or calendar binding")
        value = load(path)
        if not value["exact"] or not record["whole_session_path_valid"] or not record["exact_reference_unchanged"]:
            raise ValueError("Reference has no verified exact joint-path guarantee")
        if value["joint_E_utility"] != record["joint_E_utility"]:
            raise ValueError("Joint utility changed after witness verification")
        bindings[str(path.resolve())] = sha
        individual = sum(status == "reachable_relaxation"
                         for hour in value["hourly_references"]
                         for status in hour["reference"]["individual_status"].values())
        by_budget[value["limits"]["requests"]].append({
            "session": path.parent.name, "opportunities": value["full_opportunities"],
            "joint_E_utility": value["joint_E_utility"], "individually_reachable_relaxation": individual,
            "scope": value["scope"], "limits": value["limits"], "concurrency": value["concurrency"]})
    references = {}
    for budget, values in by_budget.items():
        if len({v["session"] for v in values}) != len(values):
            raise ValueError("Duplicate source-budget reference for a resource session")
        references[str(budget)] = {"sessions": len(values),
            "opportunities": sum(v["opportunities"] for v in values),
            "joint_E_utility": sum(v["joint_E_utility"] for v in values),
            "individually_reachable_relaxation": sum(v["individually_reachable_relaxation"] for v in values),
            "per_session": values}
    arms = {}
    for name, arm in report["arms"].items():
        settings, costs = arm["settings"], arm["costs_and_process"]
        if settings["allocation"] != "global_budget" or settings["authorization"] != "session_shared":
            raise ValueError("This reference only applies to the B11 disclosure regime")
        reference = references[str(settings["source_budget_per_session"])]
        statuses = {state: costs.get("E_" + state, 0) for state in E_STATES}
        n = sum(statuses.values())
        resolved = statuses["supported"] + statuses["refuted"]
        if n != arm["scores"]["opportunities"] or n != reference["opportunities"] or costs["resource_sessions"] != reference["sessions"]:
            raise ValueError("Joint-reference and full-portfolio E denominators differ")
        if resolved > reference["joint_E_utility"]:
            raise ValueError("Observed certified coverage exceeds the saved source-only optimum")
        arms[name] = {"opportunities": n, "source_budget_per_session": settings["source_budget_per_session"],
                      "actual_source_requests": costs["resource_requests"], "actual_model_calls": costs["actual_model_calls"],
                      "E_states": statuses, "certified_E_opportunities": resolved,
                      "source_only_joint_E_reference": reference["joint_E_utility"],
                      "source_only_coverage_headroom": reference["joint_E_utility"] - resolved,
                      "fraction_of_source_only_reference": resolved / reference["joint_E_utility"] if reference["joint_E_utility"] else None,
                      "F_settled_opportunities": arm["scores"]["settled"],
                      "F_gain_over_shared_R_base": arm["scores"]["net_realized_gain"]}
    result = {"created_at": datetime.now(timezone.utc).isoformat(), "references_by_source_budget": references,
              "arms": arms, "input_bindings": bindings,
              "implementation_sha256": digest(args.output / "analyze_joint_E.py"), "new_model_calls": 0,
              "interpretation": [
                  "Joint references use one feasible source-query path per resource session; individual reachability is not summed as a feasible joint allocation.",
                  "All registered opportunities count for E, including targets with unresolved future F outcomes.",
                  "The reference optimizes only source-query E coverage with registered costs/pacing; it does not optimize F, model tokens or model call allocation.",
                  "Positive source-only headroom is a portfolio diagnostic, not a per-target acquisition-failure penalty or proof that the F policy should acquire more.",
                  "A legal-product certified E state is separate from whether the model reports that state correctly.",
                  "Higher E coverage can coincide with worse F loss. Repeated leads and adjacent reports are not independent process evidence.",
              ]}
    write(args.output / "REPORT.json", result)
    lines = ["# Portfolio E coverage and a jointly feasible source-only reference", "",
             "This compares full registered portfolios with verified legal query paths, not a sum of incompatible per-target optima.",
             "The reference omits forecasting computation and F utility; its gap is diagnostic headroom, not a failure penalty.", "",
             "| Source requests / session | Individual reachability sum | Joint feasible E optimum | All opportunities |",
             "| --- | ---: | ---: | ---: |"]
    for budget, value in sorted(references.items(), key=lambda pair: int(pair[0])):
        lines.append(f"| {budget} | {value['individually_reachable_relaxation']} | {value['joint_E_utility']} | {value['opportunities']} |")
    lines += ["", "| Method | Certified E | Source-only joint reference | Portfolio headroom | F gain over R base |",
              "| --- | ---: | ---: | ---: | ---: |"]
    for name, value in arms.items():
        lines.append(f"| {name} | {value['certified_E_opportunities']} | {value['source_only_joint_E_reference']} | "
                     f"{value['source_only_coverage_headroom']} | {value['F_gain_over_shared_R_base']:+.9f} |")
    lines += ["", "Certified E describes the legally disclosed product facts, not the model's correctness at reading them.",
              "E and F denominators differ when future outcomes are missing; all counts and state categories remain in REPORT.json.",
              "Nothing in this comparison requires a rational F policy to maximize E coverage, or imputes F=0.5 when E is undetermined.", ""]
    (args.output / "REPORT.md").write_text("\n".join(lines))
    print(json.dumps({"arms": len(arms), "source_budgets": list(references), "new_model_calls": 0}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--joint-verification", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
