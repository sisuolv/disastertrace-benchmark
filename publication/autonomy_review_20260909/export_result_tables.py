"""Export verified cohort analyses without rescoring or changing denominators."""

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1] / "disastertrace-starter"
CASES = (
    ("p11", "qwen3", "cohort_reviews_01", "system_any_spacing"),
    ("p11", "deepseek_r1", "cohort_reviews_01", "system_any_spacing"),
    ("p12", "qwen3", "cohort_reviews_01", "system_default_spacing"),
    ("p12", "deepseek_r1", "cohort_reviews_01", "system_default_spacing"),
    ("p13", "deepseek_r1", "role_reviews_01", "user_default_spacing"),
    ("p14", "qwen3", "role_reviews_01", "user_default_spacing"),
)
METHODS = ("snapshot", "structured_state", "answer_history")


def encoded(value):
    return json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True,
                      separators=(",", ":")).encode()


def sha(content):
    return hashlib.sha256(content).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def identity(value, key):
    if value[key] != sha(encoded({k: v for k, v in value.items() if k != key})):
        raise ValueError("input identity differs: " + key)


def successful(folder, label):
    receipt = read(folder / (label + "_result.json"))
    if receipt["exit_code"] != 0 or receipt["log_sha256"] != sha((folder / (label + ".log")).read_bytes()):
        raise ValueError("analysis command did not verify: " + label)


def flatten(row):
    result = {}
    for key, value in row.items():
        if isinstance(value, dict):
            for nested, item in flatten(value).items():
                result[key + "." + nested] = item
        else:
            result[key] = value
    return result


