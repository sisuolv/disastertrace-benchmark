"""Describe separately audited v1/v2 model runs without treating time as controlled."""

import argparse
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

import runner

METHODS = ("snapshot", "structured_state", "answer_history")
SEMANTIC_FILES = (
    "episodes.jsonl",
    "micro_fixtures.jsonl",
    "schedule.jsonl",
    "private/gold.jsonl",
    "public/initial_requests.jsonl",
    "parent_sources.jsonl",
)


def denominators(value, prefix=""):
    result = {}
    if isinstance(value, dict):
        if {"numerator", "denominator", "value"} <= value.keys():
            result[prefix] = value["denominator"]
        else:
            for key, child in value.items():
                result.update(denominators(child, prefix + "/" + key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            result.update(denominators(child, prefix + "/" + str(index)))
    return result


def compare_reports(before, after):
    from disastertrace.controlled.scorer import METRICS

    if before["mode"] != "model_http" or after["mode"] != "model_http":
        raise ValueError("both reports must contain actual model captures")
    if set(before["methods"]) != set(METHODS) or set(after["methods"]) != set(METHODS):
        raise ValueError("three-method matrix changed")
    counts = denominators(before["methods"])
    if not counts or counts != denominators(after["methods"]):
        raise ValueError("metric opportunity denominators changed")
    denominator_keys = sorted({key for _, key in METRICS.values()})
    methods = {}
    checkpoint_count = 0
    for method in METHODS:
        left, right = before["methods"][method], after["methods"][method]
        identity_keys = ("episode_id", "root_id", "group_id", "family", "branch", "checkpoint_id")
        rows = []
        for score in (left, right):
            indexed = {
                tuple(row[key] for key in identity_keys): row for row in score["per_checkpoint"]
            }
            if len(indexed) != 90 or len(score["per_checkpoint"]) != 90:
                raise ValueError("expected 90 distinct planned checkpoints per method")
            rows.append(indexed)
        if rows[0].keys() != rows[1].keys():
            raise ValueError("checkpoint identities changed")
        outcomes = Counter()
        for key, old in rows[0].items():
            new = rows[1][key]
            if set(old["slots"]) != set(new["slots"]) or any(
                old["counts"][name] != new["counts"][name] for name in denominator_keys
            ):
                raise ValueError("checkpoint opportunities changed")
            a, b = old["counts"]["all_correct"], new["counts"]["all_correct"]
            outcomes[
                "v2_only_correct"
                if b > a
                else "v1_only_correct"
                if a > b
                else "both_correct"
                if a
                else "both_incorrect"
            ] += 1
            checkpoint_count += 1
        methods[method] = {
            "metrics": {
                name: {
                    "v1": old,
                    "v2": right["metrics"][name],
                    "numerator_change_v2_minus_v1": right["metrics"][name]["numerator"]
                    - old["numerator"],
                }
                for name, old in left["metrics"].items()
            },
            "matched_checkpoint_outcomes": {
                key: outcomes[key]
                for key in (
                    "v2_only_correct",
                    "v1_only_correct",
                    "both_correct",
                    "both_incorrect",
                )
            },
        }
    return {
        "schema_version": "p2_historical_contract_comparison_v1",
        "v1_execution_id": before["execution_id"],
        "v2_execution_id": after["execution_id"],
        "v1_audit_id": before["audit_id"],
        "v2_audit_id": after["audit_id"],
        "v1_complete": before["complete"],
        "v2_complete": after["complete"],
        "v1_reliability": before["reliability"],
        "v2_reliability": after["reliability"],
        "metric_denominators_checked": len(counts),
        "checkpoint_opportunities_checked": checkpoint_count,
        "methods": methods,
        "operations": {
            label: {key: value for key, value in report["operations"].items() if key != "attempts"}
            for label, report in (("v1", before), ("v2", after))
        },
        "additional_model_calls": 0,
        "causal_effect_estimated": False,
        "statistical_significance_tested": False,
        "interpretation": (
            "Descriptive development comparison: collection times differ and each condition "
            "has one sampled trajectory. Branches and checkpoints are dependent; source "
            "and primary/secondary case are confounded. Actual carriers may differ after "
            "different preceding answers. No response repair or selective exclusion."
        ),
    }


def verify_bundle(bundle):
    env = os.environ.copy()
    for key in list(env):
        if any(part in key.upper() for part in ("TOKEN", "SECRET", "API_KEY", "PASSWORD")):
            env.pop(key)
    project = runner.HERE.parents[1]
    env.update(
        DISASTERTRACE_OFFLINE="1",
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONPATH=os.pathsep.join([str(project / "scripts/offline_guard"), str(bundle)]),
    )
    script = (
        "import json; from pathlib import Path; import runner; "
        "manifest, plan = runner.verify(); "
        "_, _, reporter, _ = runner.frozen_modules(); "
        "print(json.dumps(reporter.verify_report(runner.HERE / 'execution', "
        "Path(manifest['run_output']), runner.HERE / 'runtime/report')))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=bundle,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old-bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    old, new = args.old_bundle.resolve(), runner.HERE
    verifications = {"v1": verify_bundle(old), "v2": verify_bundle(new)}
    runner.verify()
    old_plan = runner.read(old / "execution/execution.json")
    new_plan = runner.read(new / "execution/execution.json")
    if old_plan["schema_version"] != "controlled_execution_v1":
        raise ValueError("historical baseline must be v1")
    if new_plan["output_contract"] != runner.OUTPUT_CONTRACT:
        raise ValueError("candidate contract changed")
    semantic_files = {}
    for name in SEMANTIC_FILES:
        a = runner.sha(old / "execution/dataset" / name)
        b = runner.sha(new / "execution/dataset" / name)
        if a != b:
            raise ValueError("semantic task file changed: " + name)
        semantic_files[name] = a
    result = compare_reports(
        runner.read(old / "runtime/report/report.json"),
        runner.read(new / "runtime/report/report.json"),
    )
    result.update(
        independent_report_verifications=verifications,
        identical_semantic_files=semantic_files,
        analysis_script_sha256=runner.sha(Path(__file__)),
    )
    if args.verify:
        if runner.read(args.output) != result:
            raise ValueError("historical comparison differs from report reconstruction")
    else:
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "status": "verified" if args.verify else "generated",
                "metric_denominators_checked": result["metric_denominators_checked"],
                "checkpoint_opportunities_checked": result["checkpoint_opportunities_checked"],
                "causal_effect_estimated": False,
                "additional_model_calls": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