def csv_bytes(rows):
    names = list(dict.fromkeys(key for row in rows for key in row))
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=names, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def build(project):
    autonomy = project / "artifacts/autonomy_10h_v1"
    inputs, summaries, overall, grouped = {}, {}, [], []
    for phase, profile, directory, condition in CASES:
        key = phase + "_" + profile
        folder = autonomy / directory
        location_path = autonomy / "reviews_continuation_v2" / ("LOCATION_" + key + ".json")
        location = read(location_path) if location_path.exists() else None
        if location is not None:
            if location["phase"] != phase or location["model_profile"] != profile:
                raise ValueError("CPU review location belongs to a different case")
            folder = (project / location["review_directory"]).resolve()
            if folder not in {(autonomy / directory).resolve(), (autonomy / "reviews_continuation_v2").resolve()}:
                raise ValueError("CPU review location is outside the declared directories")
            inputs[location_path.relative_to(project).as_posix()] = sha(location_path.read_bytes())
        path = folder / (key + ".json")
        analysis = read(path)
        identity(analysis, "analysis_id")
        if location is not None:
            if (sha(path.read_bytes()) != location["analysis_sha256"]
                    or any(location[k] != analysis[k] for k in ("analysis_id", "report_id", "execution_id"))):
                raise ValueError("CPU review location no longer matches its analysis")
        for action in ("analyze", "verify"):
            successful(folder, key + "_" + action)
            for suffix in ("_intent.json", "_result.json", ".log"):
                item = folder / (key + "_" + action + suffix)
                inputs[item.relative_to(project).as_posix()] = sha(item.read_bytes())
        inputs[path.relative_to(project).as_posix()] = sha(path.read_bytes())
        counts, scores = analysis["counts"], analysis["score_counts"]
        if (analysis["model_profile"] != profile or scores["planned"] != 2412
                or counts["planned"] != 2412 or scores["received"] != counts["raw_returned"]
                or analysis["single_repeat_only"] is not True
                or analysis["planned_denominator_is_primary"] is not True
                or analysis["unit_normalization"] is not False):
            raise ValueError("registered model, coverage or interpretation differs: " + key)
        if len(analysis["workers"]) != 2 or any(w["job"]["released"] is not True for w in analysis["workers"]):
            raise ValueError("model workers are not both released: " + key)
        prefix = {"phase": phase, "model": profile, "condition": condition}
        overall.append({
            **prefix, "planned": scores["planned"], "received": scores["received"],
            "unreturned": scores["planned"] - scores["received"], "all_correct": scores["all_correct"],
            "strict_percentage": 100 * scores["all_correct"] / scores["planned"],
            "conditional_percentage": 100 * scores["all_correct"] / scores["received"] if scores["received"] else None,
            "shape_valid": scores["shape_valid"], "output_tokens": counts["output_tokens"],
            "generation_h100_allocation_hours": analysis["generation_h100_hours"],
            "first_worker_start_utc": min((w["job"]["start_time"] for w in analysis["workers"]
                                           if w["job"].get("start_time")), default=""),
            "last_worker_complete_utc": max((w["job"]["complete_time"] for w in analysis["workers"]
                                             if w["job"].get("complete_time")), default=""),
            "worker_stop_reasons": json.dumps({str(w["worker_id"]): (w.get("completion") or {}).get("stop_reason", "missing_completion")
                                                for w in analysis["workers"]}, sort_keys=True),
            "all_gpu_jobs_succeeded": all(w["job"]["state"] == "SUCCEEDED" for w in analysis["workers"]),
            "analysis_id": analysis["analysis_id"], "report_id": analysis["report_id"],
        })
        for method in METHODS:
            grouped.append({**prefix, "dimension": "method", "group": "all", "method": method,
                            **flatten(analysis["methods"][method])})
        for dimension, groups in analysis["cross_tables"].items():
            partition = [r for methods in groups.values() for r in methods.values()]
            if any(sum(r[metric] for r in partition) != scores[metric]
                   for metric in ("planned", "received", "shape_valid", "all_correct")):
                raise ValueError("partition does not reproduce overall counts: " + key + "/" + dimension)
            for group, methods in sorted(groups.items()):
                for method in METHODS:
                    grouped.append({**prefix, "dimension": dimension, "group": group, "method": method,
                                    **flatten(methods[method])})
        summaries[key] = {k: v for k, v in analysis.items() if k != "records"}
    notes = [
        "Primary accuracy uses all planned slots; returned-only accuracy is supplementary.",
        "All methods receive identical cumulative source evidence plus their own declared carrier.",
        "Different conditions generate separate histories; there is no shared-prefix causal estimate.",
        "Later conditions have less collection time before the shared deadline; deadline censoring is not a pure prompt-role effect.",
        "Six development storms and repeat0 support descriptive results only.",
        "These three protocol cells are not a complete role-by-whitespace factorial.",
        "H100 hours are generation-job allocation time, including loading; preflights are separate.",
        "Grouped CSV values are counts; missing error-category cells mean zero occurrences.",
    ]
    lines = ["# Verified P11-P14 tables", "", *["- " + note for note in notes], "",
             "| Phase | Model | Condition | Returned / planned | Strictly correct | Strict % | H100 allocation h |",
             "| --- | --- | --- | ---: | ---: | ---: | ---: |"]
    for row in overall:
        lines.append(f"| {row['phase']} | {row['model']} | {row['condition']} | {row['received']}/{row['planned']} | "
                     f"{row['all_correct']} | {row['strict_percentage']:.4f} | {row['generation_h100_allocation_hours']:.4f} |")
    lines += ["", "## Method counts", "",
              "| Phase | Model | Method | Returned / planned | Shape valid | Strictly correct | Whole targets / 144 |",
              "| --- | --- | --- | ---: | ---: | ---: | ---: |"]
    for phase, profile, _, _ in CASES:
        analysis = summaries[phase + "_" + profile]
        for method in METHODS:
            row = analysis["methods"][method]
            target = analysis["targets"][method]
            lines.append(f"| {phase} | {profile} | {method} | {row['received']}/{row['planned']} | "
                         f"{row['shape_valid']} | {row['all_correct']} | {target['whole_target_single_repeat']}/{target['planned_targets']} |")
    return {
        "overall.csv": csv_bytes(overall), "grouped_counts.csv": csv_bytes(grouped),
        "TABLES.md": ("\n".join(lines) + "\n").encode(),
        "summary.json": encoded({"notes": notes, "overall": overall, "analyses_without_per_slot_records": summaries}) + b"\n",
    }, inputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=PROJECT)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    content, inputs = build(args.project.resolve())
    record = {"schema_version": "verified_cohort_table_export_v1", "input_sha256": inputs,
              "files_sha256": {name: sha(data) for name, data in content.items()},
              "script_sha256": sha(Path(__file__).read_bytes()), "rescored": False, "new_model_calls": 0}
    record["export_id"] = sha(encoded(record))
    content["manifest.json"] = encoded(record) + b"\n"
    if args.verify:
        for name, expected in content.items():
            if (args.output / name).read_bytes() != expected:
                raise ValueError("exported table differs: " + name)
    else:
        args.output.mkdir(parents=True, exist_ok=False)
        for name, data in content.items():
            with (args.output / name).open("xb") as stream:
                stream.write(data)
    print(json.dumps({"status": "passed", "export_id": record["export_id"],
                      "files": len(content), "verified": args.verify}), flush=True)


if __name__ == "__main__":
    main()
